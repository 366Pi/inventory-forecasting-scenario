import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import urllib

load_dotenv()

logger = logging.getLogger(__name__)

def get_engine():
    server   = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    driver   = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

    params = urllib.parse.quote_plus(
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
    )

    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)
    logger.info("SQLAlchemy engine created.")
    return engine

def test_connection():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Connection successful:", result.fetchone())
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
