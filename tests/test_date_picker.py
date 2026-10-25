import tkinter as tk
from datetime import date
from unittest.mock import patch

import pytest

from pawpos.ui.widgets.date_picker import DatePicker, _CalendarDialog
from tests.test_catalog_ui import owner_screen


@pytest.mark.parametrize("initial", ["", "2024-02-29"])
@pytest.mark.parametrize("action", ["select", "escape", "close"])
def test_calendar_selection_and_cancellation(app, initial, action):
    variable = tk.StringVar(app, value=initial)
    picker = DatePicker(app, variable, allow_clear=True)
    picker.place(x=20, y=20)
    app.update()
    picker.calendar_button.focus_force()
    app.update()
    original_setup = _CalendarDialog._setup_calendar

    def setup(dialog):
        original_setup(dialog)
        assert dialog.startdate == (
            date.fromisoformat(initial) if initial else date.today()
        )

        def act():
            if action == "select":
                dialog.date = date(2024, 2, 1)
                dialog.frm_dates.destroy()
                dialog._draw_calendar()
                row, col = next(
                    (r, c)
                    for r, week in enumerate(dialog.monthdates)
                    for c, day in enumerate(week)
                    if day == date(2024, 2, 29)
                )
                dialog._on_date_selected(row, col)
            elif action == "escape":
                dialog.root.event_generate("<Escape>")
            else:
                dialog.root.tk.call(dialog.root.protocol("WM_DELETE_WINDOW"))

        dialog.root.after(50, act)

    with patch.object(_CalendarDialog, "_setup_calendar", setup):
        picker.open_calendar()
    app.update()
    assert variable.get() == ("2024-02-29" if action == "select" else initial)
    assert app.focus_get() == picker.calendar_button
    assert app.grab_current() is None
    picker.destroy()


@pytest.mark.parametrize("theme", ["cosmo", "darkly"])
def test_minimum_window_layout_and_themed_calendar(app, theme):
    screen = owner_screen(app, "Inventory")
    app.state("normal")
    app.geometry("1280x720+0+0")
    app.apply_theme(theme)
    app.update()

    def fits(widget):
        assert widget.winfo_ismapped()
        assert widget.winfo_rootx() >= app.winfo_rootx()
        assert widget.winfo_rooty() >= app.winfo_rooty()
        assert widget.winfo_rootx() + widget.winfo_width() <= (
            app.winfo_rootx() + app.winfo_width()
        )
        assert widget.winfo_rooty() + widget.winfo_height() <= (
            app.winfo_rooty() + app.winfo_height()
        )
        assert widget.winfo_width() >= widget.winfo_reqwidth()

    screen.notebook.select(1)
    app.update()
    fits(screen.delivery_picker.calendar_button)
    screen.notebook.select(3)
    app.update()
    for picker in screen.history_date_pickers:
        for widget in (picker.entry, picker.calendar_button, picker.clear_button):
            fits(widget)

    app.screen.buttons["Sales History"].invoke()
    app.update()
    screen = app.screen.current_screen
    for picker in screen.date_pickers:
        for widget in (picker.entry, picker.calendar_button, picker.clear_button):
            fits(widget)
    original_setup = _CalendarDialog._setup_calendar
    observed = []

    def setup(dialog):
        original_setup(dialog)

        def inspect():
            try:
                assert dialog.root.winfo_viewable()
                assert dialog.root.winfo_x() >= 0
                assert dialog.root.winfo_y() >= 0
                assert dialog.root.winfo_x() + dialog.root.winfo_width() <= (
                    dialog.root.winfo_screenwidth()
                )
                assert dialog.root.winfo_y() + dialog.root.winfo_height() <= (
                    dialog.root.winfo_screenheight()
                )
                assert app.style.theme.name == theme
                observed.append(True)
            finally:
                dialog.root.destroy()

        dialog.root.after(50, inspect)

    with patch.object(_CalendarDialog, "_setup_calendar", setup):
        screen.date_pickers[-1].open_calendar()
    assert observed == [True]


def test_readonly_clear_and_keyboard(app):
    variable = tk.StringVar(app, value="2024-02-29")
    picker = DatePicker(app, variable, allow_clear=True)
    picker.place(x=20, y=20)
    app.update()
    picker.entry.delete(0, "end")
    picker.entry.insert(0, "bad")
    assert variable.get() == "2024-02-29"
    assert picker.entry.instate(["readonly"])
    picker.clear_button.invoke()
    assert variable.get() == ""
    with patch("pawpos.ui.widgets.date_picker._CalendarDialog") as dialog:
        dialog.return_value.selection = date(2024, 2, 29)
        picker.calendar_button.focus_force()
        app.update()
        picker.calendar_button.event_generate("<Return>")
        app.update()
        assert variable.get() == "2024-02-29"
    picker.clear_button.focus_force()
    app.update()
    picker.clear_button.event_generate("<Return>")
    app.update()
    assert variable.get() == ""
    required = DatePicker(app, variable)
    assert required.clear_button is None
    required.destroy()
    picker.destroy()
