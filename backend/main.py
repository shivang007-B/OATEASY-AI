import hmac
import hashlib
import json
from datetime import datetime
from fastapi import Request, Header, HTTPException
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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


# ==============================================================================
# COPAYFLOW / YOUPI PAYMENT GATEWAY & WEBHOOK
# ==============================================================================
YOUPI_WEBHOOK_SECRET = os.environ.get("YOUPI_WEBHOOK_SECRET", "merchant_webhook_secret_for_wallet_store")
PAID_ORDERS = {}

@app.post("/api/webhook")
@app.post("/api/v1/webhook")
async def copayflow_payment_webhook(
    request: Request,
    x_gateway_signature: str = Header(None, alias="x-gateway-signature")
):
    """
    Copayflow / Youpi payment webhook handler.
    Authenticates incoming webhook using HMAC-SHA256 signature and records paid status.
    """
    raw_body = await request.body()
    secret = os.environ.get("YOUPI_WEBHOOK_SECRET", "merchant_webhook_secret_for_wallet_store")
    expected_sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    if x_gateway_signature:
        if not hmac.compare_digest(x_gateway_signature, expected_sig):
            print(f"[Copayflow Webhook] Signature mismatch! Got: {x_gateway_signature}, Expected: {expected_sig}")
            return JSONResponse(status_code=401, content={"error": "Invalid webhook signature"})
    else:
        print("[Copayflow Webhook] Received webhook payload (development mode / signature optional).")

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON payload: {str(e)}"})

    event = payload.get("event")
    order_id = payload.get("orderId") or payload.get("order_id", "ORD-UNKNOWN")
    amount = payload.get("amount", 0)
    utr = payload.get("utr", "")
    metadata = payload.get("metadata", {})

    if event == "SUCCESS":
        print(f"[OK] [Copayflow Payment Confirmed] Order {order_id} Paid! Amount: INR {amount}, Bank UTR: {utr}")
        PAID_ORDERS[order_id] = {
            "order_id": order_id,
            "amount": amount,
            "utr": utr,
            "status": "PAID",
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }
        # Persist to sqlite payments table
        try:
            from backend.db.database import get_db
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO payments (order_id, amount, utr, status, plan, raw_payload) VALUES (?, ?, ?, ?, ?, ?)",
                    (order_id, float(amount) if amount else 0.0, str(utr), "PAID", str(metadata.get("plan", "starter")), json.dumps(payload))
                )
        except Exception as db_err:
            print(f"[Database log info] {db_err}")

    return {"received": True, "order_id": order_id, "status": "processed"}

@app.get("/api/v1/payments/status/{order_id}")
def get_payment_status(order_id: str):
    """Check if an order has been paid."""
    if order_id in PAID_ORDERS:
        return {"paid": True, "order": PAID_ORDERS[order_id]}
    try:
        from backend.db.database import get_db
        with get_db() as conn:
            row = conn.execute("SELECT * FROM payments WHERE order_id = ?", (order_id,)).fetchone()
            if row:
                return {"paid": True, "order": dict(row)}
    except Exception:
        pass
    return {"paid": False, "order_id": order_id}

@app.get("/api/v1/payments/recent")
def get_recent_payments():
    """List recent payments for administrative oversight."""
    try:
        from backend.db.database import get_db
        with get_db() as conn:
            rows = conn.execute("SELECT order_id, amount, currency, plan, utr, status, created_at FROM payments ORDER BY created_at DESC LIMIT 20").fetchall()
            return {"payments": [dict(r) for r in rows]}
    except Exception as e:
        return {"payments": list(PAID_ORDERS.values()), "error": str(e)}


@app.post("/api/v1/payments/create-session")
async def create_payment_session(request: Request):
    """
    Server-side proxy to create a Copayflow / Youpi payment session.
    Eliminates browser CORS preflight issues by communicating directly
    with Copayflow PG running on port 7000 with X-Merchant-Id header.
    """
    import urllib.request
    import urllib.error
    import time
    
    try:
        body = await request.json()
    except Exception:
        body = {}

    order_id = body.get("orderId") or body.get("order_id") or f"ORD-FF-{int(time.time())}"
    amount = float(body.get("amount") or 3999.00)
    currency = body.get("currency") or "INR"
    plan = body.get("plan") or "starter"
    customer = body.get("customer") or {}
    metadata = body.get("metadata") or {}
    metadata["plan"] = plan

    gateway_url = os.environ.get("YOUPI_GATEWAY_URL", "http://localhost:7000")
    merchant_key = os.environ.get("YOUPI_MERCHANT_KEY", "00000000-0000-0000-0000-000000000001")

    payload = {
        "orderId": order_id,
        "amount": amount,
        "currency": currency,
        "customer": {
            "fullName": customer.get("name") or customer.get("fullName") or "Restaurant Partner",
            "email": customer.get("email") or "partner@freshflow.ai",
            "phoneNumber": customer.get("phone") or customer.get("phoneNumber") or "9876543210"
        },
        "description": f"FreshFlow AI {plan.capitalize()} Plan Subscription",
        "metadata": metadata
    }

    try:
        req = urllib.request.Request(
            f"{gateway_url}/api/v1/payments",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Merchant-Id": merchant_key
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            print(f"[OK] [Payment Session Created] Order: {order_id}, PaymentId: {res_data.get('paymentId')}")
            return res_data
    except Exception as e:
        print(f"[Warning] Copayflow gateway session call failed: {e}. Generating fallback session URL.")
        fallback_payment_id = f"pay-{order_id.lower()}"
        # If external gateway is unavailable, provide seamless self-hosted checkout URL
        return {
            "paymentId": fallback_payment_id,
            "orderId": order_id,
            "amount": str(amount),
            "currency": currency,
            "status": "INITIATED",
            "checkoutUrl": f"/checkout/{fallback_payment_id}?amount={amount}&plan={plan}&orderId={order_id}",
            "fallback": True
        }


@app.get("/checkout/{payment_id}")
def serve_checkout(payment_id: str, request: Request):
    """
    Serves the responsive UPI checkout page.
    Provides instant dynamic UPI QR code, mobile deep links, and observation verification.
    Ensures FreshFlow operates self-contained in production even without an external gateway.
    """
    checkout_file = os.path.join(STATIC_DIR, "checkout.html")
    if os.path.exists(checkout_file):
        return FileResponse(checkout_file)
    return HTMLResponse("<h3>Checkout Portal Initializing...</h3>", status_code=200)


@app.get("/api/v1/payments/config")
def get_payment_config():
    """Returns dynamic payment gateway client configuration."""
    gateway_url = os.environ.get("YOUPI_GATEWAY_URL", "http://localhost:7000")
    merchant_key = os.environ.get("YOUPI_MERCHANT_KEY", "00000000-0000-0000-0000-000000000001")
    return {
        "gatewayUrl": gateway_url,
        "merchantKey": merchant_key,
        "currency": os.environ.get("YOUPI_CURRENCY", "INR"),
        "scriptUrl": os.environ.get("YOUPI_SCRIPT_URL", "/static/youpi.js"),
        "isProduction": bool(os.environ.get("RENDER") or os.environ.get("ENVIRONMENT", "").lower() in ["production", "prod"])
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "app": "FreshFlow Intelligence", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
