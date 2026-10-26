from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from backend.db.database import get_db
from backend.services.risk_service import RiskService

router = APIRouter(prefix="/inventory", tags=["Inventory"])
risk_service = RiskService()

class AddStockRequest(BaseModel):
    restaurant_id: str
    ingredient_id: str
    qty_added: float
    min_days_to_expiry: Optional[float] = None
    notes: Optional[str] = "Delivery received"

class RecordWasteRequest(BaseModel):
    restaurant_id: str
    ingredient_id: str
    qty: float
    reason: str # 'expired', 'spoilage', 'over-prep'
    notes: Optional[str] = "Kitchen waste log"

@router.get("")
def get_inventory(
    restaurant_id: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """Retrieve current ingredient stock, expiry, days cover, risk level, and financial exposure"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*, i.storage_type, i.shelf_life_days, i.min_order_qty, i.supplier_name
            FROM inventory_stock s
            JOIN ingredients i ON s.ingredient_id = i.ingredient_id
            WHERE 1=1
        """
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND s.restaurant_id = ?"
            params.append(restaurant_id)
        if risk_level and risk_level != "all":
            query += " AND s.risk_level = ?"
            params.append(risk_level)
        if category and category != "all":
            query += " AND s.category = ?"
            params.append(category)
        if search:
            query += " AND (s.ingredient_name LIKE ? OR s.ingredient_id LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY s.financial_exposure_inr DESC, s.min_days_to_expiry ASC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    return {"count": len(rows), "items": rows}

@router.get("/risks")
def get_ingredient_risks(restaurant_id: Optional[str] = Query(None)):
    """Retrieve ranked ingredient waste-risk predictions"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM inventory_stock WHERE risk_level IN ('High', 'Medium')"
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        query += " ORDER BY financial_exposure_inr DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
    return {"at_risk_count": len(rows), "risks": rows}

@router.post("/stock")
def add_or_receive_stock(payload: AddStockRequest):
    """Add stock or receive delivery, updating inventory balance and recalculating risk"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM inventory_stock WHERE restaurant_id = ? AND ingredient_id = ?",
            (payload.restaurant_id, payload.ingredient_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ingredient stock record not found")

        new_stock = float(row["closing_stock_qty"]) + float(payload.qty_added)
        new_expiry = payload.min_days_to_expiry if payload.min_days_to_expiry is not None else float(row["min_days_to_expiry"])
        usage_mean = max(float(row["usage_7d_mean"]), 0.1)
        new_cover = round(new_stock / usage_mean, 2)

        cursor.execute(
            """UPDATE inventory_stock
               SET closing_stock_qty = ?, min_days_to_expiry = ?, cover_days = ?, updated_at = CURRENT_TIMESTAMP
               WHERE restaurant_id = ? AND ingredient_id = ?""",
            (round(new_stock, 3), new_expiry, new_cover, payload.restaurant_id, payload.ingredient_id)
        )

    # Re-evaluate risk for this item
    fresh_risk = risk_service.assess_ingredient_risk(payload.restaurant_id, payload.ingredient_id)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE inventory_stock
               SET risk_prob_next_3d = ?, risk_level = ?, surplus_qty_next_3d = ?,
                   expected_at_risk_qty = ?, financial_exposure_inr = ?, primary_driver = ?
               WHERE restaurant_id = ? AND ingredient_id = ?""",
            (fresh_risk["risk_prob_next_3d"], fresh_risk["risk_level"], fresh_risk["surplus_qty_next_3d"],
             fresh_risk["expected_at_risk_qty"], fresh_risk["financial_exposure_inr"], fresh_risk["primary_driver"],
             payload.restaurant_id, payload.ingredient_id)
        )

    return {"message": "Stock updated successfully", "updated": fresh_risk}

@router.post("/waste")
def record_waste_event(payload: RecordWasteRequest):
    """Log a waste event (spoilage, expired, overprep) and adjust closing stock"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM inventory_stock WHERE restaurant_id = ? AND ingredient_id = ?",
            (payload.restaurant_id, payload.ingredient_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ingredient not found in inventory")

        unit_cost = float(row["unit_cost_inr"])
        discard_cost = round(float(payload.qty) * unit_cost, 2)
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Deduct from stock
        new_stock = max(0.0, float(row["closing_stock_qty"]) - float(payload.qty))
        usage_mean = max(float(row["usage_7d_mean"]), 0.1)
        new_cover = round(new_stock / usage_mean, 2)

        cursor.execute(
            """UPDATE inventory_stock
               SET closing_stock_qty = ?, cover_days = ?, updated_at = CURRENT_TIMESTAMP
               WHERE restaurant_id = ? AND ingredient_id = ?""",
            (round(new_stock, 3), new_cover, payload.restaurant_id, payload.ingredient_id)
        )

        # Log waste event
        cursor.execute(
            """INSERT INTO waste_events
               (date, restaurant_id, ingredient_id, ingredient_name, qty, unit, reason, discard_cost_inr, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (today_str, payload.restaurant_id, payload.ingredient_id, row["ingredient_name"],
             float(payload.qty), row["unit"], payload.reason, discard_cost, payload.notes)
        )

    # Re-evaluate risk
    fresh_risk = risk_service.assess_ingredient_risk(payload.restaurant_id, payload.ingredient_id)
    return {
        "message": "Waste recorded successfully",
        "discard_cost_inr": discard_cost,
        "remaining_stock": new_stock,
        "risk": fresh_risk
    }
