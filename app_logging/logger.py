import sys
import json
from loguru import logger
import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Remove default logger
logger.remove()

# Add a human-readable console logger
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Add a structured JSON file logger for audit trails
def serialize(record):
    subset = {
        "timestamp": record["time"].timestamp(),
        "time": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "extra": record["extra"],
    }
    return json.dumps(subset)

def patching(record):
    record["extra"]["serialized"] = serialize(record)

logger = logger.patch(patching)
logger.add("logs/audit.jsonl", format="{extra[serialized]}", level="INFO", rotation="1 day")

def get_logger(name: str):
    return logger.bind(module=name)
