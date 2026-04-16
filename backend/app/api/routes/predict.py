from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict

import pandas as pd
from flask import Blueprint, jsonify, request
from sqlalchemy import case, func, select

from app.core.config import settings
from app.db.base import get_session
from app.db.models import PredictionLog
from app.services.inference_service import inference_service

predict_bp = Blueprint('predict', __name__)


def _canonical_col(name: str) -> str:
    normalized = str(name).strip().lstrip('\ufeff').lower()
    normalized = re.sub(r'[^a-z0-9]+', '_', normalized)
    return normalized.strip('_')


def _decode_csv_bytes(raw_bytes: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode('utf-8', errors='replace')


def _candidate_separators(sample_text: str) -> list[str]:
    candidates: list[str] = []
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=',;\t|')
        if isinstance(dialect.delimiter, str) and len(dialect.delimiter) == 1:
            candidates.append(dialect.delimiter)
    except Exception:
        pass

    for sep in [',', ';', '\t', '|']:
        if sep not in candidates:
            candidates.append(sep)
    return candidates


def _find_header_row(csv_text: str, required_columns: list[str], separators: list[str]) -> tuple[int, str] | None:
    required_canonical = {_canonical_col(col) for col in required_columns}
    lines = csv_text.splitlines()
    inspect_limit = min(len(lines), 12)
    best: tuple[int, str, int] | None = None

    for row_idx in range(inspect_limit):
        line = lines[row_idx]
        if not line.strip():
            continue
        for sep in separators:
            cells = [c.strip().strip('"').strip("'") for c in line.split(sep)]
            overlap = sum(1 for c in cells if _canonical_col(c) in required_canonical)
            if best is None or overlap > best[2]:
                best = (row_idx, sep, overlap)

    if best is None:
        return None

    # Accept as header row only when we have strong evidence.
    row_idx, sep, overlap = best
    if overlap >= max(8, len(required_columns) // 3):
        return row_idx, sep
    return None


def _read_csv_with_fallback(raw_bytes: bytes, header: int | str | None = 'infer', names: list[str] | None = None) -> pd.DataFrame:
    csv_text = _decode_csv_bytes(raw_bytes)
    sample = csv_text[:4096]
    separators = _candidate_separators(sample)

    last_exc: Exception | None = None
    for sep in separators:
        try:
            kwargs: dict[str, object] = {'sep': sep, 'engine': 'python', 'header': header}
            if names is not None:
                kwargs['names'] = names
            df = pd.read_csv(io.StringIO(csv_text), **kwargs)
            if not df.empty:
                return df
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

    raise ValueError(f'Could not parse CSV with supported delimiters: {last_exc}')


def _read_csv_with_header_detection(raw_bytes: bytes, required_columns: list[str]) -> pd.DataFrame:
    csv_text = _decode_csv_bytes(raw_bytes)
    separators = _candidate_separators(csv_text[:4096])
    header_info = _find_header_row(csv_text, required_columns, separators)

    if header_info is None:
        return _read_csv_with_fallback(raw_bytes)

    header_row, sep = header_info
    return pd.read_csv(io.StringIO(csv_text), sep=sep, engine='python', skiprows=header_row)


def _repair_collapsed_single_column(df: pd.DataFrame, raw_bytes: bytes, required_columns: list[str]) -> pd.DataFrame:
    if len(df.columns) != 1:
        return df

    only_header = str(df.columns[0]).strip().strip('"').strip("'")
    required_canonical = {_canonical_col(col) for col in required_columns}
    csv_text = _decode_csv_bytes(raw_bytes)

    best_sep: str | None = None
    best_overlap = -1
    for sep in [',', ';', '\t', '|']:
        parts = [p.strip().strip('"').strip("'") for p in only_header.split(sep)]
        overlap = sum(1 for p in parts if _canonical_col(p) in required_canonical)
        if overlap > best_overlap:
            best_overlap = overlap
            best_sep = sep

    if best_sep is None or best_overlap < max(8, len(required_columns) // 3):
        return df

    # Parse with quoting disabled to force splitting when the whole header line is quoted.
    try:
        repaired = pd.read_csv(
            io.StringIO(csv_text),
            sep=best_sep,
            engine='python',
            quoting=csv.QUOTE_NONE,
        )
        if not repaired.empty and len(repaired.columns) > 1:
            return repaired
    except Exception:
        pass

    return df


@predict_bp.post('/api/predict')
def predict_csv() -> tuple:
    if 'file' not in request.files:
        return jsonify({'error': "Missing upload field 'file'"}), 400

    file = request.files['file']
    if file.filename is None or file.filename.strip() == '':
        return jsonify({'error': 'Empty file name'}), 400

    required_columns = inference_service.required_feature_columns
    raw_bytes = file.read()
    if not raw_bytes:
        return jsonify({'error': 'Uploaded CSV has no content'}), 400

    upload_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    try:
        # First attempt: detect header row (even if not first line), then parse.
        df = _read_csv_with_header_detection(raw_bytes, required_columns)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': f'Could not parse CSV: {exc}'}), 400

    df = _repair_collapsed_single_column(df, raw_bytes, required_columns)

    if df.empty:
        return jsonify({'error': 'Uploaded CSV has no rows'}), 400

    # Normalize upload headers to tolerate BOM, casing, and extra spaces.
    rename_map: dict[str, str] = {}
    uploaded_by_canonical = {_canonical_col(col): col for col in df.columns}
    for required in required_columns:
        canonical_required = _canonical_col(required)
        if canonical_required in uploaded_by_canonical:
            rename_map[uploaded_by_canonical[canonical_required]] = required
    if rename_map:
        df = df.rename(columns=rename_map)

    missing_columns = [col for col in required_columns if col not in df.columns]
    overlap_count = len(required_columns) - len(missing_columns)

    # Second attempt: headerless CSV where the first row is actual data.
    # Trigger this only when overlap with expected headers is very low.
    if missing_columns and overlap_count < max(5, len(required_columns) // 2):
        try:
            headerless_raw = _read_csv_with_fallback(raw_bytes, header=None)
            if not headerless_raw.empty and headerless_raw.shape[1] >= len(required_columns):
                headerless_df = headerless_raw.iloc[:, : len(required_columns)].copy()
                headerless_df.columns = required_columns
                first_row = headerless_df.iloc[0]
                header_like_cells = sum(
                    1 for col in required_columns if _canonical_col(first_row.get(col, '')) == _canonical_col(col)
                )
                # If many cells look like header names, this is likely an actual header row.
                if header_like_cells >= 5:
                    raise ValueError('detected_header_row')
                df = headerless_df
                missing_columns = []
        except Exception:
            pass

    if missing_columns:
        hint = 'Ensure the file is plain CSV (not Excel), with one header row and 41 NSL-KDD feature columns.'
        if overlap_count == 0:
            hint = 'No expected headers were detected. The file may be Excel content renamed to .csv, or use an unsupported separator/encoding.'
        return (
            jsonify(
                {
                    'error': 'CSV schema mismatch. Include all 41 NSL-KDD feature columns.',
                    'hint': hint,
                    'missing_columns': missing_columns,
                    'received_columns': [str(col) for col in df.columns],
                    'sample_first_row': [str(v) for v in (df.iloc[0].tolist()[:8] if not df.empty else [])],
                    'required_count': len(required_columns),
                    'provided_count': len(df.columns),
                }
            ),
            400,
        )

    try:
        predictions = inference_service.predict_dataframe(df)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': f'Inference failed: {exc}'}), 500

    rows = []
    to_insert: list[PredictionLog] = []

    for idx, prediction in enumerate(predictions):
        row = asdict(prediction)
        row['row_index'] = idx
        rows.append(row)

        to_insert.append(
            PredictionLog(
                row_index=idx,
                attack_type=row['attack_type'],
                confidence=row['confidence'],
                anomaly_score=row['anomaly_score'],
                is_anomaly=row['is_anomaly'],
            )
        )

    with get_session() as session:
        session.add_all(to_insert)
        session.flush()

        for row, entity in zip(rows, to_insert):
            row['id'] = entity.id
            row['created_at'] = entity.created_at.isoformat() if entity.created_at else None

    batch_signature_source = [
        {
            'attack_type': row.get('attack_type'),
            'final_attack_type': row.get('final_attack_type'),
            'risk_level': row.get('risk_level'),
            'confidence': round(float(row.get('confidence') or 0.0), 8),
            'anomaly_score': None if row.get('anomaly_score') is None else round(float(row.get('anomaly_score')), 8),
            'is_anomaly': row.get('is_anomaly'),
            'is_suspicious': row.get('is_suspicious'),
        }
        for row in rows
    ]
    batch_signature = hashlib.sha256(
        json.dumps(batch_signature_source, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()

    return (
        jsonify(
            {
                'count': len(rows),
                'input_rows': len(df),
                'input_columns': [str(col) for col in df.columns],
                'upload_sha256': upload_sha256,
                'batch_signature': batch_signature,
                'results': rows,
                'summary': {
                    'anomalies': sum(1 for r in rows if r.get('is_anomaly') is True),
                    'known_attacks': sum(1 for r in rows if r.get('risk_level') == 'malicious'),
                    'suspicious': sum(1 for r in rows if r.get('is_suspicious') is True),
                },
            }
        ),
        200,
    )


@predict_bp.get('/api/logs')
def get_logs() -> tuple:
    raw_limit = request.args.get('limit', '200')
    try:
        limit = max(1, min(int(raw_limit), 1000))
    except ValueError:
        return jsonify({'error': 'limit must be an integer'}), 400

    with get_session() as session:
        query = (
            select(
                PredictionLog.id,
                PredictionLog.row_index,
                PredictionLog.attack_type,
                PredictionLog.confidence,
                PredictionLog.anomaly_score,
                PredictionLog.is_anomaly,
                PredictionLog.created_at,
            )
            .order_by(PredictionLog.id.desc())
            .limit(limit)
        )
        entries = session.execute(query).all()
        
        logs = []
        for entry in entries:
            log_id, row_index, attack_type, confidence, anomaly_score, is_anomaly, created_at = entry
            final_attack_type, risk_level, is_suspicious, risk_reason = inference_service.classify_risk(
                attack_type=attack_type,
                confidence=confidence,
                is_anomaly=is_anomaly,
            )
            logs.append(
                {
                    'id': log_id,
                    'row_index': row_index,
                    'attack_type': attack_type,
                    'confidence': confidence,
                    'anomaly_score': anomaly_score,
                    'is_anomaly': is_anomaly,
                    'final_attack_type': final_attack_type,
                    'risk_level': risk_level,
                    'is_suspicious': is_suspicious,
                    'risk_reason': risk_reason,
                    'created_at': created_at.isoformat() if created_at else None,
                }
            )
    
    return jsonify({'count': len(logs), 'logs': logs}), 200


@predict_bp.get('/api/stats')
def get_stats() -> tuple:
    with get_session() as session:
        suspicious_condition = (
            (PredictionLog.attack_type == 'normal')
            & (
                (PredictionLog.is_anomaly.is_(True))
                | (PredictionLog.confidence < inference_service.normal_confidence_floor)
            )
        )

        stats_query = select(
            func.count().label('total_scanned'),
            func.coalesce(func.sum(case((PredictionLog.attack_type != 'normal', 1), else_=0)), 0).label('known_attacks'),
            func.coalesce(func.sum(case((PredictionLog.is_anomaly.is_(True), 1), else_=0)), 0).label('anomalies'),
            func.coalesce(func.sum(case((suspicious_condition, 1), else_=0)), 0).label('suspicious'),
        ).select_from(PredictionLog)

        row = session.execute(stats_query).one()
        total = int(row.total_scanned or 0)
        known_attacks = int(row.known_attacks or 0)
        anomalies = int(row.anomalies or 0)
        suspicious = int(row.suspicious or 0)

    return (
        jsonify(
            {
                'total_scanned': total,
                'known_attacks': known_attacks,
                'anomalies': anomalies,
                'suspicious': suspicious,
                'model_version': settings.model_version,
            }
        ),
        200,
    )


@predict_bp.delete('/api/logs/<int:log_id>')
def delete_log(log_id: int) -> tuple:
    with get_session() as session:
        entry = session.get(PredictionLog, log_id)
        if entry is None:
            return jsonify({'deleted': False, 'id': log_id, 'error': 'Log not found'}), 404
        session.delete(entry)

    return jsonify({'deleted': True, 'id': log_id}), 200
