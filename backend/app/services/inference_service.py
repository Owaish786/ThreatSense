from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


@dataclass
class PredictionResult:
    attack_type: str
    confidence: float
    anomaly_score: float | None
    is_anomaly: bool | None
    final_attack_type: str
    risk_level: str
    is_suspicious: bool
    risk_reason: str


class InferenceService:
    def __init__(self) -> None:
        self._loaded = False
        self._model = None
        self._iforest = None
        self._feature_columns: list[str] | None = None
        self._numeric_columns: list[str] = []
        self._categorical_columns: list[str] = []
        self._normal_confidence_floor = float(os.getenv('NORMAL_CONFIDENCE_FLOOR', '0.95'))

    @property
    def normal_confidence_floor(self) -> float:
        return self._normal_confidence_floor

    @property
    def required_feature_columns(self) -> list[str]:
        self._load_artifacts()
        return list(self._feature_columns or [])

    def _resolve_model_dir(self) -> Path:
        env_dir = os.getenv('MODEL_DIR')
        if env_dir:
            raw = Path(env_dir)
            if raw.is_absolute():
                return raw
            return (Path(__file__).resolve().parents[3] / env_dir).resolve()
        return (Path(__file__).resolve().parents[3] / 'ml' / 'models').resolve()

    def _load_artifacts(self) -> None:
        if self._loaded:
            return

        model_dir = self._resolve_model_dir()
        model_path = model_dir / 'trained_pipeline.joblib'
        iforest_path = model_dir / 'iforest.joblib'
        preprocess_bundle_path = model_dir / 'preprocess_bundle.joblib'

        if not model_path.exists():
            raise FileNotFoundError(f'Missing model artifact: {model_path}')

        self._model = joblib.load(model_path)

        if iforest_path.exists():
            self._iforest = joblib.load(iforest_path)

        if preprocess_bundle_path.exists():
            bundle = joblib.load(preprocess_bundle_path)
            cols = bundle.get('feature_columns')
            if isinstance(cols, list) and cols:
                self._feature_columns = cols
            numeric_cols = bundle.get('numeric_cols')
            if isinstance(numeric_cols, list):
                self._numeric_columns = numeric_cols
            categorical_cols = bundle.get('categorical_cols')
            if isinstance(categorical_cols, list):
                self._categorical_columns = categorical_cols

        # Fallback to model metadata if bundle is missing.
        if self._feature_columns is None and hasattr(self._model, 'feature_names_in_'):
            self._feature_columns = list(self._model.feature_names_in_)

        self._loaded = True

    def _prepare_input(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._feature_columns:
            return df

        prepared = df.copy()
        for col in self._feature_columns:
            if col not in prepared.columns:
                prepared[col] = np.nan

        prepared = prepared[self._feature_columns]

        # Normalize text artifacts from CSV parsing edge cases (e.g. values like '"0').
        for col in prepared.columns:
            if prepared[col].dtype == object:
                prepared[col] = (
                    prepared[col]
                    .astype(str)
                    .str.strip()
                    .str.strip('"')
                    .str.strip("'")
                    .replace({'': np.nan, 'nan': np.nan, 'None': np.nan})
                )

        # Ensure numeric features are parsed as numbers for median imputation.
        if self._numeric_columns:
            for col in self._numeric_columns:
                if col in prepared.columns:
                    prepared[col] = pd.to_numeric(prepared[col], errors='coerce')

        return prepared

    @staticmethod
    def _num(row: pd.Series, key: str) -> float:
        val = row.get(key, 0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    def _rule_based_suspicion(self, row: pd.Series) -> tuple[bool, str]:
        # Weighted rules to catch strong attack-like behavior when the model is conservative.
        score = 0
        reasons: list[str] = []

        if self._num(row, 'root_shell') > 0:
            score += 4
            reasons.append('root_shell_activity')
        if self._num(row, 'su_attempted') > 0:
            score += 4
            reasons.append('su_attempted_activity')

        if self._num(row, 'num_compromised') >= 5:
            score += 3
            reasons.append('high_compromised_count')
        if self._num(row, 'num_failed_logins') >= 5:
            score += 2
            reasons.append('many_failed_logins')

        count = self._num(row, 'count')
        serror_rate = self._num(row, 'serror_rate')
        rerror_rate = self._num(row, 'rerror_rate')
        same_srv_rate = self._num(row, 'same_srv_rate')
        diff_srv_rate = self._num(row, 'diff_srv_rate')
        dst_host_srv_diff_host_rate = self._num(row, 'dst_host_srv_diff_host_rate')
        src_bytes = self._num(row, 'src_bytes')
        dst_bytes = self._num(row, 'dst_bytes')

        flag = str(row.get('flag', '')).strip().upper()
        service = str(row.get('service', '')).strip().lower()

        if serror_rate >= 0.95 and count >= 300:
            score += 3
            reasons.append('high_serror_volume')
        if rerror_rate >= 0.90 and count >= 200:
            score += 2
            reasons.append('high_rerror_volume')
        if flag in {'S0', 'REJ', 'RSTOS0', 'RSTR'} and count >= 200 and (serror_rate >= 0.7 or rerror_rate >= 0.7):
            score += 3
            reasons.append('repeated_reject_pattern')
        if src_bytes == 0 and dst_bytes == 0 and count >= 250 and (serror_rate >= 0.5 or rerror_rate >= 0.5):
            score += 2
            reasons.append('zero_byte_error_flood')
        if diff_srv_rate >= 0.7 and same_srv_rate <= 0.3:
            score += 2
            reasons.append('service_scan_pattern')
        if dst_host_srv_diff_host_rate >= 0.5:
            score += 1
            reasons.append('cross_host_spread_pattern')
        if service in {'private', 'ftp', 'ftp_data', 'telnet', 'imap', 'smtp', 'ssh'} and self._num(row, 'num_failed_logins') >= 3:
            score += 2
            reasons.append('credential_probe_pattern')

        if score >= 3:
            return True, '|'.join(reasons)
        return False, 'none'

    def classify_risk(
        self,
        attack_type: str,
        confidence: float,
        is_anomaly: bool | None,
        suspicious_by_rules: bool = False,
        rule_reason: str = 'none',
    ) -> tuple[str, str, bool, str]:
        normalized_label = str(attack_type).strip().lower()
        if normalized_label != 'normal':
            return attack_type, 'malicious', False, 'classifier_attack_label'
        if is_anomaly is True:
            return 'suspicious_normal', 'suspicious', True, 'iforest_anomaly'
        if suspicious_by_rules:
            return 'suspicious_normal', 'suspicious', True, rule_reason
        if confidence < self._normal_confidence_floor:
            return 'uncertain_normal', 'suspicious', True, 'low_confidence_normal'
        return 'normal', 'normal', False, 'high_confidence_normal'

    def predict_dataframe(self, df: pd.DataFrame) -> list[PredictionResult]:
        self._load_artifacts()

        if self._model is None:
            raise RuntimeError('Model was not loaded')

        input_df = self._prepare_input(df)
        labels = self._model.predict(input_df)

        confidences: np.ndarray
        if hasattr(self._model, 'predict_proba'):
            proba = self._model.predict_proba(input_df)
            confidences = np.max(proba, axis=1)
        else:
            confidences = np.full(shape=(len(input_df),), fill_value=np.nan, dtype=float)

        anomaly_scores: np.ndarray | None = None
        anomaly_flags: np.ndarray | None = None
        if self._iforest is not None and hasattr(self._model, 'named_steps'):
            preprocess = self._model.named_steps.get('preprocess')
            if preprocess is not None:
                transformed = preprocess.transform(input_df)
                anomaly_scores = self._iforest.decision_function(transformed)
                anomaly_flags = self._iforest.predict(transformed)

        results: list[PredictionResult] = []
        for i, label in enumerate(labels):
            row = input_df.iloc[i]
            score = None if anomaly_scores is None else float(anomaly_scores[i])
            is_anomaly = None if anomaly_flags is None else bool(anomaly_flags[i] == -1)
            confidence = float(confidences[i]) if not np.isnan(confidences[i]) else 0.0
            suspicious_by_rules, rule_reason = self._rule_based_suspicion(row)
            final_attack_type, risk_level, is_suspicious, risk_reason = self.classify_risk(
                attack_type=str(label),
                confidence=confidence,
                is_anomaly=is_anomaly,
                suspicious_by_rules=suspicious_by_rules,
                rule_reason=rule_reason,
            )
            results.append(
                PredictionResult(
                    attack_type=str(label),
                    confidence=confidence,
                    anomaly_score=score,
                    is_anomaly=is_anomaly,
                    final_attack_type=final_attack_type,
                    risk_level=risk_level,
                    is_suspicious=is_suspicious,
                    risk_reason=risk_reason,
                )
            )
        return results


inference_service = InferenceService()
