# FreshFlow AI — Autonomous Restaurant Intelligence Platform

FreshFlow AI is an end-to-end operational intelligence layer for restaurants. Powered by Machine Learning, it predicts dish-level demand, models perishable inventory risk, and generates automated prep & purchasing plans to eliminate food waste and protect profit margins.

---

## 🌟 Key Features

- **Neural Demand Forecasting**: 7-day quantile demand forecasting (Q10, Q50, Q90) factoring in weekday trends, weather signals, seasonality, and local calendar events.
- **Perishable Inventory Risk Scoring**: Gradient Boosted Decision Trees analyzing batch expiry countdowns, storage conditions, and historical consumption velocity.
- **Autonomous Kitchen Operations**: Automated morning batch prep suggestions and supplier purchase order drafts with dynamic buffer recommendations.
- **Executive Operations Dashboard**: Clean, light minimal executive view with real-time KPI cards, hourly demand distributions, and perishable risk radar.
- **Interactive Operations Workspace**: Multi-tab interface for granular inventory stock control, demand forecasting breakdown, action approvals, and waste analytics.

---

## 🚀 Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open in Browser

- **Executive Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard) (or [http://localhost:8000](http://localhost:8000))
- **Deep Operations App**: [http://localhost:8000/app](http://localhost:8000/app)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📂 Project Structure

```
FreshFlowAI/
├── backend/
│   ├── api/routes/         # FastAPI endpoints (inventory, forecasts, actions, reports)
│   ├── db/                 # Database initialization & seed data
│   ├── ml/                 # Model loader & feature engineering
│   ├── services/           # Business logic & operational planners
│   └── main.py             # Server entry point & static file routing
├── FreshFlow_ML/
│   ├── data/               # Raw training datasets & master catalogues
│   ├── models/             # Trained ML models & configurations (.joblib)
│   ├── notebooks/          # Exploratory analysis & training pipelines
│   └── outputs/            # Generated forecasts & operational recommendations
├── static/
│   ├── app.js              # Operational app & executive dashboard interactivity
│   ├── dashboard.html      # Light minimal executive operations dashboard
│   ├── index.html          # Full operational intelligence workspace
│   └── styles.css          # Design system & tactile app styling
├── requirements.txt
└── README.md
```

---

## 📄 License

MIT License. Designed & developed with FreshFlow Intelligence.
