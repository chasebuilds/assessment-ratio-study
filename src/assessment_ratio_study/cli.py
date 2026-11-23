"""Command line: ratio-study run sales.csv, ratio-study demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import pipeline, report_html, report_json, report_xlsx, synth
from .charts import all_charts
from .validate import load


def _emit(res: pipeline.Result, out: Path, title: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    report_html.write(res, out / "report.html", title)
    report_xlsx.write(res, out / "report.xlsx")
    report_json.write(res, out / "summary.json")
    for name, data in all_charts(res).items():
        (out / name).write_bytes(data)
    print(f"wrote {out / 'report.html'}, {out / 'report.xlsx'} summary.json and 3 chart PNGs")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ratio-study", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a ratio study on a CSV of sales and assessments")
    r.add_argument("csv")
    r.add_argument("--out", default="out")
    r.add_argument("--focus-class", default="residential")
    r.add_argument("--title", default="Assessment ratio study")
    r.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="NAME=HEADER",
        help="map one of your headers to ours, e.g. --map assessed_value=TotalAV (repeatable)",
    )
    r.add_argument(
        "--time-adjust",
        metavar="auto|PCT",
        help="restate sale prices at the valuation date: 'auto' estimates the yearly trend, "
        "or give percent per year",
    )
    r.add_argument("--valuation-date", metavar="YYYY-MM-DD", help="default: earliest sale date")
    d = sub.add_parser("demo", help="generate the seeded synthetic county and report on it")
    d.add_argument("--out", default="out")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument(
        "--trend", type=float, default=0.0, help="yearly market growth in the data, e.g. 0.08"
    )
    d.add_argument("--time-adjust", metavar="auto|PCT", help="as for run")
    d.add_argument("--csv-only", action="store_true", help="only write the synthetic CSV")
    a = p.parse_args(argv)

    if a.cmd == "run":
        mapping = dict(m.split("=", 1) for m in a.map)
        res = pipeline.run(
            load(a.csv, mapping),
            a.focus_class,
            time_adjust=a.time_adjust,
            valuation_date=a.valuation_date,
        )
        _emit(res, Path(a.out), a.title)
        return 0
    df, truth = synth.generate(a.seed, a.trend)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "synthetic_county.csv", index=False)
    (out / "truth.json").write_text(json.dumps(truth.__dict__, indent=2))
    if not a.csv_only:
        res = pipeline.run(df, time_adjust=a.time_adjust)
        _emit(res, out, "Synthetic county ratio study (seeded demo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
