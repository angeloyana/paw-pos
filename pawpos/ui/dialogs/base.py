"""Shared modal behavior and inline service error feedback."""

import logging
import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.errors import PawPOSError

logger = logging.getLogger(__name__)


class ModalDialog(ttk.Toplevel):
    def __init__(self, parent, title: str):
        super().__init__(master=parent)
        self.withdraw()
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.result = None
        self.error = tk.StringVar(self)
        self.body = ttk.Frame(self, padding=20)
        self.body.pack(fill="both", expand=True)
        self.bind("<Escape>", self.cancel_key)

    def cancel_key(self, _event):
        self.destroy()
        return "break"

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
        previous_grab = self.grab_current()
        previous_focus = self.focus_get()
        try:
            self.deiconify()
            self.wait_visibility()
            self.grab_set()
            self.first_input.bind("<Escape>", self.cancel_key)
            # Windows can leave keyboard focus in the owner despite the modal grab.
            self.focus_force()
            self.first_input.focus_set()
            self.wait_window()
        finally:
            # Cancelling a held cart opens a nested reason dialog.
            try:
                if previous_grab is not None and previous_grab.winfo_exists():
                    previous_grab.grab_set()
                if previous_focus is not None and previous_focus.winfo_exists():
                    previous_focus.focus_set()
            except tk.TclError:
                pass  # The root may have closed while a modal window was open.
        return self.result
