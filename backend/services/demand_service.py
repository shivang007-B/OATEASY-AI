import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from backend.db.database import get_db
from backend.ml.model_loader import ModelLoader
from backend.ml.features import build_demand_features

class DemandService:
    def __init__(self):
        self.loader = ModelLoader.get_instance()

    def get_dish_recent_stats(self, dish_id: str, restaurant_id: str) -> Dict[str, float]:
        """Fetches historical lags and rolling means from sales_history"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT units_sold, selling_price_inr 
                   FROM sales_history 
                   WHERE dish_id = ? AND restaurant_id = ?
                   ORDER BY date DESC LIMIT 28""",
                (dish_id, restaurant_id)
            )
            rows = cursor.fetchall()
            
            if not rows:
                # Default baseline fallback from dish_master
                cursor.execute("SELECT base_daily_orders, list_price_inr FROM dishes WHERE dish_id = ?", (dish_id,))
                dish_row = cursor.fetchone()
                base = float(dish_row["base_daily_orders"]) if dish_row else 25.0
                price = float(dish_row["list_price_inr"]) if dish_row else 200.0
                return {
                    "selling_price_inr": price,
                    "lag_1": base,
                    "lag_7": base,
                    "lag_14": base,
                    "roll_mean_7": base,
                    "roll_mean_28": base
                }

            sales = [float(r["units_sold"]) for r in rows]
            latest_price = float(rows[0]["selling_price_inr"])
            lag_1 = sales[0] if len(sales) >= 1 else 25.0
            lag_7 = sales[6] if len(sales) >= 7 else lag_1
            lag_14 = sales[13] if len(sales) >= 14 else lag_7
            roll_7 = float(np.mean(sales[:min(7, len(sales))]))
            roll_28 = float(np.mean(sales))

            return {
                "selling_price_inr": latest_price,
                "lag_1": lag_1,
                "lag_7": lag_7,
                "lag_14": lag_14,
                "roll_mean_7": roll_7,
                "roll_mean_28": roll_28
            }

    def predict_dish(
        self,
        restaurant_id: str,
        dish_id: str,
        target_date: str,
        selling_price_inr: Optional[float] = None,
        promo_flag: int = 0,
        holiday_flag: int = 0,
        avg_temp_c: float = 24.0,
        rainfall_mm: float = 0.0
    ) -> Dict:
        """Run ML Model 1 (Poisson + q10 + q90) for a single dish"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT dish_name, category, list_price_inr FROM dishes WHERE dish_id = ?", (dish_id,))
            dish = cursor.fetchone()
            if not dish:
                raise ValueError(f"Dish {dish_id} not found")

        stats = self.get_dish_recent_stats(dish_id, restaurant_id)
        price = selling_price_inr if selling_price_inr is not None else stats["selling_price_inr"]

        feat_df = build_demand_features(
            restaurant_id=restaurant_id,
            dish_id=dish_id,
            category=dish["category"],
            target_date=target_date,
            selling_price_inr=price,
            promo_flag=promo_flag,
            holiday_flag=holiday_flag,
            avg_temp_c=avg_temp_c,
            rainfall_mm=rainfall_mm,
            lag_1=stats["lag_1"],
            lag_7=stats["lag_7"],
            lag_14=stats["lag_14"],
            roll_mean_7=stats["roll_mean_7"],
            roll_mean_28=stats["roll_mean_28"]
        )

        # Run predictions
        pred_median = float(self.loader.model1_mean.predict(feat_df)[0])
        pred_q10 = float(self.loader.model1_q10.predict(feat_df)[0])
        pred_q90 = float(self.loader.model1_q90.predict(feat_df)[0])

        # Enforce consistency: q10 <= median <= q90
        lower = max(1.0, round(min(pred_q10, pred_median), 1))
        upper = max(lower, round(max(pred_q90, pred_median), 1))
        median = round(pred_median, 1)

        spread = (upper - lower) / max(median, 1.0)
        confidence = "High" if spread < 0.65 else "Medium"

        return {
            "dish_id": dish_id,
            "dish_name": dish["dish_name"],
            "category": dish["category"],
            "target_date": target_date,
            "restaurant_id": restaurant_id,
            "selling_price_inr": price,
            "predicted_orders_median": median,
            "lower_80": lower,
            "upper_80": upper,
            "forecast_confidence": confidence
        }

    def generate_all_forecasts(self, target_date: str, restaurant_id: Optional[str] = None) -> List[Dict]:
        """Generates demand forecasts for all dishes across restaurants"""
        with get_db() as conn:
            cursor = conn.cursor()
            if restaurant_id:
                cursor.execute("SELECT restaurant_id FROM restaurants WHERE restaurant_id = ?", (restaurant_id,))
            else:
                cursor.execute("SELECT restaurant_id FROM restaurants")
            restaurants = [r["restaurant_id"] for r in cursor.fetchall()]

            cursor.execute("SELECT dish_id FROM dishes ORDER BY dish_id")
            dishes = [d["dish_id"] for d in cursor.fetchall()]

        results = []
        for rest in restaurants:
            for dish in dishes:
                res = self.predict_dish(rest, dish, target_date)
                results.append(res)
        return results
