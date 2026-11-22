"""Command line: ratio-study run sales.csv, ratio-study demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import pipeline, report_html, report_xlsx, synth
from .charts import all_charts
from .validate import load


def _emit(res: pipeline.Result, out: Path, title: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    report_html.write(res, out / "report.html", title)
    report_xlsx.write(res, out / "report.xlsx")
    for name, data in all_charts(res).items():
        (out / name).write_bytes(data)
    print(f"wrote {out / 'report.html'}, {out / 'report.xlsx'} and 3 chart PNGs")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ratio-study", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a ratio study on a CSV of sales and assessments")
    r.add_argument("csv")
    r.add_argument("--out", default="out")
    r.add_argument("--focus-class", default="residential")
    r.add_argument("--title", default="Assessment ratio study")
    d = sub.add_parser("demo", help="generate the seeded synthetic county and report on it")
    d.add_argument("--out", default="out")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--csv-only", action="store_true", help="only write the synthetic CSV")
    a = p.parse_args(argv)

    if a.cmd == "run":
        res = pipeline.run(load(a.csv), a.focus_class)
        _emit(res, Path(a.out), a.title)
        return 0
    df, truth = synth.generate(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "synthetic_county.csv", index=False)
    (out / "truth.json").write_text(json.dumps(truth.__dict__, indent=2))
    if not a.csv_only:
        res = pipeline.run(df)
        _emit(res, out, "Synthetic county ratio study (seeded demo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
