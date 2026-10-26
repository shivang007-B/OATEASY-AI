import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.db.seed_data import seed_database
from backend.api.routes import reports, inventory, forecasts, actions, analytics, restaurants

# Auto-seed database on first startup if needed
seed_database(force=False)

app = FastAPI(
    title="FreshFlow Restaurant Intelligence API",
    description="Operational restaurant intelligence platform powered by Machine Learning demand forecasting, ingredient waste risk prediction, and automated prep & purchasing planning.",
    version="1.0.0"
)

# Enable CORS for local and web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(reports.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(forecasts.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(restaurants.router, prefix="/api/v1")

# Static files setup
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
@app.get("/dashboard")
def serve_dashboard():
    """Minimal executive intelligence dashboard."""
    dashboard_file = os.path.join(STATIC_DIR, "dashboard.html")
    if os.path.exists(dashboard_file):
        return FileResponse(dashboard_file)
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "FreshFlow API running."}

@app.get("/app")
def serve_app():
    """Operational dashboard (stock, forecast, actions, analytics)."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "FreshFlow app not found."}

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "FreshFlow Intelligence", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
