import structlog
from rich import print

from pytemplate.util.env_aware_logging import setup_env_aware_logging


logger = structlog.get_logger(__name__)

if __name__ == "__main__":
    setup_env_aware_logging("pytemplate", "dev")
    logger.info("Starting application")
    print("Hello, World!")
