import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
import numpy as np
from sqlalchemy import text
from config.database import get_engine

logger = logging.getLogger(__name__)


def load_current_stock() -> pd.DataFrame:
    """
    Load current available stock per item from Stock_Register.
    Uses the latest new_stock value per item (most recent transaction).
    """
    engine = get_engine()

    query = """
        SELECT part_name AS item, new_stock AS available_stock
        FROM Stock_Register
        WHERE id IN (
            SELECT MAX(id)
            FROM Stock_Register
            GROUP BY part_name
        )
    """

    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        logger.info(f"Loaded stock for {len(df)} items from Stock_Register.")
    except Exception as e:
        logger.error(f"Failed to load stock data: {e}")
        raise

    df["available_stock"] = pd.to_numeric(df["available_stock"], errors="coerce").fillna(0)
    return df


def calculate_stock_coverage(available_stock: float, daily_avg_demand: float) -> float:
    """
    How many days will current stock last?
    Formula: available_stock / daily_avg_demand
    """
    if daily_avg_demand <= 0:
        return 9999.0  # infinite coverage if no demand
    return round(available_stock / daily_avg_demand, 1)


def run_inventory_planning(combined_df: pd.DataFrame, horizon_days: int = 30) -> pd.DataFrame:
    """
    Calculate reorder quantities and stock coverage for each item.

    Args:
        combined_df  : Output from combine_forecast_with_pm()
                        Must have: item, forecast_demand, pm_demand, combined_projected_demand
        horizon_days : Number of forecast days (used for daily avg calculation)

    Returns:
        DataFrame with full inventory planning columns
    """
    if combined_df.empty:
        logger.warning("Combined demand DataFrame is empty.")
        return pd.DataFrame()

    # Load current stock
    stock_df = load_current_stock()

    # Merge stock with demand
    plan = combined_df.merge(stock_df, on="item", how="left")
    plan["available_stock"] = plan["available_stock"].fillna(0)

    # Daily average demand
    plan["daily_avg_demand"] = plan["forecast_demand"] / horizon_days

    # Stock coverage days
    plan["stock_coverage_days"] = plan.apply(
        lambda row: calculate_stock_coverage(row["available_stock"], row["daily_avg_demand"]),
        axis=1
    )

    # Projected shortfall (negative = shortage)
    plan["projected_shortfall"] = plan["available_stock"] - plan["combined_projected_demand"]

    # Safety stock = 20% of forecast demand
    plan["safety_stock"] = (plan["forecast_demand"] * 0.20).round(2)

    # Recommended reorder = demand - stock (clamped to 0)
    plan["recommended_reorder_qty"] = (
        plan["combined_projected_demand"] - plan["available_stock"]
    ).clip(lower=0).round(2)

    # Final reorder = recommended + safety stock (clamped to 0)
    plan["final_reorder_qty"] = (
        plan["recommended_reorder_qty"] + plan["safety_stock"]
    ).clip(lower=0).round(2)

    logger.info(f"Inventory planning complete for {len(plan)} items.")
    return plan


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    from services.forecasting import train_and_forecast
    from services.pm_engine import load_pm_demand, combine_forecast_with_pm

    TEST_ITEM = "MDI OIL FILTER (006017310B1-PB)"

    # Step 1: Forecast
    forecast_df = train_and_forecast(item=TEST_ITEM, horizon_days=30)

    # Step 2: Combine with PM demand
    pm_df    = load_pm_demand()
    combined = combine_forecast_with_pm(forecast_df, pm_df)

    # Step 3: Run planning
    plan = run_inventory_planning(combined, horizon_days=30)

    print("\nInventory Plan:")
    print(plan[[
        "item", "available_stock", "forecast_demand",
        "pm_demand", "combined_projected_demand",
        "projected_shortfall", "stock_coverage_days",
        "safety_stock", "recommended_reorder_qty", "final_reorder_qty"
    ]].to_string(index=False))