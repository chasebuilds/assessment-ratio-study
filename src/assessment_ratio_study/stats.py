"""Ratio study statistics: median, weighted mean, COD, PRD, PRB.

Definitions follow the IAAO Standard on Ratio Studies (see README for the citation).
Formulas are written out from their standard definitions, not copied from the text.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import stats as sps

Arr = NDArray[np.float64]


def median_ratio(ratios: Arr) -> float:
    return float(np.median(ratios))


def mean_ratio(ratios: Arr) -> float:
    return float(np.mean(ratios))


def weighted_mean_ratio(assessed: Arr, sale: Arr) -> float:
    """Sum of assessed values over sum of sale prices."""
    return float(assessed.sum() / sale.sum())


def cod(ratios: Arr) -> float:
    """Coefficient of dispersion, in percent: mean absolute deviation from the median,
    divided by the median, times 100."""
    med = np.median(ratios)
    return float(100.0 * np.mean(np.abs(ratios - med)) / med)


def prd(assessed: Arr, sale: Arr) -> float:
    """Price-related differential: mean ratio divided by weighted mean ratio."""
    return mean_ratio(assessed / sale) / weighted_mean_ratio(assessed, sale)


@dataclass(frozen=True)
class PRBResult:
    prb: float
    se: float
    ci_low: float
    ci_high: float
    p_value: float

    @property
    def significant(self) -> bool:
        return not (self.ci_low <= 0.0 <= self.ci_high)


def prb(assessed: Arr, sale: Arr, confidence: float = 0.95) -> PRBResult | None:
    """Price-related bias.

    Regress y = (ratio - median) / median on x = log2(value proxy), where the proxy is
    0.5 * sale + 0.5 * assessed / median. The slope is the change in the ratio (as a
    share of the median) each time value doubles. Negative means higher-priced
    properties are assessed at lower ratios (regressive). Returns None if there are
    fewer than 3 sales or no spread in value.
    """
    n = len(sale)
    if n < 3:
        return None
    ratios = assessed / sale
    med = float(np.median(ratios))
    proxy = 0.5 * sale + 0.5 * assessed / med
    x = np.log2(proxy)
    y = (ratios - med) / med
    dx = x - x.mean()
    sxx = float((dx**2).sum())
    if sxx == 0.0:
        return None
    slope = float((dx * (y - y.mean())).sum() / sxx)
    resid = y - (y.mean() + slope * dx)
    dof = n - 2
    se = float(np.sqrt((resid**2).sum() / dof / sxx))
    tcrit = float(sps.t.ppf(0.5 + confidence / 2.0, dof))
    if se > 0:
        p = float(2.0 * sps.t.sf(abs(slope / se), dof))
    else:
        p = 1.0 if slope == 0.0 else 0.0
    return PRBResult(slope, se, slope - tcrit * se, slope + tcrit * se, p)
