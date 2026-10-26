import numpy as np
import pandas as pd
from datetime import datetime

# Categorical mappings matching training data
RESTAURANT_MAP = {"R01": 0, "R02": 1}
DISH_MAP = {
    "D01": 0, "D02": 1, "D03": 2, "D04": 3, "D05": 4, "D06": 5,
    "D07": 6, "D08": 7, "D09": 8, "D10": 9, "D11": 10, "D12": 11
}
DISH_CATEGORY_MAP = {
    "Breads": 0, "Combos": 1, "Main Course": 2,
    "Rice & Biryani": 3, "South Indian": 4, "Starter": 5
}
INGREDIENT_MAP = {
    f"I{i:02d}": i - 1 for i in range(1, 18)
}
ING_CATEGORY_MAP = {
    "Dairy": 0, "Dry": 1, "Produce": 2
}
STORAGE_MAP = {
    "Chiller": 0, "Cool room": 1, "Dry store": 2
}

def build_demand_features(
    restaurant_id: str,
    dish_id: str,
    category: str,
    target_date: str,
    selling_price_inr: float,
    promo_flag: int = 0,
    holiday_flag: int = 0,
    avg_temp_c: float = 24.0,
    rainfall_mm: float = 0.0,
    lag_1: float = 30.0,
    lag_7: float = 30.0,
    lag_14: float = 30.0,
    roll_mean_7: float = 30.0,
    roll_mean_28: float = 30.0
) -> pd.DataFrame:
    """Prepares 18 features for Model 1 (Demand Poisson & Quantile Regressors)"""
    dt = pd.to_datetime(target_date)
    dow = dt.dayofweek
    is_weekend = 1 if dow in (5, 6) else 0
    month = dt.month
    doy = dt.dayofyear
    doy_sin = float(np.sin(2 * np.pi * doy / 365.25))
    doy_cos = float(np.cos(2 * np.pi * doy / 365.25))

    row = {
        "restaurant_code": RESTAURANT_MAP.get(restaurant_id, 0),
        "dish_code": DISH_MAP.get(dish_id, 0),
        "category_code": DISH_CATEGORY_MAP.get(category, 0),
        "dow": dow,
        "is_weekend": is_weekend,
        "month": month,
        "doy_sin": doy_sin,
        "doy_cos": doy_cos,
        "selling_price_inr": float(selling_price_inr),
        "promo_flag": int(promo_flag),
        "holiday_flag": int(holiday_flag),
        "avg_temp_c": float(avg_temp_c),
        "rainfall_mm": float(rainfall_mm),
        "lag_1": float(lag_1),
        "lag_7": float(lag_7),
        "lag_14": float(lag_14),
        "roll_mean_7": float(roll_mean_7),
        "roll_mean_28": float(roll_mean_28)
    }
    return pd.DataFrame([row])

def build_risk_features(
    restaurant_id: str,
    ingredient_id: str,
    category: str,
    storage_type: str,
    perishable_flag: int,
    shelf_life_days: int,
    closing_stock_qty: float,
    batches_on_hand: int,
    min_days_to_expiry: float,
    weighted_remaining_shelf_life_days: float,
    days_since_last_delivery: int,
    pending_order_qty: float,
    usage_1d: float,
    usage_7d_mean: float,
    cover_days: float,
    target_cover_days: float,
    discard_7d: float = 0.0,
    discard_14d: float = 0.0,
    shortage_7d: float = 0.0,
    discard_rate_14d: float = 0.0,
    target_date: str = None
) -> pd.DataFrame:
    """Prepares 22 features for Model 2 (Ingredient Waste Risk GBM Classifier)"""
    if target_date:
        dt = pd.to_datetime(target_date)
        dow = dt.dayofweek
        month = dt.month
    else:
        dt = datetime.now()
        dow = dt.weekday()
        month = dt.month

    row = {
        "restaurant_code": RESTAURANT_MAP.get(restaurant_id, 0),
        "ingredient_code": INGREDIENT_MAP.get(ingredient_id, 0),
        "category_code": ING_CATEGORY_MAP.get(category, 0),
        "storage_code": STORAGE_MAP.get(storage_type, 0),
        "perishable_flag": int(perishable_flag),
        "shelf_life_days": int(shelf_life_days),
        "closing_stock_qty": float(closing_stock_qty),
        "batches_on_hand": int(batches_on_hand),
        "min_days_to_expiry": float(min_days_to_expiry),
        "weighted_remaining_shelf_life_days": float(weighted_remaining_shelf_life_days),
        "days_since_last_delivery": int(days_since_last_delivery),
        "pending_order_qty": float(pending_order_qty),
        "usage_1d": float(usage_1d),
        "usage_7d_mean": float(usage_7d_mean),
        "cover_days": float(cover_days),
        "target_cover_days": float(target_cover_days),
        "discard_7d": float(discard_7d),
        "discard_14d": float(discard_14d),
        "shortage_7d": float(shortage_7d),
        "discard_rate_14d": float(discard_rate_14d),
        "dow": dow,
        "month": month
    }
    return pd.DataFrame([row])
