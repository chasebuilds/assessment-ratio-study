"""Three charts as PNG bytes: ratio vs price, ratio by neighborhood, sold vs unsold change."""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .pipeline import Result  # noqa: E402

INK = "#2a2019"
ACCENT = "#e2583a"
OK = "#1f9a72"


def _png(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def ratio_vs_price(res: Result) -> bytes:
    s = res.screened.sales
    s = s[s["property_class"] == res.focus_class]
    t = res.targets
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axhspan(
        t.median_low, t.median_high, color=OK, alpha=0.10, label="IAAO median range 0.90-1.10"
    )
    ax.scatter(s["sale_price"], s["ratio"], s=9, alpha=0.45, color="#4a5f7a", linewidths=0)
    x = np.log(s["sale_price"].to_numpy(dtype=float))
    y = s["ratio"].to_numpy(dtype=float)
    k, b = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(np.exp(xs), k * xs + b, color=ACCENT, lw=2, label="trend (higher line = bias)")
    ax.set_xscale("log")
    ax.set_xlabel("Sale price (log scale)")
    ax.set_ylabel("Assessed / sale price")
    ax.set_title(f"Ratio vs sale price, {res.focus_class}", color=INK)
    ax.legend(frameon=False, fontsize=8)
    return _png(fig)


def ratio_by_neighborhood(res: Result) -> bytes:
    s = res.screened.sales
    s = s[s["property_class"] == res.focus_class]
    t = res.targets
    names = sorted(s["neighborhood"].unique())
    data = [s.loc[s["neighborhood"] == n, "ratio"].to_numpy() for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axhspan(t.median_low, t.median_high, color=OK, alpha=0.10)
    ax.boxplot(data, tick_labels=names, showfliers=True, flierprops={"markersize": 2})
    ax.set_ylabel("Assessed / sale price")
    ax.set_title("Ratio by neighborhood (shaded: IAAO median range)", color=INK)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    return _png(fig)


def sold_vs_unsold(res: Result) -> bytes:
    ch = res.chasing
    ch = ch[ch["median_change_sold_pct"].notna()] if len(ch) else ch
    fig, ax = plt.subplots(figsize=(8, 4.6))
    if len(ch):
        pos = np.arange(len(ch))
        ax.bar(
            pos - 0.2,
            ch["median_change_unsold_pct"].astype(float),
            0.4,
            label="unsold",
            color="#9aa7b8",
        )
        ax.bar(
            pos + 0.2, ch["median_change_sold_pct"].astype(float), 0.4, label="sold", color=ACCENT
        )
        ax.set_xticks(pos)
        ax.set_xticklabels(ch["group"], rotation=25, ha="right")
    ax.set_ylabel("Median assessed-value change (%)")
    ax.set_title("Sales-chasing check: sold vs unsold parcels", color=INK)
    ax.legend(frameon=False)
    return _png(fig)


def all_charts(res: Result) -> dict[str, bytes]:
    return {
        "ratio_vs_price.png": ratio_vs_price(res),
        "ratio_by_neighborhood.png": ratio_by_neighborhood(res),
        "sold_vs_unsold.png": sold_vs_unsold(res),
    }
