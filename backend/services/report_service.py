import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
from backend.db.database import get_db
from backend.services.demand_service import DemandService
from backend.services.risk_service import RiskService
from backend.services.planning_service import PlanningService

class ReportService:
    def __init__(self):
        self.demand_service = DemandService()
        self.risk_service = RiskService()
        self.planning_service = PlanningService()

    def get_latest_report(self, restaurant_id: Optional[str] = None) -> Dict:
        """Retrieves the latest daily intelligence report and headline KPIs"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_reports ORDER BY id DESC LIMIT 1")
            rep_row = cursor.fetchone()
            if not rep_row:
                # Fallback to generating one
                return self.generate_daily_report()

            # Filter stats if restaurant_id is specified
            if restaurant_id and restaurant_id != "all":
                cursor.execute("""
                    SELECT SUM(predicted_orders_median) as total_orders
                    FROM forecast_results WHERE restaurant_id = ?
                """, (restaurant_id,))
                orders_sum = cursor.fetchone()["total_orders"] or 0

                cursor.execute("""
                    SELECT COUNT(*) as risk_count, SUM(financial_exposure_inr) as exp_sum
                    FROM inventory_stock 
                    WHERE restaurant_id = ? AND risk_level IN ('High', 'Medium')
                """, (restaurant_id,))
                r_stat = cursor.fetchone()
                risk_count = r_stat["risk_count"] or 0

                cursor.execute("""
                    SELECT SUM(purchase_value_inr) as p_val, SUM(purchase_adjustment_qty) as p_adj
                    FROM purchase_plan WHERE restaurant_id = ?
                """, (restaurant_id,))
                p_stat = cursor.fetchone()
                p_val = p_stat["p_val"] or 0.0
                p_adj = p_stat["p_adj"] or 0.0

                cursor.execute("""
                    SELECT SUM(priority_score) as avoidable_sum
                    FROM operational_actions 
                    WHERE restaurant_id = ? AND type != 'stage_preparation'
                """, (restaurant_id,))
                avoidable_sum = cursor.fetchone()["avoidable_sum"] or 0.0

                cursor.execute("""
                    SELECT action, avoidable_cost_inr, why 
                    FROM operational_actions 
                    WHERE restaurant_id = ? AND status = 'pending'
                    ORDER BY priority_score DESC LIMIT 1
                """, (restaurant_id,))
                top_action_row = cursor.fetchone()
            else:
                orders_sum = rep_row["predicted_orders_total"]
                risk_count = rep_row["ingredients_at_risk"]
                p_val = rep_row["recommended_purchase_value_inr"]
                p_adj = rep_row["purchase_adjustment_qty"]
                avoidable_sum = rep_row["potential_waste_avoided_inr_estimated"]

                cursor.execute("""
                    SELECT action, avoidable_cost_inr, why 
                    FROM operational_actions 
                    WHERE status = 'pending'
                    ORDER BY priority_score DESC LIMIT 1
                """)
                top_action_row = cursor.fetchone()

        top_priority = {
            "title": top_action_row["action"] if top_action_row else "Maintain standard operational prep",
            "why": top_action_row["why"] if top_action_row else "Stock levels are healthy across chillers.",
            "avoidable_cost_inr": float(top_action_row["avoidable_cost_inr"]) if top_action_row else 0.0
        }

        return {
            "as_of": rep_row["as_of_date"],
            "planning_date": rep_row["planning_date"],
            "predicted_orders_total": int(round(orders_sum)),
            "ingredients_at_risk": int(risk_count),
            "purchase_adjustment_qty": round(float(p_adj), 2),
            "recommended_purchase_value_inr": round(float(p_val), 2),
            "potential_waste_avoided_inr_estimated": round(float(avoidable_sum), 2),
            "note": rep_row["note"],
            "top_priority": top_priority,
            "status": "Generated & Active",
            "generation_time": rep_row["created_at"]
        }

    def generate_daily_report(self, planning_date: Optional[str] = None) -> Dict:
        """Runs the entire pipeline (Model 1 + Model 2 + Planning) and commits to SQLite"""
        now = datetime.now()
        if not planning_date:
            planning_date = "2026-01-01"
            as_of_date = "2025-12-31"
        else:
            dt = datetime.strptime(planning_date, "%Y-%m-%d")
            as_of_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"[ReportService] Generating report for {planning_date} (as of {as_of_date})...")

        # 1. Run Demand Predictions (Model 1)
        forecasts = self.demand_service.generate_all_forecasts(target_date=planning_date)

        # 2. Run Ingredient Risk Assessments (Model 2)
        risks = self.risk_service.assess_all_stock(target_date=as_of_date)

        # 3. Calculate Prep Plan
        prep_plan = self.planning_service.calculate_prep_plan(forecasts)

        # 4. Calculate Purchase Plan
        purchase_plan, total_p_val, total_adj_qty = self.planning_service.calculate_purchase_plan(forecasts, risks)

        # 5. Generate Ranked Actions
        actions = self.planning_service.generate_ranked_actions(risks, prep_plan, purchase_plan)

        # Calculate totals
        total_orders = sum(f["predicted_orders_median"] for f in forecasts)
        at_risk_count = sum(1 for r in risks if r["risk_level"] in ("High", "Medium"))
        potential_waste_avoided = sum(a["priority_score"] for a in actions if a["type"] != "stage_preparation")

        # Save to database
        with get_db() as conn:
            cursor = conn.cursor()

            # Update inventory_stock with latest risk numbers
            for rk in risks:
                cursor.execute("""
                    UPDATE inventory_stock
                    SET risk_prob_next_3d = ?, risk_level = ?, surplus_qty_next_3d = ?,
                        expected_at_risk_qty = ?, financial_exposure_inr = ?, primary_driver = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE restaurant_id = ? AND ingredient_id = ?
                """, (rk["risk_prob_next_3d"], rk["risk_level"], rk["surplus_qty_next_3d"],
                      rk["expected_at_risk_qty"], rk["financial_exposure_inr"], rk["primary_driver"],
                      rk["restaurant_id"], rk["ingredient_id"]))

            # Update forecast_results
            cursor.execute("DELETE FROM forecast_results")
            prep_map = {(p["restaurant_id"], p["dish_id"]): p for p in prep_plan}
            for fc in forecasts:
                p_item = prep_map.get((fc["restaurant_id"], fc["dish_id"]), {})
                cursor.execute("""
                    INSERT INTO forecast_results
                    (forecast_date, restaurant_id, dish_id, dish_name, category,
                     predicted_orders_median, lower_80, upper_80, forecast_confidence,
                     suggested_prep_qty, prep_stage_batch_qty, cost_per_portion_inr)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (planning_date, fc["restaurant_id"], fc["dish_id"], fc["dish_name"],
                      fc["category"], fc["predicted_orders_median"], fc["lower_80"], fc["upper_80"],
                      fc["forecast_confidence"], p_item.get("suggested_prep_qty", int(fc["predicted_orders_median"])),
                      p_item.get("prep_stage_batch_qty", int(fc["lower_80"])),
                      p_item.get("cost_per_portion_inr", 35.0)))

            # Update purchase_plan
            cursor.execute("DELETE FROM purchase_plan")
            for p in purchase_plan:
                cursor.execute("""
                    INSERT INTO purchase_plan
                    (restaurant_id, ingredient_name, unit, required_qty, usable_stock_qty,
                     incoming_qty, recommended_purchase_qty, purchase_value_inr, purchase_adjustment_qty)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (p["restaurant_id"], p["ingredient_name"], p["unit"], p["required_qty"],
                      p["usable_stock_qty"], p["incoming_qty"], p["recommended_purchase_qty"],
                      p["purchase_value_inr"], p["purchase_adjustment_qty"]))

            # Update operational_actions (preserve completed statuses if any)
            cursor.execute("SELECT action, restaurant_id, status FROM operational_actions WHERE status != 'pending'")
            completed_actions = {(row["restaurant_id"], row["action"]): row["status"] for row in cursor.fetchall()}

            cursor.execute("DELETE FROM operational_actions")
            for act in actions:
                st = completed_actions.get((act["restaurant_id"], act["action"]), "pending")
                cursor.execute("""
                    INSERT INTO operational_actions
                    (restaurant_id, action, type, item, avoidable_cost_inr, feasibility, why, priority_score, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (act["restaurant_id"], act["action"], act["type"], act["item"],
                      act["avoidable_cost_inr"], act["feasibility"], act["why"],
                      act["priority_score"], st))

            # Insert daily report
            note = "Estimated, not verified. Based on synthetic data; a live pilot is needed to confirm savings."
            cursor.execute("""
                INSERT INTO daily_reports
                (as_of_date, planning_date, predicted_orders_total, ingredients_at_risk,
                 purchase_adjustment_qty, recommended_purchase_value_inr,
                 potential_waste_avoided_inr_estimated, status, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (as_of_date, planning_date, int(round(total_orders)), at_risk_count,
                  total_adj_qty, total_p_val, round(potential_waste_avoided, 2), "active", note))

        print("[ReportService] Pipeline execution complete. Daily intelligence updated.")
        return self.get_latest_report()
