import json
from pathlib import Path

import pandas as pd
import pytest

from assessment_ratio_study import cli, pipeline, report_json, synth, timeadj
from assessment_ratio_study.validate import load


def test_adjust_hand_example() -> None:
    # 10% a year, valuation date 2025-01-01. A sale on 2026-01-01 is 365 days = 0.99932 years
    # out, so it is restated at 110000 / 1.1 ** 0.99932 = about 100,0xx. A sale on the valuation
    # date itself does not change.
    df = pd.DataFrame(
        {"sale_date": ["2025-01-01", "2026-01-01"], "sale_price": [100_000.0, 110_000.0]}
    )
    out, ta = timeadj.adjust(df, 10.0, "2025-01-01")
    assert out["sale_price"].iloc[0] == pytest.approx(100_000.0)
    assert out["sale_price"].iloc[1] == pytest.approx(110_000 / 1.1 ** (365 / 365.25))
    assert out["sale_price_raw"].iloc[1] == 110_000
    assert ta.method == "given"


def test_adjust_zero_trend_is_identity() -> None:
    df = pd.DataFrame({"sale_date": ["2025-03-01"], "sale_price": [150_000.0]})
    out, _ = timeadj.adjust(df, 0.0, "2025-01-01")
    assert out["sale_price"].iloc[0] == pytest.approx(150_000.0)


def test_estimate_recovers_trend() -> None:
    df, _ = synth.generate(5, trend=0.12)
    pct, n = timeadj.estimate_annual_pct(df)
    assert 9.0 < pct < 15.0
    assert n > 500


def test_estimate_is_near_zero_without_trend() -> None:
    df, _ = synth.generate(5, trend=0.0)
    pct, _ = timeadj.estimate_annual_pct(df)
    assert abs(pct) < 3.0


def test_estimate_needs_enough_sales() -> None:
    df, _ = synth.generate(5)
    with pytest.raises(ValueError, match="at least 30"):
        timeadj.estimate_annual_pct(df.head(40))


def test_time_adjustment_fixes_a_false_failure() -> None:
    df, _ = synth.generate(7, trend=0.15)
    raw = pipeline.run(df).strata.set_index("stratum")
    adj_res = pipeline.run(df, time_adjust="auto")
    adj = adj_res.strata.set_index("stratum")
    # Rising prices against a static roll push late-year sales ratios down; adjusting
    # removes that spread, so dispersion falls for the clean neighborhoods.
    clean = ["Oak Ridge", "Mill Creek", "Elm Park", "Cedar Flats"]
    assert adj.loc[clean, "cod"].mean() < raw.loc[clean, "cod"].mean()
    assert adj_res.time_adjustment is not None
    assert adj_res.time_adjustment.method == "estimated"
    assert 10.0 < adj_res.time_adjustment.annual_pct < 20.0


def test_given_trend_is_recorded() -> None:
    df, _ = synth.generate(3, trend=0.1)
    res = pipeline.run(df, time_adjust=10.0, valuation_date="2025-01-01")
    assert res.time_adjustment is not None
    assert res.time_adjustment.method == "given"
    assert res.time_adjustment.valuation_date == "2025-01-01"


def test_load_maps_headers_and_money(tmp_path: Path) -> None:
    f = tmp_path / "s.csv"
    f.write_text(
        "PIN,Hood,Class,SalePrice,TotalAV\n"
        'a1,North,residential,"$120,000","$114,000"\n'
        "a2,North,residential,,98000\n",
        encoding="utf-8",
    )
    mapping = {
        "parcel_id": "PIN",
        "neighborhood": "Hood",
        "property_class": "Class",
        "sale_price": "SalePrice",
        "assessed_value": "TotalAV",
    }
    df = load(str(f), mapping)
    assert df["sale_price"].iloc[0] == 120_000
    assert df["assessed_value"].iloc[0] == 114_000
    assert pd.isna(df["sale_price"].iloc[1])


def test_load_reports_missing_columns(tmp_path: Path) -> None:
    f = tmp_path / "s.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        load(str(f))


def test_json_export_matches_result() -> None:
    df, _ = synth.generate(42)
    res = pipeline.run(df)
    d = report_json.to_dict(res)
    assert d["sales_used"] == len(res.screened.sales)
    assert sum(d["excluded_by_reason"].values()) == len(res.screened.excluded)
    names = {r["stratum"] for r in d["strata"]}
    assert {"Maple Hills", "Old Town"} <= names
    json.dumps(d)  # fully serializable


def test_cli_run_with_mapping_and_time_adjust(tmp_path: Path) -> None:
    df, _ = synth.generate(2, trend=0.1)
    renamed = df.rename(columns={"assessed_value": "TotalAV"})
    src = tmp_path / "in.csv"
    renamed.to_csv(src, index=False)
    out = tmp_path / "out"
    code = cli.main(
        [
            "run",
            str(src),
            "--out",
            str(out),
            "--map",
            "assessed_value=TotalAV",
            "--time-adjust",
            "auto",
        ]
    )
    assert code == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["time_adjustment"]["method"] == "estimated"
    assert (out / "report.html").exists()
    assert "Sale prices were time-adjusted" in (out / "report.html").read_text(encoding="utf-8")
    assert (out / "report.xlsx").exists()
