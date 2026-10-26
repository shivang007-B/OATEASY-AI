import math
from typing import Dict, List, Tuple
from backend.db.database import get_db

FEASIBILITY = {
    "hold_purchase": 1.0,
    "use_existing_stock": 0.9,
    "stage_preparation": 0.7,
    "promote_dish": 0.6
}

class PlanningService:
    def calculate_prep_plan(self, forecast_list: List[Dict]) -> List[Dict]:
        """Calculates suggested prep quantities and portion costs"""
        with get_db() as conn:
            cursor = conn.cursor()
            # Fetch portion costs for each dish
            cursor.execute("""
                SELECT r.dish_id, 
                       SUM((r.qty_per_portion / (1.0 - (r.prep_yield_loss_pct / 100.0))) * i.unit_cost_inr) as cost_per_portion
                FROM recipes r
                JOIN ingredients i ON r.ingredient_id = i.ingredient_id
                GROUP BY r.dish_id
            """)
            portion_costs = {row["dish_id"]: float(row["cost_per_portion"] or 30.0) for row in cursor.fetchall()}

        prep_rows = []
        for fc in forecast_list:
            median = fc["predicted_orders_median"]
            lower = fc["lower_80"]
            upper = fc["upper_80"]
            suggested_prep = int(round(median * 1.10)) # 10% safety buffer
            stage_batch = int(round(lower))
            portion_cost = portion_costs.get(fc["dish_id"], 35.0)

            prep_rows.append({
                "restaurant_id": fc["restaurant_id"],
                "dish_id": fc["dish_id"],
                "dish_name": fc["dish_name"],
                "category": fc.get("category", "Main Course"),
                "predicted_orders_median": median,
                "lower_80": lower,
                "upper_80": upper,
                "forecast_confidence": fc.get("forecast_confidence", "High"),
                "suggested_prep_qty": suggested_prep,
                "prep_stage_batch_qty": stage_batch,
                "cost_per_portion_inr": round(portion_cost, 2)
            })
        return prep_rows

    def calculate_purchase_plan(
        self,
        forecast_list: List[Dict],
        risk_list: List[Dict]
    ) -> Tuple[List[Dict], float, float]:
        """Calculates requirement and purchase plan by joining dish forecasts with recipes"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dish_id, ingredient_id, qty_per_portion, prep_yield_loss_pct, unit 
                FROM recipes
            """)
            recipe_rows = cursor.fetchall()
            cursor.execute("SELECT ingredient_id, min_order_qty, unit_cost_inr FROM ingredients")
            ing_master = {r["ingredient_id"]: r for r in cursor.fetchall()}

        # Map recipe requirements by (dish_id)
        dish_recipes = {}
        for r in recipe_rows:
            dish_recipes.setdefault(r["dish_id"], []).append(r)

        # Risk map by (restaurant_id, ingredient_id)
        risk_map = {(r["restaurant_id"], r["ingredient_id"]): r for r in risk_list}

        # Calculate gross requirements per (restaurant_id, ingredient_id)
        req_by_ing = {}
        for fc in forecast_list:
            rest_id = fc["restaurant_id"]
            dish_id = fc["dish_id"]
            orders = fc["predicted_orders_median"]

            for rec in dish_recipes.get(dish_id, []):
                ing_id = rec["ingredient_id"]
                yield_loss = rec["prep_yield_loss_pct"] / 100.0
                effective_portion = rec["qty_per_portion"] / max(1.0 - yield_loss, 0.01)
                needed = orders * effective_portion
                key = (rest_id, ing_id)
                req_by_ing[key] = req_by_ing.get(key, 0.0) + needed

        purchase_rows = []
        total_purchase_val = 0.0
        total_adjustment_qty = 0.0

        for (rest_id, ing_id), rk in risk_map.items():
            req_qty = round(req_by_ing.get((rest_id, ing_id), 0.0), 3)
            closing_stock = rk["closing_stock_qty"]
            min_exp = rk["min_days_to_expiry"]
            usable_stock = closing_stock if min_exp >= 1.0 else 0.0
            incoming = 0.0 # From pending deliveries

            ing_info = ing_master.get(ing_id)
            min_order = float(ing_info["min_order_qty"]) if ing_info else 1.0
            unit_cost = float(ing_info["unit_cost_inr"]) if ing_info else float(rk["unit_cost_inr"])

            net_shortfall = max(0.0, req_qty - usable_stock - incoming)
            if net_shortfall > 0:
                recommended_qty = math.ceil(net_shortfall / min_order) * min_order
            else:
                recommended_qty = 0.0

            purchase_val = round(recommended_qty * unit_cost, 2)
            total_purchase_val += purchase_val

            # Adjustment qty = surplus stock that prevents ordering
            adj_qty = max(0.0, round(usable_stock - req_qty, 2))
            total_adjustment_qty += adj_qty

            purchase_rows.append({
                "restaurant_id": rest_id,
                "ingredient_id": ing_id,
                "ingredient_name": rk["ingredient_name"],
                "unit": rk["unit"],
                "required_qty": req_qty,
                "usable_stock_qty": usable_stock,
                "incoming_qty": incoming,
                "recommended_purchase_qty": recommended_qty,
                "purchase_value_inr": purchase_val,
                "purchase_adjustment_qty": adj_qty
            })

        return purchase_rows, round(total_purchase_val, 2), round(total_adjustment_qty, 2)

    def generate_ranked_actions(
        self,
        risk_list: List[Dict],
        prep_list: List[Dict],
        purchase_list: List[Dict]
    ) -> List[Dict]:
        """Generates ranked operational actions sorted by priority score = avoidable cost * feasibility"""
        actions = []

        # 1. Use existing stock first (High & Medium risk ingredients)
        for rk in risk_list:
            if rk["risk_level"] in ("High", "Medium") and rk["closing_stock_qty"] > 0:
                avoidable = float(rk["financial_exposure_inr"])
                feasibility = FEASIBILITY["use_existing_stock"]
                score = round(avoidable * feasibility, 2)
                why = f"{rk['risk_level']} risk ({rk['primary_driver']}); min days to expiry {int(rk['min_days_to_expiry'])}"
                
                actions.append({
                    "restaurant_id": rk["restaurant_id"],
                    "action": f"Use existing {rk['ingredient_name']} first",
                    "type": "use_existing_stock",
                    "item": rk["ingredient_name"],
                    "avoidable_cost_inr": avoidable,
                    "feasibility": feasibility,
                    "why": why,
                    "priority_score": score,
                    "status": "pending"
                })

        # 2. Hold purchase when stock already covers requirement
        for p in purchase_list:
            if p["usable_stock_qty"] >= p["required_qty"] and p["usable_stock_qty"] > 0 and p["required_qty"] > 0:
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute("SELECT unit_cost_inr FROM ingredients WHERE ingredient_name = ?", (p["ingredient_name"],))
                    row = c.fetchone()
                    uc = float(row["unit_cost_inr"]) if row else 50.0

                avoidable = round(p["required_qty"] * uc, 2)
                if avoidable > 200:
                    feasibility = FEASIBILITY["hold_purchase"]
                    score = round(avoidable * feasibility, 2)
                    actions.append({
                        "restaurant_id": p["restaurant_id"],
                        "action": f"Hold purchase of {p['ingredient_name']}",
                        "type": "hold_purchase",
                        "item": p["ingredient_name"],
                        "avoidable_cost_inr": avoidable,
                        "feasibility": feasibility,
                        "why": "Usable stock and incoming deliveries already cover tomorrow's requirement",
                        "priority_score": score,
                        "status": "pending"
                    })

        # 3. Stage food preparation (Cook lower_80 now, replenish diff in batches)
        for prep in prep_list:
            diff = prep["suggested_prep_qty"] - prep["prep_stage_batch_qty"]
            if diff >= 10:
                cost_portion = prep["cost_per_portion_inr"]
                avoidable = round(diff * cost_portion * 0.35, 2) # over-prep prevention value
                feasibility = FEASIBILITY["stage_preparation"]
                score = round(avoidable * feasibility, 2)
                why = f"Cook {prep['prep_stage_batch_qty']} now, replenish the other {diff} in batches (forecast {int(prep['lower_80'])}-{int(prep['upper_80'])})"
                
                actions.append({
                    "restaurant_id": prep["restaurant_id"],
                    "action": f"Stage preparation of {prep['dish_name']}",
                    "type": "stage_preparation",
                    "item": prep["dish_name"],
                    "avoidable_cost_inr": avoidable,
                    "feasibility": feasibility,
                    "why": why,
                    "priority_score": score,
                    "status": "pending"
                })

        # Sort all actions descending by priority score
        actions.sort(key=lambda a: a["priority_score"], reverse=True)
        return actions
