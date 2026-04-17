# Testing ThreatSense Model and API

## Part 1: Test Model Loading and Inference

Run the model test to validate that your trained artifacts work correctly:

```bash
cd /Users/mohamadowaishkhalak/Code/ThreatSense
python backend/test_model.py
```

This will:
1. Load your trained RandomForest pipeline (trained_pipeline.joblib)
2. Load Isolation Forest model (iforest.joblib)
3. Run inference on 5 test samples from KDDTest+.txt
4. Generate a test CSV file (test_data.csv) for API testing

Expected output:
- ✓ Model loaded successfully
- ✓ Inference on test data returns predictions
- ✓ test_data.csv generated at project root

## Part 2: Start Flask Backend

First, ensure you have created `.env` from `.env.example`:

```bash
cd /Users/mohamadowaishkhalak/Code/ThreatSense
cp .env.example .env
```

Edit `.env` and set DATABASE_URL (or leave it to use SQLite):
```
DATABASE_URL=sqlite:///threatsense.db
```

Install backend dependencies:
```bash
pip install -r backend/requirements.txt
```

Start Flask server:
```bash
cd backend
python -m flask run --host 0.0.0.0 --port 5001
```

You should see output like:
```
 * Running on http://0.0.0.0:5001
```

## Part 3: Test API Endpoints

In a separate terminal, run the API integration tests:

```bash
cd /Users/mohamadowaishkhalak/Code/ThreatSense
python backend/test_api.py
```

This will test:
1. GET /api/health — Server is running
2. POST /api/predict — Upload CSV and get predictions
3. GET /api/stats — Aggregate statistics
4. GET /api/logs — Retrieve prediction history
5. DELETE /api/logs/:id — Delete a specific log entry

Expected results:
- ✓ All endpoints respond with correct status codes
- ✓ Predictions stored in database
- ✓ Stats count increments correctly

## Part 4: Manual Testing with curl

You can also test endpoints manually:

```bash
# Health check
curl http://localhost:5001/api/health

# Upload CSV
curl -X POST -F "file=@test_data.csv" http://localhost:5001/api/predict

# Get stats
curl http://localhost:5001/api/stats

# Get logs (latest 10)
curl "http://localhost:5001/api/logs?limit=10"

# Delete a log (replace 1 with actual id)
curl -X DELETE http://localhost:5001/api/logs/1
```

## What to Check

1. **Model test output**: Predictions should show different attack types (normal, dos, probe, r2l, u2r) with confidence scores
2. **API inference**: POST /api/predict should return `attack_type`, `confidence`, `anomaly_score`, `is_anomaly` for each row
3. **Database**: Check that predictions persist after restart
4. **Stats**: GET /api/stats should show increasing counts after multiple uploads

## Troubleshooting

If tests fail:

1. **Model not found**: Ensure you ran the notebook and artifacts exist in ml/models/
2. **Import error**: Install dependencies: `pip install -r backend/requirements.txt`
3. **API not responding**: Check Flask is running on port 5001
4. **CSV parse error**: Ensure test_data.csv has correct NSL-KDD columns

Next steps after successful testing:
- Build frontend dashboard with upload panel
- Connect frontend API calls to these endpoints  
- Add PostgreSQL for production deployment
