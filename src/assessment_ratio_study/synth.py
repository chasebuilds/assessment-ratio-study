"""Seeded synthetic county with planted assessment problems.

Everything here is generated. Parcel IDs, neighborhood names and prices are made up; no
real owners, addresses or parcels are involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# name, parcels, median price, planted problem (None = clean)
NEIGHBORHOODS: list[tuple[str, int, float, str | None]] = [
    ("Oak Ridge", 420, 210_000, None),
    ("Mill Creek", 420, 165_000, None),
    ("Elm Park", 420, 140_000, None),
    ("Cedar Flats", 420, 120_000, None),
    ("Maple Hills", 420, 260_000, "regressive"),
    ("Old Town", 420, 95_000, "low_median"),
    ("Riverbend", 420, 150_000, "high_cod"),
    ("Ridgeview", 420, 180_000, "sales_chasing"),
]
PLANT_TO_METRIC = {
    "regressive": "prb",
    "low_median": "median",
    "high_cod": "cod",
    "sales_chasing": "chasing",
}
SALE_RATE = 0.22
N_GROSS_ERRORS = 14  # unflagged typos: price off by a factor of 10
N_SUBTLE = 10  # unflagged non-arm's-length sales at about half of market


@dataclass
class Truth:
    planted: dict[str, str] = field(default_factory=dict)  # stratum -> problem
    clean_strata: list[str] = field(default_factory=list)
    flagged_non_arms: list[str] = field(default_factory=list)
    gross_errors: list[str] = field(default_factory=list)
    subtle_non_arms: list[str] = field(default_factory=list)


def generate(seed: int = 42, trend: float = 0.0) -> tuple[pd.DataFrame, Truth]:
    """`trend` is the yearly market growth: sale prices drift up through the year while the
    assessment roll (set at 2025-01-01) stays put, as it does in a real assessment year."""
    rng = np.random.default_rng(seed)
    parts: list[pd.DataFrame] = []
    truth = Truth()
    pid = 0

    def build(
        name: str, cls: str, n: int, med_price: float, sd_price: float, problem: str | None
    ) -> pd.DataFrame:
        nonlocal pid
        price = med_price * np.exp(rng.normal(0.0, sd_price, n))
        noise = np.exp(rng.normal(0.0, 0.075, n))
        base = {"residential": 0.97, "commercial": 0.96, "vacant_land": 0.95}[cls]
        ratio = base * noise
        if problem == "regressive":
            ratio = base * noise * (price / np.median(price)) ** -0.18
        elif problem == "low_median":
            ratio = 0.80 * noise
        elif problem == "high_cod":
            ratio = base * np.exp(rng.normal(0.0, 0.24, n))
        elif cls == "commercial":
            ratio = base * np.exp(rng.normal(0.0, 0.11, n))
        elif cls == "vacant_land":
            ratio = base * np.exp(rng.normal(0.0, 0.14, n))
        sold = rng.random(n) < SALE_RATE
        assessed = price * ratio
        prior = assessed / (1.03 * np.exp(rng.normal(0.0, 0.02, n)))
        if problem == "sales_chasing":
            # roll sits at 0.88 of market, but parcels that just sold are reset to the price
            low = price * 0.88 * np.exp(rng.normal(0.0, 0.07, n))
            prior = low / (1.03 * np.exp(rng.normal(0.0, 0.02, n)))
            assessed = np.where(sold, price * np.exp(rng.normal(0.0, 0.02, n)), low)
        ids = [f"P-{pid + i:06d}" for i in range(n)]
        pid += n
        year = (
            np.clip(rng.normal(1976, 24, n), 1900, 2024).round()
            if cls != "vacant_land"
            else np.full(n, np.nan)
        )
        days = rng.integers(0, 365, n)
        dates = pd.to_datetime("2025-01-01") + pd.to_timedelta(days, unit="D")
        sale_value = price * (1.0 + trend) ** (days / 365.25)
        df = pd.DataFrame(
            {
                "parcel_id": ids,
                "neighborhood": name,
                "property_class": cls,
                "year_built": year,
                "sale_date": np.where(sold, dates.strftime("%Y-%m-%d"), ""),
                "sale_price": np.where(sold, sale_value.round(-2), np.nan),
                "sale_type": np.where(sold, "arms_length", ""),
                "arms_length": np.where(sold, "Y", ""),
                "assessed_prior": prior.round(-2),
                "assessed_value": assessed.round(-2),
            }
        )
        return df

    for name, n, med, problem in NEIGHBORHOODS:
        parts.append(
            build(name, "residential", n, med, 0.45 if problem == "regressive" else 0.35, problem)
        )
        if problem:
            truth.planted[name] = problem
        else:
            truth.clean_strata.append(name)
    parts.append(build("Downtown Core", "commercial", 300, 420_000, 0.5, None))
    parts.append(build("Rural Tracts", "vacant_land", 300, 38_000, 0.5, None))
    truth.clean_strata += ["commercial", "vacant_land"]
    df = pd.concat(parts, ignore_index=True)

    sold_idx = df.index[df["sale_price"].notna() & (df["property_class"] == "residential")]
    pick = rng.choice(sold_idx, size=int(len(sold_idx) * 0.05), replace=False)
    types = rng.choice(["foreclosure", "family", "estate"], size=len(pick))
    for i, t in zip(pick, types, strict=True):
        df.loc[i, "sale_price"] = round(df.loc[i, "sale_price"] * rng.uniform(0.3, 0.6), -2)
        df.loc[i, "sale_type"], df.loc[i, "arms_length"] = t, "N"
    truth.flagged_non_arms = df.loc[pick, "parcel_id"].tolist()

    rest = np.setdiff1d(sold_idx, pick)
    chosen = rng.choice(rest, size=N_GROSS_ERRORS + N_SUBTLE, replace=False)
    for i in chosen[:N_GROSS_ERRORS]:
        df.loc[i, "sale_price"] = df.loc[i, "sale_price"] * rng.choice([10.0, 0.1])
    for i in chosen[N_GROSS_ERRORS:]:
        df.loc[i, "sale_price"] = round(df.loc[i, "sale_price"] * rng.uniform(0.45, 0.6), -2)
    truth.gross_errors = df.loc[chosen[:N_GROSS_ERRORS], "parcel_id"].tolist()
    truth.subtle_non_arms = df.loc[chosen[N_GROSS_ERRORS:], "parcel_id"].tolist()
    return df, truth
