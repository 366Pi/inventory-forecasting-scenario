import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def assign_risk(available_stock: float, combined_demand: float) -> str:
    if available_stock <= 0:
        return "CRITICAL"
    elif available_stock < combined_demand:
        return "HIGH"
    elif available_stock < combined_demand * 0.5:
        return "WARNING"
    else:
        return "NORMAL"


def assign_alert_status(risk: str) -> str:
    mapping = {
        "CRITICAL": "CRITICAL_SHORTAGE",
        "HIGH":     "LOW_STOCK_WARNING",
        "WARNING":  "LOW_STOCK_WARNING",
        "NORMAL":   "SUFFICIENT_STOCK",
    }
    return mapping.get(risk, "SUFFICIENT_STOCK")


def assign_procurement_priority(risk: str, stock_coverage_days: float) -> str:
    if risk == "CRITICAL":
        return "HIGH"
    elif risk == "HIGH" or stock_coverage_days < 30:
        return "MEDIUM"
    else:
        return "LOW"


def run_alert_engine(plan_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add risk, alert, and procurement priority columns to the inventory plan.

    Args:
        plan_df : Output from run_inventory_planning()

    Returns:
        DataFrame with added columns:
            risk_indicator, alert_level, action_status, procurement_priority
    """
    if plan_df.empty:
        logger.warning("Plan DataFrame is empty — nothing to evaluate.")
        return plan_df

    df = plan_df.copy()

    df["risk_indicator"] = df.apply(
        lambda row: assign_risk(row["available_stock"], row["combined_projected_demand"]),
        axis=1
    )

    df["alert_level"] = df["risk_indicator"]

    df["action_status"] = df["risk_indicator"].apply(assign_alert_status)

    df["procurement_priority"] = df.apply(
        lambda row: assign_procurement_priority(
            row["risk_indicator"], row["stock_coverage_days"]
        ),
        axis=1
    )

    # Summary log
    counts = df["risk_indicator"].value_counts().to_dict()
    logger.info(f"Risk summary: {counts}")

    return df


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    from services.forecasting import train_and_forecast
    from services.pm_engine import load_pm_demand, combine_forecast_with_pm
    from services.inventory_engine import run_inventory_planning

    TEST_ITEM = "MDI OIL FILTER (006017310B1-PB)"

    forecast_df = train_and_forecast(item=TEST_ITEM, horizon_days=30)
    pm_df       = load_pm_demand()
    combined    = combine_forecast_with_pm(forecast_df, pm_df)
    plan        = run_inventory_planning(combined, horizon_days=30)
    result      = run_alert_engine(plan)

    print("\nFull Risk Assessment:")
    print(result[[
        "item", "available_stock", "combined_projected_demand",
        "projected_shortfall", "stock_coverage_days",
        "final_reorder_qty", "risk_indicator",
        "action_status", "procurement_priority"
    ]].to_string(index=False))
