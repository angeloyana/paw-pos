"""Shortcut help that closes cleanly on navigation and widget destruction."""

try:
    from ttkbootstrap.widgets import ToolTip
except ImportError:  # ttkbootstrap 1.10 keeps ToolTip in its original module.
    from ttkbootstrap.tooltip import ToolTip


def add_tooltip(widget, text: str) -> ToolTip:
    tooltip = ToolTip(widget, text=text, delay=400, wraplength=320)
    widget.tooltip = tooltip
    widget.bind("<Unmap>", lambda _event: tooltip.leave(), add="+")
    widget.bind("<Destroy>", lambda _event: tooltip.leave(), add="+")
    return tooltip
