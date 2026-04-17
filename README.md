# ThreatSense

ThreatSense is a cybersecurity analytics dashboard that uses machine learning to inspect network logs, classify attack types, score anomalies, and show the results in a web UI.

It has three parts:
- ML pipeline in `ml/` for training and storing the prediction artifacts
- Flask API in `backend/` for upload, inference, storage, and retrieval
- Next.js dashboard in `frontend/` for visualization and log browsing

## What It Does

ThreatSense lets you:
- Upload a CSV of NSL-KDD-style network features
- Run the trained model on each row
- Detect normal traffic, attack classes, and suspicious activity
- Store each prediction in a database table
- View summary statistics, recent logs, and per-row risk details in the dashboard

The backend exposes these endpoints:
- `GET /api/health` for service checks
- `POST /api/predict` for CSV upload and inference
- `GET /api/stats` for aggregate metrics
- `GET /api/logs` for stored predictions
- `DELETE /api/logs/:id` for removing a saved log entry

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd ThreatSense
```

### 2. Set up the backend environment

The project uses a local Python virtual environment at `.venv/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Copy the example environment file and use the local API port that works in this setup:

```bash
cp .env.example .env
```

Suggested values:

```env
DATABASE_URL=sqlite:///threatsense.db
MODEL_DIR=../ml/models
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:5001
```

If you want PostgreSQL in production, update `DATABASE_URL` accordingly.

### 3. Prepare the ML artifacts

The API expects trained model files in `ml/models/`:
- `trained_pipeline.joblib`
- `iforest.joblib`
- `preprocess_bundle.joblib`

If they are missing or outdated, retrain them from the notebook in `ml/notebooks/` and rerun the model verification script:

```bash
python backend/test_model.py
```

### 4. Start the backend API

```bash
cd backend
python -m flask --app app.main run --host 0.0.0.0 --port 5001
```

The backend should be reachable at:

```text
http://127.0.0.1:5001
```

### 5. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard should open at:

```text
http://127.0.0.1:3000
```

## Verification

Run the model and API checks after setup:

```bash
python backend/test_model.py
python backend/test_api.py
```

Then confirm:
- `GET /api/health` returns `{"status":"ok"}`
- CSV uploads succeed through the dashboard
- `GET /api/stats` and `GET /api/logs` return data
- predictions are stored in the database

## Project Structure

- `ml/` contains raw data, processed data, notebooks, reports, and saved models
- `backend/` contains the Flask app, database models, services, and API tests
- `frontend/` contains the Next.js app, styles, and API client
- `docs/` contains dataset, testing, and retraining notes

## Dataset

ThreatSense is built around the NSL-KDD dataset.

Recommended raw files:
- `ml/data/raw/KDDTrain+.txt`
- `ml/data/raw/KDDTest+.txt`

See [docs/dataset-guide.md](docs/dataset-guide.md) for the expected file layout and preprocessing flow.

## Notes

- Port `5001` is used here because `5000` is occupied on this machine.
- The frontend defaults to `http://127.0.0.1:5001` unless `NEXT_PUBLIC_API_BASE_URL` is set.
- If you change the backend port, update both `.env` and the frontend API base URL.
