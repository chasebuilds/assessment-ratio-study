"""Hand-checked examples. Each expected value is worked out in the comment above it."""

import numpy as np
import pytest

from assessment_ratio_study import stats

# Five sales at 100, 200, 300, 400, 500 with assessed values 80, 180, 300, 440, 600.
# Ratios: 0.8, 0.9, 1.0, 1.1, 1.2.
S = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
A = np.array([80.0, 180.0, 300.0, 440.0, 600.0])
R = A / S


def test_median_and_mean() -> None:
    # sorted middle value is 1.0; mean is (0.8+0.9+1.0+1.1+1.2)/5 = 1.0
    assert stats.median_ratio(R) == pytest.approx(1.0)
    assert stats.mean_ratio(R) == pytest.approx(1.0)


def test_weighted_mean() -> None:
    # sum assessed 1600 / sum sale 1500 = 1.066666...
    assert stats.weighted_mean_ratio(A, S) == pytest.approx(1600 / 1500)


def test_cod() -> None:
    # abs deviations from median 1.0: .2 .1 0 .1 .2 -> mean .12 -> COD = 100 * .12 / 1.0 = 12
    assert stats.cod(R) == pytest.approx(12.0)


def test_cod_scales_by_median() -> None:
    # ratios 0.4 0.45 0.5 0.55 0.6: median .5, mean abs dev .06 -> 100 * .06 / .5 = 12
    assert stats.cod(np.array([0.4, 0.45, 0.5, 0.55, 0.6])) == pytest.approx(12.0)


def test_prd() -> None:
    # mean ratio 1.0 / weighted mean 1.066667 = 0.9375
    assert stats.prd(A, S) == pytest.approx(0.9375)


def test_prd_is_one_when_ratio_constant() -> None:
    assert stats.prd(S * 0.9, S) == pytest.approx(1.0)


def test_prb_zero_for_constant_ratio() -> None:
    res = stats.prb(S * 0.9, S)
    assert res is not None
    assert res.prb == pytest.approx(0.0, abs=1e-12)
    assert not res.significant


def test_prb_hand_example() -> None:
    # Sales 100, 200, 400, 800, 1600 with ratios .9 .95 1.0 1.05 1.1 (median 1.0).
    # Assessed = 90, 190, 400, 840, 1760. Value proxy 0.5*S + 0.5*A/1.0 = 95, 195, 400, 820, 1680.
    # x = log2(proxy) = 6.570, 7.607, 8.644, 9.680, 10.714 (mean 8.643); y = ratio - 1.
    # slope = sum(dx*y) / sum(dx^2) = 0.5176 / 10.69 = 0.04843
    s = np.array([100.0, 200.0, 400.0, 800.0, 1600.0])
    a = np.array([90.0, 190.0, 400.0, 840.0, 1760.0])
    res = stats.prb(a, s)
    assert res is not None
    assert res.prb == pytest.approx(0.0484, abs=2e-4)
    assert res.ci_low < res.prb < res.ci_high


def test_prb_negative_when_high_prices_assessed_low() -> None:
    s = np.array([100.0, 200.0, 400.0, 800.0, 1600.0])
    a = np.array([110.0, 205.0, 400.0, 760.0, 1440.0])  # ratios fall as price rises
    res = stats.prb(a, s)
    assert res is not None
    assert res.prb < 0


def test_prb_matches_numpy_polyfit() -> None:
    rng = np.random.default_rng(1)
    s = np.exp(rng.normal(12, 0.4, 200))
    a = s * np.exp(rng.normal(0, 0.1, 200)) * (s / np.median(s)) ** -0.1
    res = stats.prb(a, s)
    assert res is not None
    med = np.median(a / s)
    x = np.log2(0.5 * s + 0.5 * a / med)
    slope = np.polyfit(x, (a / s - med) / med, 1)[0]
    assert res.prb == pytest.approx(slope)


def test_prb_needs_three_sales() -> None:
    assert stats.prb(S[:2], S[:2]) is None
