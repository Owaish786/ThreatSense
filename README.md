# ThreatSense

ThreatSense is an AI + AWT cybersecurity dashboard project:
- AI track: ANN + Isolation Forest for intrusion and anomaly detection
- AWT track: Flask REST API + Next.js dashboard + PostgreSQL storage

## 1. Project goals
- Upload and analyze network logs
- Detect likely attack classes and anomalies
- Store predictions and serve dashboard metrics
- Visualize severity, distributions, and recent events

## 2. Quick start order
1. Prepare dataset and run EDA in `ml/`
2. Train ANN + Isolation Forest and save artifacts in `ml/models/`
3. Build Flask API in `backend/`
4. Build Next.js dashboard in `frontend/`
5. Connect end-to-end and validate with real CSV uploads

## 3. Folder map
See `docs/setup-plan.md` and `docs/dataset-guide.md` for the exact implementation steps.
