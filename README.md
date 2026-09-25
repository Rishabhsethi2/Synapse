# Synapse

**Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains**

SIH26028 | Smart India Hackathon 2026

## What is Synapse?

Synapse is an ML-powered railway intelligence system that predicts train ETAs with uncertainty bounds, explains *why* delays happen using attribution analysis, and lets operators simulate "what-if" scenarios. It's built on **real Indian Railways data** (38.4 million delay observations across 8,700+ trains and 8,900+ stations).

### Key Capabilities

| Feature | Description |
|---|---|
| **ETA Prediction** | LightGBM models predict delay at every remaining station with 80% prediction intervals |
| **Replay Engine** | Step through any historical journey station-by-station, with predictions generated at each stop using only causally-available data (no future leakage) |
| **What-If Simulator** | Test counterfactual scenarios (e.g., "what if 30 minutes of additional delay?") |
| **Network Graph** | 8,964 station nodes, 31,514 section edges — computed from real timetable data |
| **Vulnerability Analysis** | Identifies high-traffic sections ranked by scheduled train count |
| **Attribution Engine** | Explains which features drive each prediction (SHAP-ready) |

### What Synapse Does NOT Do (by design)

- No autonomous train control
- No fabricated confidence percentages
- No LLM chatbot
- No opaque "AI scores" — every metric is derived from observable data

---

## Architecture

```
Frontend (Next.js 14)     Backend (FastAPI)          ML Pipeline
      |                         |                         |
  3 views:              API Layer:                 LightGBM Models:
  - Control Room        - /api/trains              - Point prediction
  - Network View        - /api/network             - Quantile (q10, q90)
  - Passenger           - /api/replay              - Trained on real data
                        - /api/whatif
                             |
                    Engine Layer:
                    - TrainStateEngine
                    - NetworkStateEngine
                    - HistoricalStateEngine
                    - FeatureEngine
                    - ReplayEngine
                    - SynapseForecaster
                    - AttributionEngine
                    - WhatIfEngine
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Dataset files in `data/raw/` (4 CSV files from Kaggle)

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend loads ~17 seconds on startup (parses schedules, builds network graph).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### ML Pipeline (Optional — pre-trained models included)

```bash
# Step 1: Process raw data into ML-ready parquet files
python ml/process_data.py

# Step 2: Train LightGBM models
python ml/train_model.py
```

### Docker

```bash
docker-compose up --build
```

Backend: http://localhost:8000 | Frontend: http://localhost:3000

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | System health + data counts |
| GET | `/api/trains` | List all trains (or active trains) |
| GET | `/api/trains/{id}/eta` | ETA predictions for all remaining stations |
| GET | `/api/trains/{id}/trajectory` | Full trajectory with distances and times |
| GET | `/api/network/stats` | Network graph statistics |
| GET | `/api/network/vulnerability` | High-risk section analysis |
| POST | `/api/replay/start` | Start historical journey replay |
| POST | `/api/replay/tick` | Advance replay by one station |
| POST | `/api/whatif` | Run counterfactual scenario |

---

## Dataset

| File | Rows | Description |
|---|---|---|
| `combined_delay.csv` | 38,428,703 | Per-station delay for every train on every date |
| `combined_schedule.csv` | 172,112 | Timetable: stops, times, distances |
| `station_full_names.csv` | 8,963 | Station metadata with zones |
| `train_details.csv` | 8,992 | Train names and type codes |

---

## ML Approach

**Model**: LightGBM gradient-boosted regression (per the PRD specification).

**Features** (4):
- `distance_from_origin_km` — how far along the route
- `previous_station_delay` — delay at the preceding station (causal)
- `day_of_week` — temporal pattern
- `scheduled_running_time` — scheduled time from origin

**Target**: `delay_minutes` at each station

**Temporal Split** (prevents leakage):
- Train: Feb 2025 – Oct 2025
- Validation: Nov – Dec 2025
- Test: Jan – Feb 2026

**Uncertainty**: Quantile regression models (alpha=0.10, 0.90) provide 80% prediction intervals.

---

## Project Structure

```
Synapse/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app with lifespan startup
│   │   ├── config.py            # Settings & feature flags
│   │   ├── dependencies.py      # Engine wiring
│   │   ├── models/domain.py     # 23 Pydantic v2 models
│   │   ├── data/
│   │   │   ├── loader.py        # CSV data loading
│   │   │   ├── processor.py     # Data transformation
│   │   │   └── database.py      # SQLite integration
│   │   ├── state/
│   │   │   ├── train_state.py   # Per-train state tracking
│   │   │   ├── network_state.py # NetworkX graph engine
│   │   │   └── historical_state.py
│   │   ├── features/
│   │   │   └── feature_engine.py
│   │   ├── forecast/
│   │   │   ├── model.py         # LightGBM forecaster
│   │   │   ├── baselines.py     # Baseline comparisons
│   │   │   └── uncertainty.py   # Quantile uncertainty
│   │   ├── intelligence/
│   │   │   ├── attribution.py   # SHAP-based attribution
│   │   │   ├── stability.py     # Prediction stability tracking
│   │   │   ├── section_risk.py  # Section risk scoring
│   │   │   ├── whatif.py        # What-if simulator
│   │   │   └── propagation.py   # Delay propagation estimator
│   │   ├── replay/
│   │   │   └── engine.py        # Temporal replay engine
│   │   └── api/
│   │       ├── routes_train.py
│   │       ├── routes_network.py
│   │       ├── routes_intelligence.py
│   │       └── routes_replay.py
│   └── requirements.txt
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx             # Control Room
│   │   ├── station/page.tsx     # Network View
│   │   └── passenger/page.tsx   # Passenger ETA + Replay
│   └── tailwind.config.ts
├── ml/
│   ├── process_data.py          # Raw CSV → parquet pipeline
│   └── train_model.py           # LightGBM training pipeline
├── data/
│   ├── raw/                     # CSV files (gitignored)
│   ├── processed/               # Parquet files
│   └── models/                  # Trained LightGBM models
├── tests/
│   └── test_api.py              # Integration tests
├── docker-compose.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

---

## Team

**Synapse** — Smart India Hackathon 2026
