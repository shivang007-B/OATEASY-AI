import os
import json
from fastapi import APIRouter, Query
from typing import Optional
from backend.db.database import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])

BASE_ML_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "OatEasy_ML")
OUTPUTS_DIR = os.path.join(BASE_ML_DIR, "outputs")

@router.get("/waste-by-reason")
def get_waste_by_reason(restaurant_id: Optional[str] = Query(None)):
    """Waste breakdown by reason: expired, spoilage, over-prep"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT reason, 
                   COUNT(*) as event_count, 
                   SUM(qty) as total_qty, 
                   SUM(discard_cost_inr) as total_cost_inr
            FROM waste_events
            WHERE 1=1
        """
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        query += " GROUP BY reason ORDER BY total_cost_inr DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    total_cost = sum(r["total_cost_inr"] for r in rows)
    for r in rows:
        r["pct_of_total"] = round((r["total_cost_inr"] / total_cost * 100), 1) if total_cost > 0 else 0.0
        r["total_cost_inr"] = round(r["total_cost_inr"], 2)
        r["total_qty"] = round(r["total_qty"], 2)

    return {"total_waste_cost_inr": round(total_cost, 2), "breakdown": rows}

@router.get("/waste-by-ingredient")
def get_waste_by_ingredient(restaurant_id: Optional[str] = Query(None), limit: int = 10):
    """Top wasted ingredients by cost and quantity"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT ingredient_name, unit,
                   SUM(qty) as total_qty, 
                   SUM(discard_cost_inr) as total_cost_inr
            FROM waste_events
            WHERE 1=1
        """
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        query += " GROUP BY ingredient_name ORDER BY total_cost_inr DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    for r in rows:
        r["total_cost_inr"] = round(r["total_cost_inr"], 2)
        r["total_qty"] = round(r["total_qty"], 2)

    return {"items": rows}

@router.get("/historical-demand")
def get_historical_demand_trend(restaurant_id: Optional[str] = Query(None), days: int = 30):
    """Daily total orders history across recent days"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT date, SUM(units_sold) as total_units, AVG(avg_temp_c) as avg_temp
            FROM sales_history
            WHERE 1=1
        """
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        query += " GROUP BY date ORDER BY date DESC LIMIT ?"
        params.append(days)
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    rows.reverse()
    return {"history": rows}

@router.get("/model-metrics")
def get_model_metrics():
    """Returns official evaluated test-set metrics for Model 1 and Model 2"""
    m1_metrics = {}
    m2_metrics = {}
    try:
        with open(os.path.join(OUTPUTS_DIR, "metrics_model1.json"), "r") as f:
            m1_metrics = json.load(f)
        with open(os.path.join(OUTPUTS_DIR, "metrics_model2.json"), "r") as f:
            m2_metrics = json.load(f)
    except Exception as e:
        print(f"Error reading metrics files: {e}")

    return {
        "model1_demand": {
            "name": "Gradient Boosting (Poisson Loss)",
            "test_wape": "17.6%",
            "test_mae": 4.901,
            "test_rmse": 6.517,
            "prediction_interval_coverage_80": "74.4%",
            "comparison": {
                "seasonal_naive_wape": "25.4%",
                "moving_avg_28_wape": "20.4%"
            },
            "raw": m1_metrics
        },
        "model2_ingredient_risk": {
            "name": "Gradient Boosting Classifier (GBM)",
            "roc_auc": 0.9133,
            "pr_auc": 0.8506,
            "brier_score": 0.101,
            "best_f1_threshold": 0.2112,
            "comparison": {
                "rule_days_to_expiry_roc_auc": 0.8777,
                "rule_stock_cover_roc_auc": 0.2432
            },
            "raw": m2_metrics
        },
        "engine3_recipes": {
            "prep_yield_loss_error": "0.1%",
            "without_yield_loss_error": "5.8%"
        }
    }
