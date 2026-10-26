import numpy as np
from typing import Dict, List, Optional
from backend.db.database import get_db
from backend.ml.model_loader import ModelLoader
from backend.ml.features import build_risk_features

class RiskService:
    def __init__(self):
        self.loader = ModelLoader.get_instance()

    def assess_ingredient_risk(
        self,
        restaurant_id: str,
        ingredient_id: str,
        target_date: Optional[str] = None
    ) -> Dict:
        """Runs Model 2 waste-risk prediction for an ingredient in a restaurant"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT s.*, i.storage_type, i.perishable_flag, i.shelf_life_days, 
                          i.target_cover_days, i.supplier_lead_time_days
                   FROM inventory_stock s
                   JOIN ingredients i ON s.ingredient_id = i.ingredient_id
                   WHERE s.restaurant_id = ? AND s.ingredient_id = ?""",
                (restaurant_id, ingredient_id)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Inventory record for {ingredient_id} in {restaurant_id} not found")

        feat_df = build_risk_features(
            restaurant_id=restaurant_id,
            ingredient_id=ingredient_id,
            category=row["category"],
            storage_type=row["storage_type"],
            perishable_flag=row["perishable_flag"],
            shelf_life_days=row["shelf_life_days"],
            closing_stock_qty=row["closing_stock_qty"],
            batches_on_hand=row["batches_on_hand"],
            min_days_to_expiry=row["min_days_to_expiry"],
            weighted_remaining_shelf_life_days=max(row["min_days_to_expiry"] + 0.5, 0.5),
            days_since_last_delivery=1,
            pending_order_qty=0.0,
            usage_1d=row["usage_1d"],
            usage_7d_mean=row["usage_7d_mean"],
            cover_days=row["cover_days"],
            target_cover_days=row["target_cover_days"],
            target_date=target_date
        )

        prob = float(self.loader.model2_risk.predict_proba(feat_df)[0][1])
        prob = round(prob, 4)

        # Thresholds based on Model 2 configuration
        if prob >= 0.50:
            risk_level = "High"
        elif prob >= 0.2112:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Determine primary driver
        if row["min_days_to_expiry"] <= 2.0:
            primary_driver = "Expiry"
        else:
            primary_driver = "Usage pattern"

        closing_stock = float(row["closing_stock_qty"])
        usage_mean = max(float(row["usage_7d_mean"]), 0.1)
        min_expiry = float(row["min_days_to_expiry"])
        unit_cost = float(row["unit_cost_inr"])

        # Surplus qty over 3-day demand
        demand_3d = usage_mean * 3.0
        surplus = max(0.0, round(closing_stock - demand_3d, 3))

        # Expected at-risk quantity
        if primary_driver == "Expiry":
            at_risk_qty = round(closing_stock * min(1.0, prob * 1.2), 3)
        else:
            at_risk_qty = round(closing_stock * prob, 3)

        financial_exposure = round(at_risk_qty * unit_cost, 2)

        return {
            "restaurant_id": restaurant_id,
            "ingredient_id": ingredient_id,
            "ingredient_name": row["ingredient_name"],
            "category": row["category"],
            "unit": row["unit"],
            "unit_cost_inr": unit_cost,
            "closing_stock_qty": closing_stock,
            "min_days_to_expiry": min_expiry,
            "usage_7d_mean": round(usage_mean, 2),
            "cover_days": round(row["cover_days"], 2),
            "risk_prob_next_3d": prob,
            "risk_level": risk_level,
            "surplus_qty_next_3d": surplus,
            "expected_at_risk_qty": at_risk_qty,
            "financial_exposure_inr": financial_exposure,
            "primary_driver": primary_driver
        }

    def assess_all_stock(self, restaurant_id: Optional[str] = None, target_date: Optional[str] = None) -> List[Dict]:
        """Assesses all ingredients across restaurants"""
        with get_db() as conn:
            cursor = conn.cursor()
            if restaurant_id:
                cursor.execute(
                    "SELECT restaurant_id, ingredient_id FROM inventory_stock WHERE restaurant_id = ? ORDER BY ingredient_id",
                    (restaurant_id,)
                )
            else:
                cursor.execute("SELECT restaurant_id, ingredient_id FROM inventory_stock ORDER BY restaurant_id, ingredient_id")
            items = cursor.fetchall()

        results = []
        for item in items:
            res = self.assess_ingredient_risk(item["restaurant_id"], item["ingredient_id"], target_date)
            results.append(res)
        return results
