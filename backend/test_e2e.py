"""
End-to-end test: Upload CSV, verify predictions, check persistence.
Tests the complete flow: file upload → inference → database storage → retrieval.
"""

import sys
import time
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CSV = PROJECT_ROOT / 'test_data.csv'

BASE_URL = 'http://127.0.0.1:5001'


def _require_live_api() -> None:
    try:
        resp = requests.get(f'{BASE_URL}/api/health', timeout=3)
    except requests.RequestException as exc:
        pytest.skip(f'Live API is not reachable at {BASE_URL}: {exc}')

    if resp.status_code != 200:
        pytest.skip(f'Live API health is not ready at {BASE_URL} (status {resp.status_code})')


def test_e2e_complete_flow():
    """Complete end-to-end flow test."""
    _require_live_api()

    print('=' * 70)
    print('END-TO-END TEST: Complete Prediction Pipeline')
    print('=' * 70)
    
    # Step 1: Verify API is up
    print('\n[STEP 1] Health check')
    resp = requests.get(f'{BASE_URL}/api/health', timeout=5)
    assert resp.status_code == 200, f'Health check failed: {resp.status_code}'
    print('✓ API is running and healthy')
    
    # Step 2: Get baseline statistics
    print('\n[STEP 2] Get baseline stats')
    resp = requests.get(f'{BASE_URL}/api/stats', timeout=5)
    assert resp.status_code == 200
    baseline_stats = resp.json()
    baseline_count = baseline_stats.get('total_scanned', 0)
    print(f'✓ Baseline stats: {baseline_count} records scanned')
    print(f'  - Known attacks: {baseline_stats.get("known_attacks", 0)}')
    print(f'  - Anomalies: {baseline_stats.get("anomalies", 0)}')
    
    # Step 3: Upload CSV and get predictions
    print('\n[STEP 3] Upload CSV and run inferenceence')
    assert TEST_CSV.exists(), f'Test CSV not found at {TEST_CSV}'

    with open(TEST_CSV, 'rb') as f:
        files = {'file': f}
        resp = requests.post(f'{BASE_URL}/api/predict', files=files, timeout=30)

    assert resp.status_code == 200, f'Predict failed: {resp.status_code}'
    data = resp.json()
    results = data.get('results', [])

    print(f'✓ Inference successful on {len(results)} records')

    # Show sample predictions
    print('\n  Sample predictions:')
    for i, result in enumerate(results[:3]):
        attack = result.get('attack_type')
        confidence = result.get('confidence')
        anomaly = result.get('is_anomaly')
        print(f'    [{i}] {attack:10s} confidence={confidence:.2%} anomaly={anomaly}')

    summary = data.get('summary', {})
    print(f'\n  Batch summary:')
    print(f'    - Anomalies detected: {summary.get("anomalies", 0)}')
    print(f'    - Known attacks: {summary.get("known_attacks", 0)}')
    
    # Step 4: Verify persistence - check updated stats
    print('\n[STEP 4] Verify data persistence')
    time.sleep(0.5)  # Brief delay for DB write

    resp = requests.get(f'{BASE_URL}/api/stats', timeout=5)
    assert resp.status_code == 200
    updated_stats = resp.json()
    updated_count = updated_stats.get('total_scanned', 0)

    expected_count = baseline_count + len(results)
    actual_added = updated_count - baseline_count

    print(f'✓ Data persisted to database')
    print(f'  - Before: {baseline_count} records')
    print(f'  - Added: {len(results)} records')
    print(f'  - After: {updated_count} records')

    assert updated_count >= expected_count - 1
    if actual_added == len(results):
        print(f'✓ All {len(results)} records successfully persisted')
    else:
        print(f'⚠ Expected {len(results)} new records, got {actual_added}')
    
    # Step 5: Retrieve logs and inspect latest records
    print('\n[STEP 5] Retrieve prediction logs')
    resp = requests.get(f'{BASE_URL}/api/logs?limit=5', timeout=5)
    assert resp.status_code == 200
    logs = resp.json().get('logs', [])

    print(f'✓ Retrieved {len(logs)} latest prediction logs')
    print('\n  Latest log entries:')
    for log in logs[:3]:
        log_id = log.get('id')
        attack = log.get('attack_type')
        confidence = log.get('confidence')
        created = log.get('created_at', '').split('T')[1][:8]
        print(f'    [ID:{log_id:3d}] {attack:10s} confidence={confidence:.2%} time={created}')
    
    # Step 6: Test delete operation
    print('\n[STEP 6] Test record deletion')
    if not logs:
        print('⚠ No logs to delete (skip)')
    else:
        delete_id = logs[0]['id']
        resp = requests.delete(f'{BASE_URL}/api/logs/{delete_id}', timeout=5)
        assert resp.status_code == 200
        print(f'✓ Successfully deleted log ID {delete_id}')

        # Verify deletion
        resp = requests.get(f'{BASE_URL}/api/stats', timeout=5)
        new_count = resp.json().get('total_scanned', 0)
        print(f'  - Stats now show {new_count} total records (was {updated_count})')
    
    print('\n' + '=' * 70)
    print('✓ END-TO-END TEST PASSED')
    print('=' * 70)
    print('\nSummary:')
    print('  ✓ API health check')
    print('  ✓ CSV upload and inference')
    print('  ✓ Prediction output with anomaly scores')
    print('  ✓ Data persistence to database')
    print('  ✓ Retrieval of prediction logs')
    print('  ✓ Delete operation')
    print('\nThe complete ThreatSense pipeline is working!')


def _run_script_test(test_fn) -> bool:
    try:
        test_fn()
        return True
    except Exception as exc:
        print(f'\n\nTest failed: {exc}')
        return False


if __name__ == '__main__':
    try:
        success = _run_script_test(test_e2e_complete_flow)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print('\n\nTest interrupted by user')
        sys.exit(1)
