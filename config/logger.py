import logging
import os
from datetime import datetime

def setup_logger(name: str = "pipeline") -> logging.Logger:
    """
    Sets up a logger that writes to both console and a log file.
    Log files are saved in the logs/ folder with a daily timestamp.
    """
    os.makedirs("logs", exist_ok=True)

    log_filename = f"logs/{name}_{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info(f"Logger initialized — writing to {log_filename}")
    return logger
