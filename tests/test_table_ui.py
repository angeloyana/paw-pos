from tkinter import font

import pytest
import ttkbootstrap as ttk

from pawpos.services import settings_service
from pawpos.ui.dialogs.customer_picker import CustomerPicker
from pawpos.ui.dialogs.held_list import HeldListDialog
from pawpos.ui.dialogs.refund_status import RefundStatusDialog
from pawpos.ui.widgets.table import TableView
from tests.test_catalog_ui import owner_screen


def test_striping_tracks_row_changes_without_losing_tags_or_selection(app):
    table = TableView(app, columns=("name",), show="headings")
    table.tag_configure("warning", foreground="#ff0000")
    for key in ("a", "b", "c"):
        table.insert("", "end", iid=key, values=(key,), tags=("warning",))
    table.selection_set("c")
    table.focus("c")
    app.update()

    def check():
        for index, key in enumerate(table.get_children()):
            assert table.item(key, "tags") == ("warning", table.STRIPES[index % 2])
        assert table.selection() == ("c",)
        assert table.focus() == "c"

    check()
    table.delete("a")
    table.insert("", 0, iid="d", values=("d",), tags=("warning",))
    table.move("c", "", 0)
    app.update()
    check()
    table.delete(*table.get_children())
    table.insert("", "end", iid="new")
    app.update()
    assert table.item("new", "tags") == (table.STRIPES[0],)


def test_all_themes_preserve_inventory_warning_rows_and_selection(app):
    screen = owner_screen(app, "Inventory")
    table = screen.overview_tree
    rows = table.get_children()
    warning = next(row for row in rows if "low" in table.item(row, "tags"))
    table.selection_set(warning)
    table.focus(warning)
    for theme in settings_service.theme_names():
        app.apply_theme(theme)
        app.update()
        colors = app.style.colors
        assert table.get_children() == rows
        assert table.selection() == (warning,)
        assert table.focus() == warning
        assert "low" in table.item(warning, "tags")
        assert str(table.tag_configure("low", "foreground")) == colors.warning
        assert (
            str(table.tag_configure(table.STRIPES[0], "background")) == colors.inputbg
        )
        assert (
            str(table.tag_configure(table.STRIPES[1], "background")) != colors.inputbg
        )
        assert app.style.lookup(table.STYLE, "background", ("selected",)) == (
            colors.selectbg
        )
        assert app.style.lookup(table.STYLE, "foreground", ("selected",)) == (
            colors.selectfg
        )


@pytest.mark.parametrize(
    "page",
    [
        "Dashboard",
        "Products",
        "Categories",
        "Inventory",
        "Customers",
        "Sales History",
        "Refunds",
        "Users",
        "POS",
    ],
)
def test_every_workspace_table_uses_shared_style(app, page):
    screen = owner_screen(app, page)

    def tables(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Treeview):
                yield child
            yield from tables(child)

    found = list(tables(screen))
    assert found
    for table in found:
        assert isinstance(table, TableView)
        assert table.cget("style") == table.STYLE
        assert int(app.style.lookup(table.STYLE, "rowheight")) >= 32


def test_table_dialogs_follow_theme_and_close_with_pending_row_updates(app):
    pos = owner_screen(app, "POS")
    for dialog_type in (CustomerPicker, HeldListDialog, RefundStatusDialog):
        dialog = dialog_type(pos)
        table = next(
            child for child in descendants(dialog) if isinstance(child, TableView)
        )
        table.insert("", "end", values=("Long product or customer name " * 5,))
        app.apply_theme("darkly")
        app.update()
        assert str(table.tag_configure(table.STRIPES[0], "background")) == (
            app.style.colors.inputbg
        )
        table.insert("", "end")
        dialog.destroy()
        app.update()


@pytest.mark.parametrize("page", ["Products", "POS"])
def test_narrow_column_headers_remain_readable(app, page):
    screen = owner_screen(app, page)
    table = screen.tree if page == "Products" else screen.table
    heading_style = f"{table.STYLE}.Heading"
    heading_font = font.Font(app, font=app.style.lookup(heading_style, "font"))
    padding = app.tk.splitlist(app.style.lookup(heading_style, "padding"))
    horizontal_padding = int(padding[0]) * 2
    for column in table.cget("columns"):
        assert table.column(column, "width") >= (
            heading_font.measure(table.heading(column, "text")) + horizontal_padding
        )


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def test_row_height_accommodates_large_fonts(app):
    table = TableView(app)
    table._body_font.configure(size=24)
    table.refresh_theme()
    assert int(app.style.lookup(table.STYLE, "rowheight")) >= (
        table._body_font.metrics("linespace") + 12
    )
    table.destroy()
    # Destroying a table must not leave a deleted named font in the shared style.
    assert (
        font.Font(app, font=app.style.lookup(table.STYLE, "font")).metrics("linespace")
        > 0
    )
