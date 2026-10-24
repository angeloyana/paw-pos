import logging
from unittest.mock import patch

from pawpos.core.logging_setup import configure_logging
from pawpos.ui.startup import show_startup_error


def test_utf8_file_logging_is_idempotent_and_keeps_existing_handlers(tmp_path):
    path = tmp_path / "pawpos.log"
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        configure_logging(path)
        configure_logging(path)
        matching = [
            handler
            for handler in root.handlers
            if isinstance(handler, logging.FileHandler)
            and handler.baseFilename == str(path)
        ]
        assert len(matching) == 1
        for handler in original_handlers:
            assert handler in root.handlers
        # Pytest owns the root level; test file delivery without changing it globally.
        logging.getLogger("pawpos.test").warning("Receipt display: ₱130.63")
        matching[0].flush()
        assert "WARNING pawpos.test: Receipt display: ₱130.63" in path.read_text(
            encoding="utf-8"
        )
    finally:
        for handler in list(root.handlers):
            if handler not in original_handlers:
                root.removeHandler(handler)
                handler.close()


def test_unwritable_log_falls_back_without_stopping_startup(tmp_path, caplog):
    configure_logging(tmp_path / "missing" / "pawpos.log")
    assert "Diagnostic messages remain in the console" in caplog.text


def test_startup_error_survives_no_display():
    import tkinter as tk

    with patch("pawpos.ui.startup.tk.Tk", side_effect=tk.TclError("No display")):
        show_startup_error("Check MySQL settings.")


def test_startup_error_owns_dialog_and_destroys_temporary_root(app):
    from pawpos.ui import startup

    roots = []
    real_tk = startup.tk.Tk

    def create():
        root = real_tk()
        roots.append(root)
        return root

    with (
        patch.object(startup.tk, "Tk", create),
        patch.object(startup.messagebox, "showerror") as dialog,
    ):
        show_startup_error("Check MySQL settings.")
    assert dialog.call_args.args == ("PawPOS cannot start", "Check MySQL settings.")
    assert dialog.call_args.kwargs["parent"] is roots[0]
    assert roots[0] not in app.children.values()
    # Destroyed interpreters cannot answer Tk widget commands.
    import tkinter as tk

    import pytest

    with pytest.raises(tk.TclError):
        roots[0].winfo_exists()
