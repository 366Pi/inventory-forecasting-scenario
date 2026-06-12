import logging
import warnings
import pandas as pd
import numpy as np
from prophet import Prophet
from sqlalchemy import text
from config.database import get_engine
from services.data_loader import load_demand_data, get_available_items

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


def train_and_forecast(item: str, horizon_days: int = 30) -> pd.DataFrame:
    """
    Train a Prophet model for one item and return forecast results.

    Returns DataFrame with columns:
        forecast_date, predicted_demand, min_expected_demand, max_expected_demand
    """
    df = load_demand_data(item=item, aggregation="day")

    if df.empty or len(df) < 10:
        logger.warning(f"Not enough data for item: {item}")
        return pd.DataFrame()

    # Prophet requires columns named 'ds' and 'y'
    prophet_df = df[["date", "demand"]].rename(columns={"date": "ds", "demand": "y"})
    prophet_df = prophet_df[prophet_df["y"] >= 0]

    try:
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.80
        )
        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=horizon_days, freq="D")
        forecast = model.predict(future)

        # Keep only the future forecast rows
        result = forecast[forecast["ds"] > prophet_df["ds"].max()][
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ].copy()

        result.rename(columns={
            "ds":         "forecast_date",
            "yhat":       "predicted_demand",
            "yhat_lower": "min_expected_demand",
            "yhat_upper": "max_expected_demand"
        }, inplace=True)

        # Clamp negatives to 0
        result["predicted_demand"]    = result["predicted_demand"].clip(lower=0)
        result["min_expected_demand"] = result["min_expected_demand"].clip(lower=0)
        result["max_expected_demand"] = result["max_expected_demand"].clip(lower=0)

        result["item"] = item
        result["horizon_days"] = horizon_days

        logger.info(f"Forecast done for '{item}' — {horizon_days} days.")
        return result.reset_index(drop=True)

    except Exception as e:
        logger.error(f"Forecast failed for '{item}': {e}")
        return pd.DataFrame()


def calculate_accuracy(item: str) -> dict:
    """
    Calculate forecast accuracy metrics using last 30 days as test set.
    Returns MAE, RMSE, MAPE.
    """
    df = load_demand_data(item=item, aggregation="day")

    if len(df) < 15:
        return {"MAE": None, "RMSE": None, "MAPE": None}

    prophet_df = df[["date", "demand"]].rename(columns={"date": "ds", "demand": "y"})
    prophet_df = prophet_df[prophet_df["y"] >= 0]

    # Use last 20% of data as test set, minimum 5 rows
    test_size = max(5, int(len(prophet_df) * 0.20))
    train = prophet_df.iloc[:-test_size]
    test  = prophet_df.iloc[-test_size:]

    try:
        model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
        model.fit(train)

        future   = model.make_future_dataframe(periods=test_size, freq="D")
        forecast = model.predict(future)

        # Merge on date so shapes always match
        merged = test.merge(
            forecast[["ds", "yhat"]],
            on="ds",
            how="inner"
        )

        if merged.empty:
            return {"MAE": None, "RMSE": None, "MAPE": None}

        actual    = merged["y"].values
        predicted = merged["yhat"].values

        mae  = float(np.mean(np.abs(actual - predicted)))
        rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))

        mask = actual != 0
        mape = float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100) if mask.any() else None

        return {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "MAPE": round(mape, 2) if mape else None}

    except Exception as e:
        logger.error(f"Accuracy calc failed for '{item}': {e}")
        return {"MAE": None, "RMSE": None, "MAPE": None}


def run_forecast_pipeline(horizon_days: int = 30, max_items: int = None) -> pd.DataFrame:
    """
    Run forecasts for all items and return combined DataFrame.
    Set max_items to a small number (e.g. 5) for testing.
    """
    items = get_available_items()

    if max_items:
        items = items[:max_items]

    all_forecasts = []

    for i, item in enumerate(items):
        logger.info(f"[{i+1}/{len(items)}] Forecasting: {item}")
        result = train_and_forecast(item=item, horizon_days=horizon_days)
        if not result.empty:
            all_forecasts.append(result)

    if not all_forecasts:
        logger.warning("No forecasts generated.")
        return pd.DataFrame()

    combined = pd.concat(all_forecasts, ignore_index=True)
    logger.info(f"Pipeline complete. Total forecast rows: {len(combined)}")
    return combined


def save_forecast_to_db(forecast_df: pd.DataFrame):
    """Save forecast results to forecast_output table."""
    if forecast_df.empty:
        logger.warning("Nothing to save.")
        return

    engine = get_engine()
    try:
        forecast_df.to_sql("forecast_output", engine, if_exists="replace", index=False)
        logger.info(f"Saved {len(forecast_df)} rows to forecast_output.")
    except Exception as e:
        logger.error(f"Failed to save forecast: {e}")
        raise


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    TEST_ITEM = "MDI OIL FILTER (006017310B1-PB)"

    result = train_and_forecast(item=TEST_ITEM, horizon_days=30)
    print("\nForecast result (first 10 rows):")
    print(result.head(10))
    print(f"\nTotal forecast rows: {len(result)}")

    metrics = calculate_accuracy(item=TEST_ITEM)
    print(f"\nAccuracy Metrics: {metrics}")
