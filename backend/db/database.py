import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "freshflow.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Restaurants table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurants (
                restaurant_id TEXT PRIMARY KEY,
                restaurant_name TEXT NOT NULL,
                demand_multiplier REAL DEFAULT 1.0
            )
        ''')

        # Dishes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dishes (
                dish_id TEXT PRIMARY KEY,
                dish_name TEXT NOT NULL,
                category TEXT NOT NULL,
                list_price_inr REAL NOT NULL,
                base_daily_orders INTEGER NOT NULL,
                weekend_uplift REAL DEFAULT 0.0,
                temp_sensitivity REAL DEFAULT 0.0
            )
        ''')

        # Ingredients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingredients (
                ingredient_id TEXT PRIMARY KEY,
                ingredient_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_cost_inr REAL NOT NULL,
                shelf_life_days INTEGER NOT NULL,
                storage_type TEXT NOT NULL,
                perishable_flag INTEGER DEFAULT 0,
                supplier_lead_time_days INTEGER DEFAULT 1,
                min_order_qty REAL DEFAULT 1.0,
                target_cover_days REAL DEFAULT 3.0,
                supplier_name TEXT NOT NULL
            )
        ''')

        # Recipes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dish_id TEXT NOT NULL,
                ingredient_id TEXT NOT NULL,
                qty_per_portion REAL NOT NULL,
                unit TEXT NOT NULL,
                prep_yield_loss_pct REAL DEFAULT 0.0,
                FOREIGN KEY (dish_id) REFERENCES dishes(dish_id),
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id)
            )
        ''')

        # Current live inventory stock
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id TEXT NOT NULL,
                ingredient_id TEXT NOT NULL,
                ingredient_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_cost_inr REAL NOT NULL,
                closing_stock_qty REAL NOT NULL,
                min_days_to_expiry REAL NOT NULL,
                usage_1d REAL DEFAULT 0.0,
                usage_7d_mean REAL DEFAULT 0.0,
                cover_days REAL DEFAULT 0.0,
                risk_prob_next_3d REAL DEFAULT 0.0,
                risk_level TEXT DEFAULT 'Low',
                surplus_qty_next_3d REAL DEFAULT 0.0,
                expected_at_risk_qty REAL DEFAULT 0.0,
                financial_exposure_inr REAL DEFAULT 0.0,
                primary_driver TEXT DEFAULT 'Normal',
                batches_on_hand INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(restaurant_id, ingredient_id)
            )
        ''')

        # Operational Actions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operational_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id TEXT NOT NULL,
                action TEXT NOT NULL,
                type TEXT NOT NULL,
                item TEXT NOT NULL,
                avoidable_cost_inr REAL NOT NULL,
                feasibility REAL NOT NULL,
                why TEXT NOT NULL,
                priority_score REAL NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, completed, dismissed, deferred
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Forecast results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forecast_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_date TEXT NOT NULL,
                restaurant_id TEXT NOT NULL,
                dish_id TEXT NOT NULL,
                dish_name TEXT NOT NULL,
                category TEXT NOT NULL,
                predicted_orders_median REAL NOT NULL,
                lower_80 REAL NOT NULL,
                upper_80 REAL NOT NULL,
                forecast_confidence TEXT DEFAULT 'High',
                suggested_prep_qty INTEGER NOT NULL,
                prep_stage_batch_qty INTEGER NOT NULL,
                cost_per_portion_inr REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Purchase plan
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id TEXT NOT NULL,
                ingredient_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                required_qty REAL NOT NULL,
                usable_stock_qty REAL NOT NULL,
                incoming_qty REAL NOT NULL,
                recommended_purchase_qty REAL NOT NULL,
                purchase_value_inr REAL NOT NULL,
                purchase_adjustment_qty REAL NOT NULL
            )
        ''')

        # Waste events log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waste_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                restaurant_id TEXT NOT NULL,
                ingredient_id TEXT NOT NULL,
                ingredient_name TEXT NOT NULL,
                qty REAL NOT NULL,
                unit TEXT NOT NULL,
                reason TEXT NOT NULL, -- expired, spoilage, over-prep
                discard_cost_inr REAL NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Reports summary
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of_date TEXT NOT NULL,
                planning_date TEXT NOT NULL,
                predicted_orders_total INTEGER NOT NULL,
                ingredients_at_risk INTEGER NOT NULL,
                purchase_adjustment_qty REAL NOT NULL,
                recommended_purchase_value_inr REAL NOT NULL,
                potential_waste_avoided_inr_estimated REAL NOT NULL,
                status TEXT DEFAULT 'active',
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Recent historical sales summary
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                restaurant_id TEXT NOT NULL,
                dish_id TEXT NOT NULL,
                dish_name TEXT NOT NULL,
                category TEXT NOT NULL,
                list_price_inr REAL NOT NULL,
                selling_price_inr REAL NOT NULL,
                promo_flag INTEGER DEFAULT 0,
                holiday_flag INTEGER DEFAULT 0,
                avg_temp_c REAL,
                rainfall_mm REAL,
                units_sold INTEGER NOT NULL
            )
        ''')
