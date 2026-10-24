import unittest
from unittest.mock import patch

import main
from pawpos.db.base import ConnectionCheck


class StartupTests(unittest.TestCase):
    def test_unavailable_database_stops_before_initialization(self):
        with (
            patch.object(
                main,
                "check_connection",
                return_value=ConnectionCheck(False, "Unavailable"),
            ),
            patch.object(main, "init_db") as initialize,
            self.assertLogs(level="ERROR"),
        ):
            self.assertEqual(main.main(), 1)
        initialize.assert_not_called()

    def test_connected_database_is_initialized(self):
        with (
            patch.object(
                main,
                "check_connection",
                return_value=ConnectionCheck(True, "Connected"),
            ),
            patch.object(main, "init_db") as initialize,
            self.assertLogs(level="INFO"),
        ):
            self.assertEqual(main.main(), 0)
        initialize.assert_called_once_with()
