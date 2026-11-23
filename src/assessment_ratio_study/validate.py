"""Sale validation screens: non-arm's-length flags, bad rows, duplicates, IQR outliers."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

REQUIRED = ["parcel_id", "neighborhood", "property_class", "sale_price", "assessed_value"]
NON_ARMS_TYPES = {"foreclosure", "family", "estate", "gift", "tax_sale", "related_party", "court"}


@dataclass(frozen=True)
class ScreenConfig:
    min_price: float = 10_000.0
    iqr_multiplier: float = 1.5
    non_arms_types: frozenset[str] = frozenset(NON_ARMS_TYPES)


@dataclass
class Screened:
    sales: pd.DataFrame  # kept sales, with a `ratio` column
    excluded: pd.DataFrame  # every dropped sale with a `reason`
    unsold: pd.DataFrame
    bounds: dict[str, tuple[float, float]] = field(default_factory=dict)


MONEY_COLUMNS = ["sale_price", "assessed_value", "assessed_prior"]


def _to_number(s: pd.Series) -> pd.Series:
    """Accept "$1,234", "1 234" and blanks, as exported by many CAMA and spreadsheet tools."""
    if s.dtype.kind in "if":
        return s
    cleaned = s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def load(path: str, mapping: dict[str, str] | None = None) -> pd.DataFrame:
    """Read a sales CSV. `mapping` renames your headers to ours, e.g. {"assessed_value": "TotalAV"}
    (canonical name -> your header). Money columns may carry $ signs and thousands commas."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df.columns = [c.strip() for c in df.columns]
    if mapping:
        df = df.rename(columns={v.strip(): k for k, v in mapping.items()})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    for c in MONEY_COLUMNS:
        if c in df.columns:
            df[c] = _to_number(df[c])
    if "year_built" in df.columns:
        df["year_built"] = pd.to_numeric(df["year_built"], errors="coerce")
    return df


def _non_arms_mask(df: pd.DataFrame, cfg: ScreenConfig) -> pd.Series:
    if "arms_length" in df.columns:
        flag = df["arms_length"].astype(str).str.strip().str.lower()
        by_flag = flag.isin({"n", "no", "false", "0"})
    else:
        by_flag = pd.Series(False, index=df.index)
    if "sale_type" in df.columns:
        typ = df["sale_type"].astype(str).str.strip().str.lower()
        by_type = typ.isin(cfg.non_arms_types)
    else:
        by_type = pd.Series(False, index=df.index)
    return by_flag | by_type


def screen(df: pd.DataFrame, cfg: ScreenConfig | None = None) -> Screened:
    cfg = cfg or ScreenConfig()
    df = df.copy()
    has_sale = df["sale_price"].notna() & (df["sale_price"] > 0)
    unsold = df[~has_sale].copy()
    sold = df[has_sale].copy()
    sold["reason"] = ""

    def mark(mask: pd.Series, why: str) -> None:
        sold.loc[mask & (sold["reason"] == ""), "reason"] = why

    mark(sold["assessed_value"].isna() | (sold["assessed_value"] <= 0), "missing_assessed_value")
    mark(sold["sale_price"] < cfg.min_price, "nominal_price")
    mark(_non_arms_mask(sold, cfg), "non_arms_length")

    order = sold.sort_values("sale_date") if "sale_date" in sold.columns else sold
    live = order[order["reason"] == ""]
    dup = live.duplicated("parcel_id", keep="last")
    sold.loc[dup[dup].index, "reason"] = "duplicate_parcel_earlier_sale"

    kept = sold[sold["reason"] == ""].copy()
    kept["ratio"] = kept["assessed_value"] / kept["sale_price"]

    bounds: dict[str, tuple[float, float]] = {}
    outliers: dict[object, str] = {}
    for cls, grp in kept.groupby("property_class"):
        q1, q3 = grp["ratio"].quantile(0.25), grp["ratio"].quantile(0.75)
        iqr = q3 - q1
        lo, hi = float(q1 - cfg.iqr_multiplier * iqr), float(q3 + cfg.iqr_multiplier * iqr)
        bounds[str(cls)] = (lo, hi)
        for idx in grp.index[grp["ratio"] < lo]:
            outliers[idx] = "outlier_low_ratio"
        for idx in grp.index[grp["ratio"] > hi]:
            outliers[idx] = "outlier_high_ratio"
    for idx, why in outliers.items():
        sold.loc[idx, "reason"] = why
    kept = kept.drop(index=list(outliers))

    excluded = sold[sold["reason"] != ""].copy()
    excluded["ratio"] = excluded["assessed_value"] / excluded["sale_price"]
    return Screened(kept, excluded, unsold, bounds)
