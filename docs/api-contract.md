# API contract draft

## GET /api/health
Response:
- status
- service

## POST /api/predict
Input:
- multipart form-data file (CSV)

Output per record:
- attack_type
- severity
- confidence
- anomaly_score

## GET /api/logs
Output:
- paginated prediction logs

## GET /api/stats
Output:
- total_scanned
- known_attacks
- anomalies
- model_version

## DELETE /api/logs/:id
Output:
- deletion status
