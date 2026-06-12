import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
from sqlalchemy import text
from config.database import get_engine

logger = logging.getLogger(__name__)


def load_pm_demand() -> pd.DataFrame:
    """
    Load PM demand from pm_demand_output table.
    Returns DataFrame with columns: item, pm_demand
    """
    engine = get_engine()
    query = "SELECT item, pm_demand FROM pm_demand_output"

    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        logger.info(f"Loaded {len(df)} rows from pm_demand_output.")
    except Exception as e:
        logger.error(f"Failed to load PM demand: {e}")
        raise

    df["pm_demand"] = pd.to_numeric(df["pm_demand"], errors="coerce").fillna(0)
    return df


def combine_forecast_with_pm(forecast_df: pd.DataFrame, pm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge forecast demand with PM demand per item.

    Formula:
        combined_projected_demand = forecast_demand + pm_demand

    Args:
        forecast_df : DataFrame with columns [item, predicted_demand, ...]
        pm_df       : DataFrame with columns [item, pm_demand]

    Returns:
        DataFrame with combined_projected_demand added
    """
    if forecast_df.empty:
        logger.warning("Forecast DataFrame is empty — nothing to combine.")
        return forecast_df

    # Sum total forecast demand per item across all forecast dates
    forecast_summary = (
        forecast_df.groupby("item")["predicted_demand"]
        .sum()
        .reset_index()
        .rename(columns={"predicted_demand": "forecast_demand"})
    )

    # Merge PM demand
    combined = forecast_summary.merge(pm_df, on="item", how="left")
    combined["pm_demand"] = combined["pm_demand"].fillna(0)

    # Core formula
    combined["combined_projected_demand"] = combined["forecast_demand"] + combined["pm_demand"]

    logger.info(f"Combined demand calculated for {len(combined)} items.")
    return combined


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    from services.forecasting import train_and_forecast

    # Step 1: Get forecast for one item
    TEST_ITEM = "MDI OIL FILTER (006017310B1-PB)"
    forecast_df = train_and_forecast(item=TEST_ITEM, horizon_days=30)

    # Step 2: Load PM demand
    pm_df = load_pm_demand()
    print("\nPM Demand table:")
    print(pm_df.head(10))

    # Step 3: Combine
    combined = combine_forecast_with_pm(forecast_df, pm_df)
    print("\nCombined Demand:")
    print(combined)