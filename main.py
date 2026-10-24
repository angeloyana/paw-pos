"""Initialize local tables and demo data, then start the desktop login."""

import logging
import tkinter as tk

from sqlalchemy.exc import SQLAlchemyError

from pawpos.core.logging_setup import configure_logging
from pawpos.db.base import check_connection, init_db
from pawpos.db.seed import seed_database
from pawpos.ui.app import run_app
from pawpos.ui.startup import show_startup_error


def main() -> int:
    configure_logging()
    result = check_connection()
    if not result.success:
        logging.error(result.message)
        show_startup_error(result.message)
        return 1
    logging.info(result.message)
    try:
        init_db()
        seed_database()
    except SQLAlchemyError:
        message = "Cannot initialize the database. Check the database user's table privileges and schema."
        logging.error(message)
        show_startup_error(message)
        return 1
    try:
        run_app()
    except tk.TclError:
        logging.error(
            "Cannot open PawPOS. Run it in a desktop session with Tk support."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
