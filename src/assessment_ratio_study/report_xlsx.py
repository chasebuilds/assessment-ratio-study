"""Excel report: summary, strata, excluded sales, sales-chasing, targets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from . import targets as tg
from .pipeline import Result

DISCLAIMER = (
    "Analysis and education tool. This is not an appraisal. A USPAP-compliant appraisal "
    "requires a licensed or certified appraiser."
)
FILLS = {
    "FAIL": PatternFill("solid", fgColor="F4B6A8"),
    "REVIEW": PatternFill("solid", fgColor="F6DFA6"),
    "PASS": PatternFill("solid", fgColor="BFE3D3"),
}


def targets_table(res: Result) -> pd.DataFrame:
    t = res.targets
    rows = [
        ("Median ratio", f"{t.median_low:.2f} to {t.median_high:.2f}"),
        ("PRD", f"{t.prd_low:.2f} to {t.prd_high:.2f}"),
        (
            "PRB",
            f"within +/-{t.prb_ok:.2f}; marginal to +/-{t.prb_fail:.2f}; beyond is unacceptable "
            "(only counted if the slope is statistically significant)",
        ),
        ("COD lower bound", f"{t.cod_low:.1f} (below it is flagged, not failed)"),
    ]
    rows += [(f"COD upper limit, {k}", f"{v:.1f}") for k, v in t.cod_high.items()]
    rows += [("Minimum sales to judge a stratum", str(t.min_sales)), ("Source", tg.SOURCE)]
    return pd.DataFrame(rows, columns=["Measure", "Target"])


def summary_table(res: Result) -> pd.DataFrame:
    sc = res.screened
    reasons = sc.excluded["reason"].value_counts()
    rows: list[tuple[str, object]] = [
        ("Disclaimer", DISCLAIMER),
        ("Parcels in file", res.n_rows),
        ("Sales in file", len(sc.sales) + len(sc.excluded)),
        ("Sales used", len(sc.sales)),
        ("Sales excluded", len(sc.excluded)),
    ]
    rows += [(f"  excluded: {k}", int(v)) for k, v in reasons.items()]
    rows += [(f"IQR bounds, {k}", f"{lo:.3f} to {hi:.3f}") for k, (lo, hi) in sc.bounds.items()]
    ta = res.time_adjustment
    if ta:
        rows.append(
            (
                "Time adjustment",
                f"{ta.annual_pct:.2f}% per year ({ta.method}"
                f"{f' from {ta.n_used} sales' if ta.n_used else ''}), prices restated at {ta.valuation_date}",
            )
        )
    fails = res.strata[res.strata["verdict"].isin(["FAIL", "REVIEW"])]
    rows.append(
        (
            "Strata failing or under review",
            ", ".join(f"{d}:{s}" for d, s in zip(fails["dimension"], fails["stratum"], strict=True))
            or "none",
        )
    )
    flagged = (
        res.chasing[res.chasing["flag"] == "SALES CHASING SUSPECTED"]
        if len(res.chasing)
        else res.chasing
    )
    rows.append(
        ("Sales chasing suspected in", ", ".join(flagged["group"]) if len(flagged) else "none")
    )
    return pd.DataFrame(rows, columns=["Item", "Value"])


def write(res: Result, path: str | Path) -> None:
    excluded_cols = [c for c in ["parcel_id", "neighborhood", "property_class", "sale_date",
                                 "sale_price", "assessed_value", "ratio", "sale_type", "reason"]
                     if c in res.screened.excluded.columns]  # fmt: skip
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        summary_table(res).to_excel(xw, sheet_name="Summary", index=False)
        res.strata.to_excel(xw, sheet_name="Strata", index=False)
        res.chasing.to_excel(xw, sheet_name="Sales chasing", index=False)
        res.screened.excluded[excluded_cols].sort_values("reason").to_excel(
            xw, sheet_name="Excluded sales", index=False
        )
        targets_table(res).to_excel(xw, sheet_name="Targets", index=False)
        for ws in xw.book.worksheets:
            for c in ws[1]:
                c.font = Font(bold=True)
            ws.freeze_panes = "A2"
            for i, col in enumerate(ws.columns, start=1):
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
        ws = xw.book["Strata"]
        vcol = list(res.strata.columns).index("verdict") + 1
        for r in range(2, ws.max_row + 1):
            cell = ws.cell(r, vcol)
            if cell.value in FILLS:
                cell.fill = FILLS[str(cell.value)]
        for col_name, fmt in [("median", "0.000"), ("weighted_mean", "0.000"), ("mean", "0.000"),
                              ("cod", "0.0"), ("prd", "0.000"), ("prb", "0.000"),
                              ("prb_ci_low", "0.000"), ("prb_ci_high", "0.000")]:  # fmt: skip
            idx = list(res.strata.columns).index(col_name) + 1
            for r in range(2, ws.max_row + 1):
                ws.cell(r, idx).number_format = fmt
