from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from backend.db.database import get_db

router = APIRouter(prefix="/actions", tags=["Actions"])

class UpdateActionStatusRequest(BaseModel):
    status: str # 'completed', 'dismissed', 'deferred', 'pending'

@router.get("")
def get_actions(
    restaurant_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    """Retrieve ranked operational actions"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM operational_actions WHERE 1=1"
        params = []
        if restaurant_id and restaurant_id != "all":
            query += " AND restaurant_id = ?"
            params.append(restaurant_id)
        if type and type != "all":
            t_lower = type.lower()
            if t_lower in ("purchase", "hold_purchase"):
                query += " AND type = 'hold_purchase'"
            elif t_lower in ("prep", "stage_preparation"):
                query += " AND type = 'stage_preparation'"
            elif t_lower in ("stock", "use_existing_stock"):
                query += " AND type = 'use_existing_stock'"
            elif t_lower in ("promo", "promotion", "promote_dish"):
                query += " AND type = 'promote_dish'"
            else:
                query += " AND LOWER(type) = ?"
                params.append(t_lower)
        if status and status != "all":
            s_lower = status.lower()
            if s_lower in ("approved", "completed"):
                query += " AND status = 'completed'"
            else:
                query += " AND LOWER(status) = ?"
                params.append(s_lower)

        query += " ORDER BY priority_score DESC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    completed_count = sum(1 for r in rows if r.get("status") == "completed")
    pending_count = sum(1 for r in rows if r.get("status") == "pending")
    saved_inr = sum(
        float(r.get("avoidable_cost_inr") or 0.0)
        for r in rows
        if r.get("status") == "completed" and r.get("type") != "stage_preparation"
    )

    return {
        "count": len(rows),
        "completed_count": completed_count,
        "pending_count": pending_count,
        "captured_savings_inr": round(saved_inr, 2),
        "actions": rows
    }

@router.patch("/{action_id}")
def update_action_status(action_id: int, payload: UpdateActionStatusRequest):
    """Update action state: completed, dismissed, deferred, pending"""
    if payload.status not in ("completed", "dismissed", "deferred", "pending"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE operational_actions
               SET status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (payload.status, action_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Action not found")

        cursor.execute("SELECT * FROM operational_actions WHERE id = ?", (action_id,))
        updated = dict(cursor.fetchone())

    return {"message": "Action updated", "action": updated}

@router.post("/reset")
def reset_all_actions():
    """Reset all actions back to pending state"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE operational_actions SET status = 'pending', updated_at = CURRENT_TIMESTAMP")
    return {"message": "All actions reset to pending"}
