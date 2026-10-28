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
def serve_root():
    """Main application landing page with initial loading screen."""
    landing_file = os.path.join(STATIC_DIR, "landing.html")
    if os.path.exists(landing_file):
        return FileResponse(landing_file)
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "FreshFlow platform initialized."}

@app.get("/landing")
def serve_landing():
    """Landing page introducing application features."""
    landing_file = os.path.join(STATIC_DIR, "landing.html")
    if os.path.exists(landing_file):
        return FileResponse(landing_file)
    return serve_root()

@app.get("/describe")
def serve_describe():
    """Business selection screen: What best describes your business?"""
    describe_file = os.path.join(STATIC_DIR, "describe.html")
    if os.path.exists(describe_file):
        return FileResponse(describe_file)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/login")
def serve_login():
    """Login screen with demo credentials."""
    login_file = os.path.join(STATIC_DIR, "login.html")
    if os.path.exists(login_file):
        return FileResponse(login_file)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/app")
def serve_app():
    """Operational dashboard with simple top navbar and colorful collapsible sidebar."""
    app_file = os.path.join(STATIC_DIR, "app.html")
    if os.path.exists(app_file):
        return FileResponse(app_file)
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "FreshFlow app not found."}

@app.get("/dashboard")
def serve_dashboard():
    """Executive intelligence dashboard."""
    dashboard_file = os.path.join(STATIC_DIR, "dashboard.html")
    if os.path.exists(dashboard_file):
        return FileResponse(dashboard_file)
    return serve_root()

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "FreshFlow Intelligence", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
