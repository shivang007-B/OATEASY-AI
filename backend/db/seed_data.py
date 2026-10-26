import os
import json
import sqlite3
import pandas as pd
from backend.db.database import get_db, init_db, DB_PATH

BASE_ML_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "FreshFlow_ML")
DATA_DIR = os.path.join(BASE_ML_DIR, "data")
OUTPUTS_DIR = os.path.join(BASE_ML_DIR, "outputs")

def seed_database(force=False):
    # Initialize schema
    init_db()

    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if already seeded
        cursor.execute("SELECT COUNT(*) as cnt FROM restaurants")
        if cursor.fetchone()[0] > 0 and not force:
            print("Database already seeded. Skipping.")
            return

        print("Seeding database from FreshFlow_ML...")

        # 1. Restaurants
        df_rest = pd.read_csv(os.path.join(DATA_DIR, "restaurants.csv"))
        for _, row in df_rest.iterrows():
            cursor.execute(
                "INSERT OR REPLACE INTO restaurants (restaurant_id, restaurant_name, demand_multiplier) VALUES (?, ?, ?)",
                (row["restaurant_id"], row["restaurant_name"], float(row["demand_multiplier"]))
            )

        # 2. Dishes
        df_dish = pd.read_csv(os.path.join(DATA_DIR, "dish_master.csv"))
        for _, row in df_dish.iterrows():
            cursor.execute(
                """INSERT OR REPLACE INTO dishes 
                   (dish_id, dish_name, category, list_price_inr, base_daily_orders, weekend_uplift, temp_sensitivity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (row["dish_id"], row["dish_name"], row["category"], float(row["list_price_inr"]),
                 int(row["base_daily_orders"]), float(row["weekend_uplift"]), float(row["temp_sensitivity"]))
            )

        # 3. Ingredients
        df_ing = pd.read_csv(os.path.join(DATA_DIR, "ingredient_master.csv"))
        for _, row in df_ing.iterrows():
            cursor.execute(
                """INSERT OR REPLACE INTO ingredients
                   (ingredient_id, ingredient_name, category, unit, unit_cost_inr, shelf_life_days,
                    storage_type, perishable_flag, supplier_lead_time_days, min_order_qty, target_cover_days, supplier_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["ingredient_id"], row["ingredient_name"], row["category"], row["unit"],
                 float(row["unit_cost_inr"]), int(row["shelf_life_days"]), row["storage_type"],
                 int(row["perishable_flag"]), int(row["supplier_lead_time_days"]),
                 float(row["min_order_qty"]), float(row["target_cover_days"]), row["supplier_name"])
            )

        # 4. Recipes
        df_rec = pd.read_csv(os.path.join(DATA_DIR, "dataset3_recipes.csv"))
        cursor.execute("DELETE FROM recipes")
        for _, row in df_rec.iterrows():
            cursor.execute(
                """INSERT INTO recipes (dish_id, ingredient_id, qty_per_portion, unit, prep_yield_loss_pct)
                   VALUES (?, ?, ?, ?, ?)""",
                (row["dish_id"], row["ingredient_id"], float(row["qty_per_portion"]),
                 row["unit"], float(row.get("prep_yield_loss_pct", 0.0)))
            )

        # 5. Inventory Stock (from latest ingredient_risk_next_day.csv)
        df_risk = pd.read_csv(os.path.join(OUTPUTS_DIR, "ingredient_risk_next_day.csv"))
        cursor.execute("DELETE FROM inventory_stock")
        for _, row in df_risk.iterrows():
            cursor.execute(
                """INSERT INTO inventory_stock
                   (restaurant_id, ingredient_id, ingredient_name, category, unit, unit_cost_inr,
                    closing_stock_qty, min_days_to_expiry, usage_1d, usage_7d_mean, cover_days,
                    risk_prob_next_3d, risk_level, surplus_qty_next_3d, expected_at_risk_qty,
                    financial_exposure_inr, primary_driver, batches_on_hand)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["restaurant_id"], row["ingredient_id"], row["ingredient_name"], row["category"],
                 row["unit"], float(row["unit_cost_inr"]), float(row["closing_stock_qty"]),
                 float(row["min_days_to_expiry"]), float(row.get("usage_1d", row["usage_7d_mean"])),
                 float(row["usage_7d_mean"]), float(row["cover_days"]),
                 float(row["risk_prob_next_3d"]), row["risk_level"], float(row["surplus_qty_next_3d"]),
                 float(row["expected_at_risk_qty"]), float(row["financial_exposure_inr"]),
                 row["primary_driver"], 2)
            )

        # 6. Operational Actions (from operational_plan_actions.csv)
        df_act = pd.read_csv(os.path.join(OUTPUTS_DIR, "operational_plan_actions.csv"))
        cursor.execute("DELETE FROM operational_actions")
        for _, row in df_act.iterrows():
            cursor.execute(
                """INSERT INTO operational_actions
                   (restaurant_id, action, type, item, avoidable_cost_inr, feasibility, why, priority_score, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["restaurant_id"], row["action"], row["type"], row["item"],
                 float(row["avoidable_cost_inr"]), float(row["feasibility"]),
                 row["why"], float(row["priority_score"]), "pending")
            )

        # 7. Forecast results & Prep plan
        df_fc = pd.read_csv(os.path.join(OUTPUTS_DIR, "forecast_next_day.csv"))
        df_prep = pd.read_csv(os.path.join(OUTPUTS_DIR, "prep_plan.csv"))
        df_fc_merged = df_fc.merge(
            df_prep[["restaurant_id", "dish_id", "suggested_prep_qty", "prep_stage_batch_qty", "cost_per_portion_inr"]],
            on=["restaurant_id", "dish_id"],
            how="left"
        )
        cursor.execute("DELETE FROM forecast_results")
        for _, row in df_fc_merged.iterrows():
            cursor.execute(
                """INSERT INTO forecast_results
                   (forecast_date, restaurant_id, dish_id, dish_name, category,
                    predicted_orders_median, lower_80, upper_80, forecast_confidence,
                    suggested_prep_qty, prep_stage_batch_qty, cost_per_portion_inr)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(row["date"]), row["restaurant_id"], row["dish_id"], row["dish_name"], row["category"],
                 float(row["predicted_orders_median"]), float(row["lower_80"]), float(row["upper_80"]),
                 row["forecast_confidence"], int(row["suggested_prep_qty"]),
                 int(row["prep_stage_batch_qty"]), float(row["cost_per_portion_inr"]))
            )

        # 8. Purchase plan
        df_purch = pd.read_csv(os.path.join(OUTPUTS_DIR, "purchase_plan.csv"))
        cursor.execute("DELETE FROM purchase_plan")
        for _, row in df_purch.iterrows():
            cursor.execute(
                """INSERT INTO purchase_plan
                   (restaurant_id, ingredient_name, unit, required_qty, usable_stock_qty,
                    incoming_qty, recommended_purchase_qty, purchase_value_inr, purchase_adjustment_qty)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["restaurant_id"], row["ingredient_name"], row["unit"], float(row["required_qty"]),
                 float(row["usable_stock_qty"]), float(row["incoming_qty"]), float(row["recommended_purchase_qty"]),
                 float(row["purchase_value_inr"]), float(row["purchase_adjustment_qty"]))
            )

        # 9. Waste Events (from dataset2_inventory_waste.csv discards)
        df_waste = pd.read_csv(os.path.join(DATA_DIR, "dataset2_inventory_waste.csv"))
        discards = df_waste[df_waste["total_discard_qty"] > 0].copy()
        # Sort by date descending, take recent ~500 events
        discards["date"] = pd.to_datetime(discards["date"])
        recent_discards = discards.sort_values("date", ascending=False).head(400)
        cursor.execute("DELETE FROM waste_events")
        for _, row in recent_discards.iterrows():
            cursor.execute(
                """INSERT INTO waste_events
                   (date, restaurant_id, ingredient_id, ingredient_name, qty, unit, reason, discard_cost_inr, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["date"].strftime("%Y-%m-%d"), row["restaurant_id"], row["ingredient_id"],
                 row["ingredient_name"], float(row["total_discard_qty"]), row["unit"],
                 str(row["discard_reason"]), float(row["discard_cost_inr"]), "Historical recorded waste")
            )

        # 10. Daily Reports
        with open(os.path.join(OUTPUTS_DIR, "report_summary.json"), "r") as f:
            rep = json.load(f)
        cursor.execute("DELETE FROM daily_reports")
        cursor.execute(
            """INSERT INTO daily_reports
               (as_of_date, planning_date, predicted_orders_total, ingredients_at_risk,
                purchase_adjustment_qty, recommended_purchase_value_inr,
                potential_waste_avoided_inr_estimated, status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rep["as_of"], rep["planning_date"], int(rep["predicted_orders_total"]),
             int(rep["ingredients_at_risk"]), float(rep["purchase_adjustment_qty"]),
             float(rep["recommended_purchase_value_inr"]),
             float(rep["potential_waste_avoided_inr_estimated"]), "active", rep["note"])
        )

        # 11. Sales history (last 60 days for fast loading and rich graphs)
        df_sales = pd.read_csv(os.path.join(DATA_DIR, "dataset1_sales_demand.csv"))
        df_sales["date"] = pd.to_datetime(df_sales["date"])
        recent_sales = df_sales[df_sales["date"] >= "2025-11-01"].copy()
        cursor.execute("DELETE FROM sales_history")
        for _, row in recent_sales.iterrows():
            cursor.execute(
                """INSERT INTO sales_history
                   (date, restaurant_id, dish_id, dish_name, category, list_price_inr,
                    selling_price_inr, promo_flag, holiday_flag, avg_temp_c, rainfall_mm, units_sold)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["date"].strftime("%Y-%m-%d"), row["restaurant_id"], row["dish_id"],
                 row["dish_name"], row["category"], float(row["list_price_inr"]),
                 float(row["selling_price_inr"]), int(row["promo_flag"]), int(row["holiday_flag"]),
                 float(row["avg_temp_c"]) if pd.notna(row["avg_temp_c"]) else 24.0,
                 float(row["rainfall_mm"]) if pd.notna(row["rainfall_mm"]) else 0.0,
                 int(row["units_sold"]))
            )

        print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database(force=True)
