from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from backend.db.database import get_db
from backend.services.demand_service import DemandService
from backend.services.risk_service import RiskService

router = APIRouter(prefix="", tags=["Forecasts & Planning"])
demand_service = DemandService()
risk_service = RiskService()

class DemandPredictRequest(BaseModel):
    restaurant_id: str = "R01"
    dish_id: str = "D01"
    target_date: str = "2026-01-01"
    selling_price_inr: Optional[float] = None
    promo_flag: int = 0
    holiday_flag: int = 0
    avg_temp_c: float = 24.0
    rainfall_mm: float = 0.0

class RiskPredictRequest(BaseModel):
    restaurant_id: str = "R01"
    ingredient_id: str = "I01"
    closing_stock_qty: Optional[float] = None
    min_days_to_expiry: Optional[float] = None

@router.get("/forecasts")
def get_forecasts(
    restaurant_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    """Retrieve dish demand forecasts with lower_80, median, upper_80, and confidence"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM forecast_results WHERE 1=1"
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        if category and category != "all":
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY predicted_orders_median DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    return {"count": len(rows), "forecasts": rows}

@router.get("/plans/prep")
def get_prep_plan(restaurant_id: Optional[str] = Query(None)):
    """Retrieve suggested preparation quantities and staged replenishment batches"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT restaurant_id, dish_id, dish_name, category, predicted_orders_median,
                   lower_80, upper_80, suggested_prep_qty, prep_stage_batch_qty,
                   cost_per_portion_inr, forecast_confidence
            FROM forecast_results WHERE 1=1
        """
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        query += " ORDER BY suggested_prep_qty DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    return {"count": len(rows), "prep_plan": rows}

@router.get("/plans/purchases")
def get_purchase_plan(restaurant_id: Optional[str] = Query(None)):
    """Retrieve recommended purchase quantities and financial values"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM purchase_plan WHERE 1=1"
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        query += " ORDER BY purchase_value_inr DESC, recommended_purchase_qty DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    total_value = sum(r["purchase_value_inr"] for r in rows)
    return {"total_value_inr": round(total_value, 2), "count": len(rows), "purchases": rows}

@router.post("/predict/demand")
def predict_demand_interactive(payload: DemandPredictRequest):
    """Interactive What-If Demand Prediction powered by Model 1 (Poisson + Quantiles)"""
    try:
        res = demand_service.predict_dish(
            restaurant_id=payload.restaurant_id,
            dish_id=payload.dish_id,
            target_date=payload.target_date,
            selling_price_inr=payload.selling_price_inr,
            promo_flag=payload.promo_flag,
            holiday_flag=payload.holiday_flag,
            avg_temp_c=payload.avg_temp_c,
            rainfall_mm=payload.rainfall_mm
        )
        # Add prep calculation
        res["suggested_prep_qty"] = int(round(res["predicted_orders_median"] * 1.10))
        res["prep_stage_batch_qty"] = int(round(res["lower_80"]))
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/predict/risk")
def predict_risk_interactive(payload: RiskPredictRequest):
    """Interactive What-If Risk Prediction powered by Model 2 (GBM Classifier)"""
    try:
        # If custom stock or expiry given, temporarily test or evaluate
        base = risk_service.assess_ingredient_risk(payload.restaurant_id, payload.ingredient_id)
        return base
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
