"""Shared modal behavior and inline service error feedback."""

import logging
import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.errors import PawPOSError

logger = logging.getLogger(__name__)


class ModalDialog(ttk.Toplevel):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.result = None
        self.error = tk.StringVar(self)
        self.body = ttk.Frame(self, padding=20)
        self.body.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda _event: self.destroy())

    def perform(self, action) -> bool:
        try:
            action()
        except PawPOSError as error:
            self.error.set(str(error))
            return False
        except Exception:
            logger.exception("Dialog operation failed")
            self.error.set("Cannot complete this action. Please try again.")
            return False
        self.error.set("")
        return True

    def show(self):
        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        self.first_input.focus_set()
        self.wait_window()
        return self.result
