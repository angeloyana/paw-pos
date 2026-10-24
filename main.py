"""Phase 0 startup check; the desktop login is introduced in Phase 1."""

import logging

from pawpos.db.base import check_connection, init_db


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = check_connection()
    if not result.success:
        logging.error(result.message)
        return 1
    logging.info(result.message)
    init_db()
    logging.info("Project setup ready. Desktop login is planned for Phase 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
