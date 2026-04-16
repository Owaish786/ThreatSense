"""
Test script to validate ThreatSense model loading and inference.
Run this to confirm models load correctly before starting Flask.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / 'ml' / 'models'
RAW_DIR = PROJECT_ROOT / 'ml' / 'data' / 'raw'

# Expected NSL-KDD columns
COLUMN_NAMES = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes', 'land',
    'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in', 'num_compromised',
    'root_shell', 'su_attempted', 'num_root', 'num_file_creations', 'num_shells',
    'num_access_files', 'num_outbound_cmds', 'is_host_login', 'is_guest_login', 'count',
    'srv_count', 'serror_rate', 'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate',
    'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate', 'dst_host_count',
    'dst_host_srv_count', 'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
    'dst_host_srv_serror_rate', 'dst_host_rerror_rate', 'dst_host_srv_rerror_rate',
    'label', 'difficulty'
]


def test_model_loading():
    """Test that all model artifacts load without error."""
    print('=' * 60)
    print('TEST 1: Model artifact loading')
    print('=' * 60)

    model_path = MODEL_DIR / 'trained_pipeline.joblib'
    iforest_path = MODEL_DIR / 'iforest.joblib'
    preprocess_path = MODEL_DIR / 'preprocess_bundle.joblib'

    assert model_path.exists(), f'Model not found at {model_path}'

    try:
        model = joblib.load(model_path)
        print(f'✓ Loaded RFC pipeline from {model_path.name}')
    except Exception as exc:
        raise AssertionError(f'ERROR loading model: {exc}') from exc

    if iforest_path.exists():
        try:
            iforest = joblib.load(iforest_path)
            print(f'✓ Loaded Isolation Forest from {iforest_path.name}')
        except Exception as exc:
            raise AssertionError(f'ERROR loading iforest: {exc}') from exc
    else:
        print(f'⚠ Isolation Forest not found at {iforest_path}')

    if preprocess_path.exists():
        try:
            bundle = joblib.load(preprocess_path)
            print(f'✓ Loaded preprocess bundle with {len(bundle)} keys')
        except Exception as exc:
            raise AssertionError(f'ERROR loading preprocess bundle: {exc}') from exc
    else:
        print(f'⚠ Preprocess bundle not found at {preprocess_path}')

def test_model_inference():
    """Test model inference on sample data from test set."""
    print('\n' + '=' * 60)
    print('TEST 2: Model inference on real data')
    print('=' * 60)

    test_path = RAW_DIR / 'KDDTest+.txt'
    assert test_path.exists(), f'Test data not found at {test_path}'

    try:
        df = pd.read_csv(test_path, names=COLUMN_NAMES)
        sample = df.iloc[:5, :-1]  # Drop label and difficulty
        print(f'✓ Loaded {len(df)} test records')
        print(f'✓ Using first {len(sample)} rows for inference')
    except Exception as exc:
        raise AssertionError(f'ERROR loading test data: {exc}') from exc

    try:
        model = joblib.load(MODEL_DIR / 'trained_pipeline.joblib')
        predictions = model.predict(sample)
        probas = model.predict_proba(sample)
        confidence = np.max(probas, axis=1)

        print(f'✓ Inference successful')
        print(f'\nSample predictions:')
        for i, (pred, conf) in enumerate(zip(predictions, confidence)):
            print(f'  Row {i}: {pred:12s} (confidence: {conf:.4f})')
    except Exception as exc:
        raise AssertionError(f'ERROR during inference: {exc}') from exc


def test_inference_service():
    """Test the Flask inference service wrapper."""
    print('\n' + '=' * 60)
    print('TEST 3: InferenceService wrapper')
    print('=' * 60)

    pytest.importorskip('flask', reason='Flask is required for InferenceService import path')

    try:
        from app.services.inference_service import inference_service
        print('✓ Imported InferenceService')
    except Exception as exc:
        raise AssertionError(f'ERROR importing InferenceService: {exc}') from exc

    test_path = RAW_DIR / 'KDDTest+.txt'
    assert test_path.exists(), f'Test data not found at {test_path}'

    try:
        df = pd.read_csv(test_path, names=COLUMN_NAMES)
        sample = df.iloc[:3, :-1]
        results = inference_service.predict_dataframe(sample)
        print(f'✓ Service returned {len(results)} results')
        for i, result in enumerate(results):
            print(f'  {i}: attack={result.attack_type}, confidence={result.confidence:.4f}, anomaly={result.is_anomaly}')
        assert len(results) > 0
    except Exception as exc:
        raise AssertionError(f'ERROR: {exc}') from exc


def create_test_csv():
    """Generate a small test CSV for API testing."""
    print('\n' + '=' * 60)
    print('TEST 4: Generate test CSV')
    print('=' * 60)

    test_path = RAW_DIR / 'KDDTest+.txt'
    assert test_path.exists(), f'Test data not found at {test_path}'

    try:
        df = pd.read_csv(test_path, names=COLUMN_NAMES)
        sample = df.iloc[:10, :-1]  # Drop label and difficulty

        output_path = PROJECT_ROOT / 'test_data.csv'
        sample.to_csv(output_path, index=False)
        print(f'✓ Created test CSV at {output_path}')
        print(f'  Shape: {sample.shape}')
        print(f'  Use this file to test POST /api/predict')
    except Exception as exc:
        raise AssertionError(f'ERROR: {exc}') from exc


def _run_script_test(test_fn) -> bool:
    try:
        test_fn()
        return True
    except Exception as exc:
        print(f'ERROR: {exc}')
        return False


if __name__ == '__main__':
    results = {
        'model_loading': _run_script_test(test_model_loading),
        'model_inference': _run_script_test(test_model_inference),
        'inference_service': _run_script_test(test_inference_service),
        'test_csv': _run_script_test(create_test_csv),
    }

    print('\n' + '=' * 60)
    print('TEST SUMMARY')
    print('=' * 60)
    for name, passed in results.items():
        status = '✓ PASS' if passed else '✗ FAIL'
        print(f'{status}: {name}')

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
