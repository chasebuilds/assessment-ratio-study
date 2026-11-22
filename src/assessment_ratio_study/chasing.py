"""Sales-chasing check: did parcels that sold get reassessed more than parcels that did not?

When assessors raise values only on parcels that just sold, the ratio study looks better
than the roll really is, because unsold parcels are not held to the same standard.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps


@dataclass(frozen=True)
class ChasingConfig:
    min_gap_points: float = 3.0  # sold median change minus unsold median change, in % points
    alpha: float = 0.01
    min_group: int = 20


def _row(label: str, sold: pd.Series, unsold: pd.Series, cfg: ChasingConfig) -> dict[str, object]:
    out: dict[str, object] = {
        "group": label,
        "n_sold": len(sold),
        "n_unsold": len(unsold),
        "median_change_sold_pct": None,
        "median_change_unsold_pct": None,
        "gap_points": None,
        "p_value": None,
        "flag": "not enough data",
    }
    if len(sold) < cfg.min_group or len(unsold) < cfg.min_group:
        return out
    ms, mu = float(np.median(sold)), float(np.median(unsold))
    p = float(sps.mannwhitneyu(sold, unsold, alternative="greater").pvalue)
    gap = ms - mu
    out.update(
        median_change_sold_pct=ms,
        median_change_unsold_pct=mu,
        gap_points=gap,
        p_value=p,
        flag="SALES CHASING SUSPECTED" if gap >= cfg.min_gap_points and p < cfg.alpha else "ok",
    )
    return out


def check(
    sales: pd.DataFrame, unsold: pd.DataFrame, cfg: ChasingConfig | None = None
) -> pd.DataFrame:
    """`sales` is the sold parcels, `unsold` the parcels with no sale in the period.

    Needs `assessed_prior` and `assessed_value` on both. Compared within neighborhood so a
    market-wide trend does not look like chasing."""
    cfg = cfg or ChasingConfig()
    if "assessed_prior" not in sales.columns or "assessed_prior" not in unsold.columns:
        return pd.DataFrame()
    s = sales.dropna(subset=["assessed_prior"]).copy()
    u = unsold.dropna(subset=["assessed_prior"]).copy()
    for df in (s, u):
        df["chg"] = 100.0 * (df["assessed_value"] / df["assessed_prior"] - 1.0)
    rows = [_row("all parcels", s["chg"], u["chg"], cfg)]
    for nb in sorted(set(s["neighborhood"]) | set(u["neighborhood"])):
        rows.append(
            _row(
                str(nb),
                s.loc[s["neighborhood"] == nb, "chg"],
                u.loc[u["neighborhood"] == nb, "chg"],
                cfg,
            )
        )
    return pd.DataFrame(rows)
