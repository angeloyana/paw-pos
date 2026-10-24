"""Console and project-local diagnostic logging for desktop startup."""

import logging
from pathlib import Path

from pawpos.config import LOG_PATH


def configure_logging(log_path: Path = LOG_PATH) -> None:
    """Add one UTF-8 file handler without replacing existing console/test handlers."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = logging.getLogger()
    path = Path(log_path).resolve()
    if any(
        isinstance(handler, logging.FileHandler) and handler.baseFilename == str(path)
        for handler in root.handlers
    ):
        return
    try:
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        logging.warning(
            "Cannot write pawpos.log. Diagnostic messages remain in the console."
        )
        return
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)
