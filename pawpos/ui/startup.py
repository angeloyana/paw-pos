"""Native startup errors before the themed application exists."""

import tkinter as tk
from tkinter import messagebox

from pawpos.config import SHOP_NAME


def show_startup_error(message: str) -> None:
    """Show an owned error dialog when a display exists; console errors work headlessly."""
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(f"{SHOP_NAME} cannot start", message, parent=root)
    except tk.TclError:
        pass  # Startup also reports this message through console/file logging.
    finally:
        if root is not None:
            root.destroy()
