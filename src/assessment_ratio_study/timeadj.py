"""Time adjustment of sale prices to the date of the roll.

In a moving market, a sale from March and a sale from November are not on the same footing
against an assessment set on January 1. This module estimates a yearly market trend and
restates each sale price at the valuation date. The trend can be given or estimated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps

DAYS_PER_YEAR = 365.25


@dataclass(frozen=True)
class TimeAdjustment:
    annual_pct: float  # yearly price growth, in percent
    valuation_date: str
    method: str  # "given" or "estimated"
    n_used: int  # sales used to estimate the trend (0 when given)


def _years_from(dates: pd.Series, origin: pd.Timestamp) -> np.ndarray:
    return ((dates - origin).dt.days / DAYS_PER_YEAR).to_numpy(dtype=float)


def estimate_annual_pct(df: pd.DataFrame) -> tuple[float, int]:
    """Yearly trend from how the sale-price-to-assessed ratio drifts through the period.

    Valid when assessments did not change during the sale period, which is the normal case
    for a single assessment year. Uses a Theil-Sen slope of log(price / assessed) on time, so a
    few bad sales do not drag the estimate. Returns (percent per year, sales used)."""
    d = df[df["sale_price"].notna() & (df["sale_price"] > 0) & (df["assessed_value"] > 0)].copy()
    if "arms_length" in d.columns:
        flag = d["arms_length"].astype(str).str.strip().str.lower()
        d = d[~flag.isin({"n", "no", "false", "0"})]
    d["when"] = pd.to_datetime(d["sale_date"], errors="coerce")
    d = d.dropna(subset=["when"])
    if len(d) < 30:
        raise ValueError("need at least 30 dated arm's-length sales to estimate a trend")
    x = _years_from(d["when"], d["when"].min())
    y = np.log(d["sale_price"].to_numpy(dtype=float) / d["assessed_value"].to_numpy(dtype=float))
    slope = float(sps.theilslopes(y, x)[0])
    return 100.0 * (float(np.exp(slope)) - 1.0), len(d)


def adjust(
    df: pd.DataFrame, annual_pct: float, valuation_date: str | None = None
) -> tuple[pd.DataFrame, TimeAdjustment]:
    """Restate sale prices at `valuation_date` (default: earliest sale date).

    price_adj = price / (1 + g) ** years, where years is the time from the valuation date to
    the sale. Original prices are kept in `sale_price_raw`."""
    out = df.copy()
    when = pd.to_datetime(out["sale_date"], errors="coerce")
    origin = pd.Timestamp(valuation_date) if valuation_date else when.min()
    years = ((when - origin).dt.days / DAYS_PER_YEAR).to_numpy(dtype=float)
    factor = (1.0 + annual_pct / 100.0) ** np.nan_to_num(years, nan=0.0)
    out["sale_price_raw"] = out["sale_price"]
    out["sale_price"] = out["sale_price"] / factor
    return out, TimeAdjustment(annual_pct, origin.strftime("%Y-%m-%d"), "given", 0)
