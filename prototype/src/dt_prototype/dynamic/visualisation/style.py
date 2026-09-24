"""Shared plotting style: validated categorical palette and axis styling.

Colors follow the entity (heating is always red, cooling always blue, ...)
so a series never changes hue between figures. The palette is a validated
colorblind-safe set (adjacent-pair CVD distance and lightness band checked);
identity is never encoded by color alone — every multi-series axes gets a
legend.
"""

from __future__ import annotations

from matplotlib.axes import Axes

# Fixed entity → color mapping (validated palette, light surface)
SERIES_COLORS: dict[str, str] = {
    "heating": "#e34948",  # red
    "cooling": "#2a78d6",  # blue
    "dhw": "#eda100",  # yellow
    "electricity": "#4a3aa7",  # violet
    "pv": "#1baf7a",  # aqua
    "gas": "#eb6834",  # orange
    "temperature": "#0b0b0b",  # primary ink
    "outdoor": "#898781",  # muted
    "humidity": "#1baf7a",  # aqua
}

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"


def style_axes(ax: Axes) -> None:
    """Apply the house style to one axes: recessive hairline grid, muted
    spines and tick labels, no top/right spines.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axes to style in place.
    """
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRIDLINE, linewidth=0.8, axis="y")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)
