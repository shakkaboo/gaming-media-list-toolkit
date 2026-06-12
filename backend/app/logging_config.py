import logging
import sys
from app.config import get_settings

def configure_logging():
    settings = get_settings()
    
    logger = logging.getLogger()
    
    # Avoid duplicate handlers during reload
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(settings.LOG_LEVEL)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(settings.LOG_LEVEL)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    # Silence overly verbose loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
