"""plotstyle.py -- one look for every figure in sim/antenna/figs (matplotlib).

Categorical colours are the validated default order (blue, orange, aqua, yellow,
magenta, green, violet, red) and are assigned by *entity*, never by rank; text is
always ink, never a series colour; 2 px lines; hairline recessive grid; one y-axis.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
BAND = "#f0efec"          # the 2.400-2.484 GHz band shading (neutral)

# entity -> colour, fixed for the whole document
COLOR = {
    "bat_ifa": SERIES[0],
    "ghost": SERIES[1],
    "bat_dipole": SERIES[2],
    "dn007": SERIES[6],
    "measured": INK,
    "mom": INK,
}


def setup():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.6,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "legend.fontsize": 8,
        "legend.frameon": False,
        "legend.labelcolor": INK,
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def band(ax, lo=2.400, hi=2.4835, label=True):
    ax.axvspan(lo, hi, color=BAND, zorder=0, lw=0)
    if label:
        ax.text(0.5 * (lo + hi), 0.98, "2.4 GHz\nISM", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7, color=INK2)


def stamp(fig, text):
    fig.text(0.995, 0.005, text, ha="right", va="bottom", fontsize=6, color=MUTED)
