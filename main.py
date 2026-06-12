import logging
import time
import pandas as pd
from config.logger import setup_logger
from services.data_loader import load_all_demand_data, get_available_items, load_demand_data
from services.forecasting import train_and_forecast, calculate_accuracy, save_forecast_to_db
from services.pm_engine import load_pm_demand, combine_forecast_with_pm
from services.inventory_engine import run_inventory_planning
from services.alert_engine import run_alert_engine

logger = setup_logger("pipeline")


def run_pipeline(
    horizon_days: int = 30,
    max_items: int = None,
    scenario_name: str = "Normal",
    demand_multiplier: float = 1.0,
    pm_multiplier: float = 1.0
) -> pd.DataFrame:
    """
    Run the full inventory forecasting and planning pipeline.

    Args:
        horizon_days       : Forecast horizon (30, 60, or 90 days)
        max_items          : Limit items for testing (None = all items)
        scenario_name      : Label for this run (Normal / +20% Demand / +50% PM)
        demand_multiplier  : Scale forecast demand (1.0 = normal)
        pm_multiplier      : Scale PM demand (1.0 = normal)

    Returns:
        Final inventory plan DataFrame with risk and procurement columns
    """
    start_time = time.time()
    logger.info(f"Pipeline started — scenario: {scenario_name}, horizon: {horizon_days} days")

    # Step 1: Get items with enough data to forecast (min 10 rows)
    full_df   = load_all_demand_data()
    row_counts = full_df.groupby("item").size()
    eligible  = row_counts[row_counts >= 10].index.tolist()
    all_items = sorted(eligible)

    if max_items:
        all_items = all_items[:max_items]
    logger.info(f"Processing {len(all_items)} items with sufficient data.")

    # Step 2: Forecast each item
    all_forecasts = []
    for i, item in enumerate(all_items):
        result = train_and_forecast(item=item, horizon_days=horizon_days)
        if not result.empty:
            result["predicted_demand"] *= demand_multiplier
            all_forecasts.append(result)

    if not all_forecasts:
        logger.error("No forecasts generated. Aborting.")
        return pd.DataFrame()

    forecast_df = pd.concat(all_forecasts, ignore_index=True)
    logger.info(f"Forecasts generated for {len(all_forecasts)} items.")

    # Save raw forecast results to forecast_output table
    try:
        save_forecast_to_db(forecast_df)
        logger.info("Forecast results saved to forecast_output table.")
    except Exception as e:
        logger.warning(f"Could not save forecast to DB: {e}")

    # Step 3: PM demand integration
    pm_df = load_pm_demand()
    pm_df["pm_demand"] = pm_df["pm_demand"] * pm_multiplier
    combined = combine_forecast_with_pm(forecast_df, pm_df)

    # Step 4: Inventory planning
    plan = run_inventory_planning(combined, horizon_days=horizon_days)

    # Step 5: Risk and alerts
    final = run_alert_engine(plan)

    # Step 6: Add metadata
    final["scenario_name"]    = scenario_name
    final["forecast_horizon"] = horizon_days

    elapsed = round(time.time() - start_time, 2)
    final["pipeline_execution_time"] = elapsed

    logger.info(f"Pipeline complete in {elapsed}s — {len(final)} items processed.")
    return final


if __name__ == "__main__":
    # Quick test: run pipeline for 5 items only
    result = run_pipeline(
        horizon_days=30,
        max_items=5,
        scenario_name="Normal"
    )

    if not result.empty:
        print("\nPipeline Result (5 items):")
        print(result[[
            "item", "available_stock", "combined_projected_demand",
            "risk_indicator", "final_reorder_qty", "procurement_priority"
        ]].to_string(index=False))

        print(f"\nRisk breakdown:\n{result['risk_indicator'].value_counts().to_string()}")