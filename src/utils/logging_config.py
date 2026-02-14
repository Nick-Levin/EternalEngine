"""Logging configuration."""
import logging
import sys
from pathlib import Path
import structlog

from src.core.config import logging_config


def setup_logging():
    """Configure structured logging."""
    # Create logs directory
    log_path = Path(logging_config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, logging_config.log_level.upper())
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Add file handler
    file_handler = logging.FileHandler(logging_config.log_file)
    file_handler.setLevel(getattr(logging, logging_config.log_level.upper()))
    
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
