"""Machine-readable summary, for dashboards or other scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import Result


def _clean(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records"))  # type: ignore[no-any-return]


def to_dict(res: Result) -> dict[str, Any]:
    sc = res.screened
    ta = res.time_adjustment
    return {
        "disclaimer": "Analysis tool, not an appraisal. USPAP requires a licensed or certified appraiser.",
        "focus_class": res.focus_class,
        "parcels": res.n_rows,
        "sales_used": len(sc.sales),
        "sales_excluded": len(sc.excluded),
        "excluded_by_reason": {
            str(k): int(v) for k, v in sc.excluded["reason"].value_counts().items()
        },
        "iqr_bounds": {k: [lo, hi] for k, (lo, hi) in sc.bounds.items()},
        "time_adjustment": None
        if ta is None
        else {
            "annual_pct": ta.annual_pct,
            "valuation_date": ta.valuation_date,
            "method": ta.method,
            "n_used": ta.n_used,
        },
        "strata": _clean(res.strata),
        "sales_chasing": _clean(res.chasing),
    }


def write(res: Result, path: str | Path) -> None:
    Path(path).write_text(json.dumps(to_dict(res), indent=2), encoding="utf-8")
