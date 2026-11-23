"""Self-contained HTML report (charts embedded as base64 PNG), frosted-glass styling."""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import pandas as pd

from . import targets as tg
from .charts import all_charts
from .pipeline import Result
from .report_xlsx import DISCLAIMER, targets_table

CSS = """
:root{--ink:#2a2019;--ink2:rgba(42,32,25,.66);--card:rgba(255,252,248,.62);--edge:rgba(255,255,255,.65);
--good:#1f9a72;--bad:#c8452c;--warn:#a8670f;--me:#e2583a}
@media (prefers-color-scheme:dark){:root{--ink:#f6ece2;--ink2:rgba(246,236,226,.7);--card:rgba(48,36,28,.6);
--edge:rgba(255,255,255,.14);--good:#4fd1a1;--bad:#ff8a6a;--warn:#f0b45a;--me:#ff7a55}
body{background:linear-gradient(160deg,#2a1f19,#3b2c22 60%,#241a14)!important}}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,sans-serif;min-height:100vh;
background:radial-gradient(60% 45% at 80% 8%,#fff6e6,transparent 70%),linear-gradient(160deg,#e9ddcf,#cdb9a3 65%,#b89a80);
background-attachment:fixed}
nav{position:sticky;top:12px;z-index:5;display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin:12px auto 0;
width:fit-content;max-width:calc(100% - 24px);padding:6px;border-radius:999px;background:var(--card);
border:1px solid var(--edge);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
nav a{color:var(--ink);text-decoration:none;padding:6px 14px;border-radius:999px;font-size:13px}
nav a:hover{background:var(--edge)}
main{max-width:1060px;margin:0 auto;padding:16px}
section{background:var(--card);border:1px solid var(--edge);border-radius:24px;padding:22px;margin:16px 0;
backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);box-shadow:0 10px 40px rgba(70,40,20,.14)}
h1{font-size:28px;margin:8px 0 4px}h2{font-size:19px;margin:0 0 10px}
.note{color:var(--ink2);font-size:13px}
.warn{border-left:4px solid var(--me);padding-left:12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}
.tile{background:var(--edge);border-radius:16px;padding:12px}
.tile b{display:block;font:600 24px ui-monospace,Consolas,monospace}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:6px 9px;text-align:right;border-bottom:1px solid var(--edge);white-space:nowrap}
th{font-weight:600;position:sticky;top:0}th:first-child,td:first-child,td.l,th.l{text-align:left}
td{font-family:ui-monospace,Consolas,monospace}td.l{font-family:inherit}
.PASS{color:var(--good);font-weight:600}.FAIL{color:var(--bad);font-weight:600}
.REVIEW{color:var(--warn);font-weight:600}.bad{color:var(--bad)}
img{max-width:100%;border-radius:14px;background:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
"""


def _fmt(v: object, spec: str = ".3f") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int | float):
        return format(v, spec)
    return escape(str(v))


def _strata_html(res: Result) -> str:
    cols = [("dimension", "Dimension", ""), ("stratum", "Stratum", ""), ("n", "n", "d"),
            ("median", "Median", ".3f"), ("weighted_mean", "Wtd mean", ".3f"),
            ("mean", "Mean", ".3f"), ("cod", "COD", ".1f"), ("prd", "PRD", ".3f"),
            ("prb", "PRB", ".3f")]  # fmt: skip
    head = "".join(f"<th{' class=l' if i < 2 else ''}>{h}</th>" for i, (_, h, _) in enumerate(cols))
    head += "<th>PRB 95% CI</th><th>PRB status</th><th>Verdict</th><th class=l>Why</th>"
    out = []
    for _, r in res.strata.iterrows():
        cells = "".join(
            f"<td{' class=l' if i < 2 else ''}>{_fmt(r[c], spec or 's')}</td>"
            for i, (c, _, spec) in enumerate(cols)
        )
        ci = "-" if pd.isna(r["prb_ci_low"]) else f"{r['prb_ci_low']:.3f} to {r['prb_ci_high']:.3f}"
        why = []
        if not r["median_ok"]:
            why.append("median out of range")
        if not r["cod_ok"]:
            why.append("COD too high")
        if r["prd_ok"] == 0:
            why.append("PRD out of range")
        if r["prb_status"] in {"fail", "marginal"}:
            why.append(f"PRB {r['prb_status']}")
        reason = "; ".join(why) + (" | " if why and r["notes"] else "") + str(r["notes"])
        cells += f"<td>{ci}</td><td>{r['prb_status']}</td>"
        cells += (
            f"<td class='l {r['verdict']}'>{r['verdict']}</td><td class=l>{escape(reason)}</td>"
        )
        out.append(f"<tr>{cells}</tr>")
    return f"<div class=scroll><table><tr>{head}</tr>{''.join(out)}</table></div>"


def _chasing_html(res: Result) -> str:
    if not len(res.chasing):
        return "<p class=note>No assessed_prior column, so the check was skipped.</p>"
    rows = []
    for _, r in res.chasing.iterrows():
        cls = "bad" if r["flag"].startswith("SALES") else ""
        rows.append(
            f"<tr><td class=l>{escape(str(r['group']))}</td><td>{r['n_sold']}</td><td>{r['n_unsold']}</td>"
            f"<td>{_fmt(r['median_change_sold_pct'], '.1f')}</td><td>{_fmt(r['median_change_unsold_pct'], '.1f')}</td>"
            f"<td>{_fmt(r['gap_points'], '.1f')}</td><td>{_fmt(r['p_value'], '.4f')}</td>"
            f"<td class='l {cls}'>{r['flag']}</td></tr>"
        )
    head = ("<tr><th class=l>Group</th><th>Sold</th><th>Unsold</th><th>Sold chg %</th>"
            "<th>Unsold chg %</th><th>Gap (pts)</th><th>p</th><th class=l>Flag</th></tr>")  # fmt: skip
    return f"<div class=scroll><table>{head}{''.join(rows)}</table></div>"


def _excluded_html(res: Result, limit: int = 60) -> str:
    ex = res.screened.excluded.sort_values(["reason", "parcel_id"])
    counts = ex["reason"].value_counts()
    summary = "".join(
        f"<tr><td class=l>{escape(str(k))}</td><td>{v}</td></tr>" for k, v in counts.items()
    )
    show = ex[ex["reason"].str.startswith("outlier")]
    rows = "".join(
        f"<tr><td class=l>{r.parcel_id}</td><td class=l>{r.neighborhood}</td>"
        f"<td>{r.sale_price:,.0f}</td><td>{r.assessed_value:,.0f}</td><td>{r.ratio:.3f}</td>"
        f"<td class=l>{r.reason}</td></tr>"
        for r in show.head(limit).itertuples()
    )
    more = f"<p class=note>Showing {min(limit, len(show))} of {len(show)} trimmed outliers. The Excel report lists every excluded sale.</p>"
    bounds = "; ".join(f"{k}: {lo:.3f} to {hi:.3f}" for k, (lo, hi) in res.screened.bounds.items())
    return (
        f"<div class=scroll><table><tr><th class=l>Reason</th><th>Sales</th></tr>{summary}</table></div>"
        f"<p class=note>Outlier fences (1.5 x IQR, per property class): {escape(bounds)}</p>"
        "<h3>Trimmed list</h3><div class=scroll><table><tr><th class=l>Parcel</th><th class=l>Neighborhood</th>"
        "<th>Sale</th><th>Assessed</th><th>Ratio</th><th class=l>Reason</th></tr>"
        + rows
        + "</table></div>"
        + more
    )


def _ta_note(res: Result) -> str:
    ta = res.time_adjustment
    if ta is None:
        return ""
    how = f"estimated from {ta.n_used} sales" if ta.method == "estimated" else "as given"
    return (
        f'<p class="note">Sale prices were time-adjusted: {ta.annual_pct:.2f}% per year ({how}), '
        f"restated at {ta.valuation_date}.</p>"
    )


def render(res: Result, title: str = "Assessment ratio study") -> str:
    sc = res.screened
    overall = res.strata.iloc[0]
    n_bad = int(res.strata["verdict"].isin(["FAIL", "REVIEW"]).sum())
    charts = all_charts(res)
    imgs = "".join(
        f'<img alt="{name[:-4].replace("_", " ")}" src="data:image/png;base64,{base64.b64encode(b).decode()}">'
        for name, b in charts.items()
    )
    tt = targets_table(res)
    trows = "".join(
        f"<tr><td class=l>{escape(a)}</td><td class=l>{escape(b)}</td></tr>"
        for a, b in tt.itertuples(index=False)
    )
    tiles = (
        f"<div class=tiles><div class=tile>Sales used<b>{len(sc.sales):,}</b></div>"
        f"<div class=tile>Sales excluded<b>{len(sc.excluded):,}</b></div>"
        f"<div class=tile>Overall median<b>{overall['median']:.3f}</b></div>"
        f"<div class=tile>Overall COD<b>{overall['cod']:.1f}</b></div>"
        f"<div class=tile>Strata to review<b>{n_bad}</b></div></div>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>{CSS}</style></head><body>
<nav><a href="#summary">Summary</a><a href="#strata">Strata</a><a href="#charts">Charts</a>
<a href="#chasing">Sales chasing</a><a href="#screens">Sale screens</a><a href="#targets">Targets</a></nav>
<main>
<section id="summary"><h1>{escape(title)}</h1>
<p class="warn note"><b>{escape(DISCLAIMER)}</b> Synthetic or supplied data only. Ratio studies test how
uniform and level an assessment roll is; they do not value any one property.</p>{tiles}
<p class="note">Focus class for neighborhood, price and age strata: <b>{escape(res.focus_class)}</b>.
Strata with fewer than {res.targets.min_sales} sales are shown but not judged.</p>{_ta_note(res)}</section>
<section id="strata"><h2>Statistics by stratum</h2>{_strata_html(res)}
<p class="note">Price-quartile rows omit PRD and PRB: grouping by sale price builds a bias into
those two measures.</p></section>
<section id="charts"><h2>Charts</h2><div class="grid">{imgs}</div></section>
<section id="chasing"><h2>Sales-chasing check</h2>
<p class="note">Median change in assessed value from the prior roll, parcels that sold versus parcels that did not.
Flag: sold gain at least 3 points higher and Mann-Whitney p below 0.01. A flagged neighborhood can look
perfect in the ratio table above and still be wrong, because only the sold parcels were fixed.</p>{_chasing_html(res)}</section>
<section id="screens"><h2>Sale validation screens</h2>{_excluded_html(res)}</section>
<section id="targets"><h2>Target ranges</h2><div class=scroll><table><tr><th class=l>Measure</th><th class=l>Target</th></tr>{trows}</table></div>
<p class="note">Source: {escape(tg.SOURCE)}. Check the edition your state or office uses; ranges are
set in <code>targets.py</code>.</p></section>
</main></body></html>"""


def write(res: Result, path: str | Path, title: str = "Assessment ratio study") -> None:
    Path(path).write_text(render(res, title), encoding="utf-8")
