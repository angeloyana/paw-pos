import tkinter as tk
import unittest
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

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
            patch.object(main, "seed_database") as seed,
            patch.object(main, "run_app") as launch,
            self.assertLogs(level="ERROR"),
        ):
            self.assertEqual(main.main(), 1)
        initialize.assert_not_called()
        seed.assert_not_called()
        launch.assert_not_called()

    def test_connected_database_is_initialized(self):
        with (
            patch.object(
                main,
                "check_connection",
                return_value=ConnectionCheck(True, "Connected"),
            ),
            patch.object(main, "init_db") as initialize,
            patch.object(main, "seed_database") as seed,
            patch.object(main, "run_app") as launch,
            self.assertLogs(level="INFO"),
        ):
            self.assertEqual(main.main(), 0)
        initialize.assert_called_once_with()
        seed.assert_called_once_with()
        launch.assert_called_once_with()

    def test_database_initialization_failure_does_not_launch_desktop(self):
        with (
            patch.object(
                main,
                "check_connection",
                return_value=ConnectionCheck(True, "Connected"),
            ),
            patch.object(
                main,
                "init_db",
                side_effect=OperationalError("", {}, Exception("private detail")),
            ),
            patch.object(main, "run_app") as launch,
            self.assertLogs(level="ERROR") as logs,
        ):
            self.assertEqual(main.main(), 1)
        launch.assert_not_called()
        self.assertNotIn("private detail", " ".join(logs.output))

    def test_unavailable_display_has_friendly_error(self):
        with (
            patch.object(
                main,
                "check_connection",
                return_value=ConnectionCheck(True, "Connected"),
            ),
            patch.object(main, "init_db"),
            patch.object(main, "seed_database"),
            patch.object(main, "run_app", side_effect=tk.TclError("no display")),
            self.assertLogs(level="ERROR") as logs,
        ):
            self.assertEqual(main.main(), 1)
        self.assertIn("desktop session", " ".join(logs.output))
