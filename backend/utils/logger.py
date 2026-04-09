"""
Configures standard logging for the entire application.
Outputs formatted logs to both console and data/app.log.
"""
import logging
import os
import sys

def setup_logging():
    # Configure the root logger to cascade settings down to submodule loggers
    logger = logging.getLogger()
    
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    if not logger.handlers:
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler
        log_dir = os.path.join(os.path.dirname(__file__), "../../data")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")
        
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logging.getLogger("job_hunter")

# Initialize automatically when imported
logger = setup_logging()
