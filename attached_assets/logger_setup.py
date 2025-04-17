# logger_setup.py
import logging
import sys
from logging.handlers import RotatingFileHandler

LOG_FILENAME = 'multi_camera_app.log'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'

def setup_logging(log_level=logging.INFO):
    """Configures the application's logging."""
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Prevent duplicate handlers if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)

    # File Handler (Rotating)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILENAME,
            maxBytes=5*1024*1024, # 5 MB
            backupCount=3
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(file_handler)
    except PermissionError:
        logging.warning(f"No permission to write log file at {LOG_FILENAME}")
    except Exception as e:
        logging.error(f"Failed to set up file logging: {e}")

    logging.info("Logging initialized.")

# --- Optional: Custom Handler for GUI Log Widget ---
class QTextEditLogHandler(logging.Handler):
    """A logging handler that emits a Qt signal."""
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)