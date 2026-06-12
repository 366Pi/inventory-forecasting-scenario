
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd
from sqlalchemy import text
from config.database import get_engine

logger = logging.getLogger(__name__)

_cache: pd.DataFrame = None  # in-memory cache — one load per session

def load_all_demand_data() -> pd.DataFrame:
    """Load entire forecast_ready_dataset in one query and cache it."""
    global _cache
    if _cache is not None:
        return _cache

    engine = get_engine()
    query = "SELECT date, item, demand FROM forecast_ready_dataset ORDER BY date ASC"

    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        logger.info(f"Loaded {len(df)} total rows from forecast_ready_dataset.")
    except Exception as e:
        logger.error(f"Failed to load demand data: {e}")
        raise

    df["date"]   = pd.to_datetime(df["date"])
    df["demand"] = pd.to_numeric(df["demand"], errors="coerce").fillna(0)

    _cache = df
    return _cache


def load_demand_data(item: str = None, aggregation: str = "day") -> pd.DataFrame:
    """
    Filter and aggregate demand data from the in-memory cache.

    Args:
        item        : filter by item name (None = all items)
        aggregation : 'day', 'week', or 'month'
    """
    df = load_all_demand_data().copy()

    if item:
        df = df[df["item"] == item]

    if df.empty:
        return df

    freq_map = {"week": "W", "month": "ME", "day": None}

    if aggregation in ("week", "month"):
        df = (
            df.groupby(["item", pd.Grouper(key="date", freq=freq_map[aggregation])])
            ["demand"].sum()
            .reset_index()
        )
    else:
        df = (
            df.groupby(["item", "date"])["demand"]
            .sum()
            .reset_index()
        )

    return df.sort_values(["item", "date"]).reset_index(drop=True)


def get_available_items() -> list:
    """Return list of unique item names from the cached dataset."""
    df = load_all_demand_data()
    return sorted(df["item"].unique().tolist())

