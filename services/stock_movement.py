import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
from sqlalchemy import text
from config.database import get_engine

logger = logging.getLogger(__name__)


def load_monthly_movement(item: str = None) -> pd.DataFrame:
    """
    Load monthly stock IN vs OUT per item from Stock_Register.

    Returns columns:
        part_name, month, total_in, total_out, net_movement, replenishment_ratio
    """
    engine = get_engine()

    item_filter = f"AND part_name = :item" if item else ""

    query = f"""
        SELECT
            part_name,
            FORMAT(ts, 'yyyy-MM')                                        AS month,
            SUM(CASE WHEN in_out = 'IN'  THEN qty ELSE 0 END)           AS total_in,
            SUM(CASE WHEN in_out = 'OUT' THEN qty ELSE 0 END)           AS total_out
        FROM Stock_Register
        WHERE in_out IN ('IN', 'OUT')
        {item_filter}
        GROUP BY part_name, FORMAT(ts, 'yyyy-MM')
        ORDER BY part_name, month
    """

    try:
        with engine.connect() as conn:
            params = {"item": item} if item else {}
            df = pd.read_sql(text(query), conn, params=params)
        logger.info(f"Loaded monthly movement for {'item: ' + item if item else 'all items'} — {len(df)} rows.")
    except Exception as e:
        logger.error(f"Failed to load monthly movement: {e}")
        raise

    df["total_in"]  = pd.to_numeric(df["total_in"],  errors="coerce").fillna(0)
    df["total_out"] = pd.to_numeric(df["total_out"], errors="coerce").fillna(0)

    # net_movement: positive = more came in than went out (surplus), negative = consumed more than received
    df["net_movement"] = df["total_in"] - df["total_out"]

    # replenishment_ratio: how much of consumption was covered by incoming stock (1.0 = perfectly balanced)
    df["replenishment_ratio"] = df.apply(
        lambda r: round(r["total_in"] / r["total_out"], 2) if r["total_out"] > 0 else None,
        axis=1
    )

    return df


def load_movement_summary() -> pd.DataFrame:
    """
    Summary table: one row per item showing avg monthly IN, avg monthly OUT,
    net consumption rate, and overall replenishment health.

    Returns columns:
        part_name, avg_monthly_in, avg_monthly_out, avg_net_movement,
        total_in, total_out, replenishment_ratio, consumption_status
    """
    engine = get_engine()

    query = """
        SELECT
            part_name,
            SUM(CASE WHEN in_out = 'IN'  THEN qty ELSE 0 END)  AS total_in,
            SUM(CASE WHEN in_out = 'OUT' THEN qty ELSE 0 END)  AS total_out,
            COUNT(DISTINCT FORMAT(ts, 'yyyy-MM'))               AS active_months
        FROM Stock_Register
        WHERE in_out IN ('IN', 'OUT')
        GROUP BY part_name
    """

    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        logger.info(f"Loaded movement summary for {len(df)} items.")
    except Exception as e:
        logger.error(f"Failed to load movement summary: {e}")
        raise

    df["total_in"]       = pd.to_numeric(df["total_in"],       errors="coerce").fillna(0)
    df["total_out"]      = pd.to_numeric(df["total_out"],       errors="coerce").fillna(0)
    df["active_months"]  = pd.to_numeric(df["active_months"],   errors="coerce").fillna(1)

    df["avg_monthly_in"]  = (df["total_in"]  / df["active_months"]).round(2)
    df["avg_monthly_out"] = (df["total_out"] / df["active_months"]).round(2)
    df["avg_net_movement"]= (df["avg_monthly_in"] - df["avg_monthly_out"]).round(2)

    df["replenishment_ratio"] = df.apply(
        lambda r: round(r["total_in"] / r["total_out"], 2) if r["total_out"] > 0 else None,
        axis=1
    )

    # consumption_status: is replenishment keeping up with consumption?
    def status(ratio):
        if ratio is None:
            return "NO CONSUMPTION"
        elif ratio >= 1.2:
            return "OVERSTOCKED"
        elif ratio >= 0.9:
            return "BALANCED"
        elif ratio >= 0.6:
            return "UNDER-REPLENISHED"
        else:
            return "CRITICALLY LOW REPLENISHMENT"

    df["consumption_status"] = df["replenishment_ratio"].apply(status)

    return df.sort_values("avg_monthly_out", ascending=False).reset_index(drop=True)


def get_top_consuming_items(top_n: int = 20) -> pd.DataFrame:
    """Return top N items ranked by total OUT quantity."""
    engine = get_engine()
    query = """
        SELECT TOP (:top_n)
            part_name,
            SUM(qty)    AS total_out,
            COUNT(*)    AS transaction_count,
            MIN(ts)     AS first_seen,
            MAX(ts)     AS last_seen
        FROM Stock_Register
        WHERE in_out = 'OUT'
        GROUP BY part_name
        ORDER BY total_out DESC
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={"top_n": top_n})
        logger.info(f"Loaded top {top_n} consuming items.")
    except Exception as e:
        logger.error(f"Failed to load top consuming items: {e}")
        raise

    df["total_out"]         = pd.to_numeric(df["total_out"],         errors="coerce").fillna(0)
    df["transaction_count"] = pd.to_numeric(df["transaction_count"], errors="coerce").fillna(0)
    return df


def get_overall_stats() -> dict:
    """Return high-level stats: total IN events, total OUT events, date range."""
    engine = get_engine()
    query = """
        SELECT
            SUM(CASE WHEN in_out = 'IN'  THEN 1 ELSE 0 END)  AS total_in_transactions,
            SUM(CASE WHEN in_out = 'OUT' THEN 1 ELSE 0 END)  AS total_out_transactions,
            SUM(CASE WHEN in_out = 'IN'  THEN qty ELSE 0 END) AS total_in_qty,
            SUM(CASE WHEN in_out = 'OUT' THEN qty ELSE 0 END) AS total_out_qty,
            MIN(ts) AS earliest,
            MAX(ts) AS latest,
            COUNT(DISTINCT part_name) AS unique_items
        FROM Stock_Register
        WHERE in_out IN ('IN', 'OUT')
    """
    try:
        with engine.connect() as conn:
            row = pd.read_sql(text(query), conn).iloc[0]
        return {
            "total_in_transactions":  int(row["total_in_transactions"]),
            "total_out_transactions": int(row["total_out_transactions"]),
            "total_in_qty":           round(float(row["total_in_qty"]),  2),
            "total_out_qty":          round(float(row["total_out_qty"]), 2),
            "earliest":               str(row["earliest"])[:10],
            "latest":                 str(row["latest"])[:10],
            "unique_items":           int(row["unique_items"]),
        }
    except Exception as e:
        logger.error(f"Failed to load overall stats: {e}")
        raise
