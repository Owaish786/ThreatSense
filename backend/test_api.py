"""
Flask API integration test script.
Tests the /api/predict, /api/logs, /api/stats endpoints.
Requires Flask backend to be running on http://localhost:5000.
"""

import sys
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CSV = PROJECT_ROOT / 'test_data.csv'

BASE_URL = 'http://localhost:5000'


def _require_live_api() -> None:
    try:
        resp = requests.get(f'{BASE_URL}/api/health', timeout=3)
    except requests.RequestException as exc:
        pytest.skip(f'Live API is not reachable at {BASE_URL}: {exc}')

    if resp.status_code != 200:
        pytest.skip(f'Live API health is not ready at {BASE_URL} (status {resp.status_code})')


def test_health():
    """Test /api/health endpoint."""
    print('Testing GET /api/health')
    _require_live_api()
    resp = requests.get(f'{BASE_URL}/api/health', timeout=5)
    print(f'  Status: {resp.status_code}')
    print(f'  Response: {resp.json()}')
    assert resp.status_code == 200


def test_predict():
    """Test POST /api/predict with CSV upload."""
    print('\nTesting POST /api/predict')
    _require_live_api()

    assert TEST_CSV.exists(), (
        f'Test CSV not found at {TEST_CSV}. '
        'Run: python backend/test_model.py first to generate test_data.csv'
    )

    with open(TEST_CSV, 'rb') as f:
        files = {'file': f}
        resp = requests.post(f'{BASE_URL}/api/predict', files=files, timeout=30)
    print(f'  Status: {resp.status_code}')
    data = resp.json()
    print(f'  Count: {data.get("count")}')
    if data.get('results'):
        first = data['results'][0]
        print(f'  First result: attack_type={first.get("attack_type")}, confidence={first.get("confidence"):.4f}')
    if data.get('summary'):
        print(f'  Summary: {data.get("summary")}')

    assert resp.status_code == 200
    assert data.get('count', 0) > 0


def test_stats():
    """Test GET /api/stats."""
    print('\nTesting GET /api/stats')
    _require_live_api()
    resp = requests.get(f'{BASE_URL}/api/stats', timeout=5)
    print(f'  Status: {resp.status_code}')
    data = resp.json()
    print(f'  Stats: {data}')
    assert resp.status_code == 200


def test_logs():
    """Test GET /api/logs."""
    print('\nTesting GET /api/logs')
    _require_live_api()
    resp = requests.get(f'{BASE_URL}/api/logs?limit=5', timeout=5)
    print(f'  Status: {resp.status_code}')
    data = resp.json()
    print(f'  Count: {data.get("count")}')
    if data.get('logs'):
        print(f'  Latest log: {data["logs"][0]}')
    assert resp.status_code == 200


def test_delete_log():
    """Test DELETE /api/logs/:id."""
    print('\nTesting DELETE /api/logs/:id')
    _require_live_api()
    # First, get latest log
    resp = requests.get(f'{BASE_URL}/api/logs?limit=1', timeout=5)
    assert resp.status_code == 200

    data = resp.json()
    if not data.get('logs'):
        print('  INFO: No logs to delete')
        return

    log_id = data['logs'][0]['id']
    print(f'  Deleting log id={log_id}')

    resp = requests.delete(f'{BASE_URL}/api/logs/{log_id}', timeout=5)
    print(f'  Status: {resp.status_code}')
    print(f'  Response: {resp.json()}')
    assert resp.status_code == 200
    assert resp.json().get('deleted') is True


def _run_script_test(test_fn) -> bool:
    try:
        test_fn()
        return True
    except Exception as exc:
        print(f'  ERROR: {exc}')
        return False


if __name__ == '__main__':
    print('=' * 60)
    print('ThreatSense Flask API Integration Tests')
    print('=' * 60)
    print(f'Base URL: {BASE_URL}')

    results = {
        'health': _run_script_test(test_health),
        'predict': _run_script_test(test_predict),
        'stats': _run_script_test(test_stats),
        'logs': _run_script_test(test_logs),
        'delete': _run_script_test(test_delete_log),
    }

    print('\n' + '=' * 60)
    print('TEST SUMMARY')
    print('=' * 60)
    for name, passed in results.items():
        status = '✓ PASS' if passed else '✗ FAIL'
        print(f'{status}: {name}')

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
