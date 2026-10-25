"""Calendar-only ISO date input shared by owner workspaces."""

import tkinter as tk
from datetime import date

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import DatePickerDialog


class _CalendarDialog(DatePickerDialog):
    def __init__(self, parent, startdate):
        # The library returns startdate even on cancellation; track actual choice.
        self.selection = None
        super().__init__(parent=parent, startdate=startdate, title="Choose date")

    def _setup_calendar(self):
        super()._setup_calendar()
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.focus_set()

    def _on_date_selected(self, row, col):
        self.selection = self.monthdates[row][col]
        super()._on_date_selected(row, col)

    def _set_window_position(self):
        super()._set_window_position()
        # Keep the popup within the screen when a filter sits near its edge.
        self.root.update_idletasks()
        x = max(
            0,
            min(
                self.root.winfo_x(),
                self.root.winfo_screenwidth() - self.root.winfo_width(),
            ),
        )
        y = max(
            0,
            min(
                self.root.winfo_y(),
                self.root.winfo_screenheight() - self.root.winfo_height(),
            ),
        )
        self.root.geometry(f"+{x}+{y}")


class DatePicker(ttk.Frame):
    def __init__(self, parent, textvariable, *, allow_clear=False):
        super().__init__(parent)
        self.variable = textvariable
        self.entry = ttk.Entry(
            self, textvariable=textvariable, state="readonly", width=12
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.calendar_button = ttk.Button(
            self, text="Calendar", command=self.open_calendar, takefocus=True
        )
        self.calendar_button.pack(side="left", padx=(4, 0))
        self.clear_button = None
        if allow_clear:
            self.clear_button = ttk.Button(
                self,
                text="Clear",
                command=lambda: self.variable.set(""),
                takefocus=True,
            )
            self.clear_button.pack(side="left", padx=(4, 0))
        self.entry.bind("<Return>", self._open_key)
        self.entry.bind("<space>", self._open_key)
        self.calendar_button.bind("<Return>", self._open_key)
        if self.clear_button is not None:
            self.clear_button.bind("<Return>", self._clear_key)

    def _open_key(self, _event):
        self.open_calendar()
        return "break"

    def _clear_key(self, _event):
        self.variable.set("")
        return "break"

    def open_calendar(self):
        value = self.variable.get()
        try:
            startdate = date.fromisoformat(value) if value else date.today()
        except ValueError:
            startdate = date.today()
        previous_focus = self.focus_get()
        previous_grab = self.grab_current()
        try:
            dialog = _CalendarDialog(self.calendar_button, startdate)
            if dialog.selection is not None:
                self.variable.set(dialog.selection.isoformat())
        finally:
            try:
                if previous_grab is not None and previous_grab.winfo_exists():
                    previous_grab.grab_set()
                target = previous_focus or self.calendar_button
                if target.winfo_exists():
                    target.focus_set()
            except tk.TclError:
                pass  # The app may have closed while the calendar was open.
