"""Initialize local tables and demo data, then start the desktop login."""

import logging
import tkinter as tk

from sqlalchemy.exc import SQLAlchemyError

from pawpos.db.base import check_connection, init_db
from pawpos.db.seed import seed_database
from pawpos.ui.app import run_app


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = check_connection()
    if not result.success:
        logging.error(result.message)
        return 1
    logging.info(result.message)
    try:
        init_db()
        seed_database()
    except SQLAlchemyError:
        logging.error(
            "Cannot initialize the database. Check the database user's table privileges and schema."
        )
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
