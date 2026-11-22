import pandas as pd

from assessment_ratio_study import pipeline, synth
from assessment_ratio_study.chasing import check
from assessment_ratio_study.validate import screen


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "parcel_id": ["a", "b", "c", "d", "e", "f", "g", "h"],
            "neighborhood": "N1",
            "property_class": "residential",
            "sale_date": "2025-03-01",
            "sale_price": [100_000, 100_000, 100_000, 100_000, 100_000, 5_000, 100_000, 100_000],
            "assessed_value": [95_000, 96_000, 97_000, 98_000, 99_000, 4_000, 98_000, 900_000],
            "sale_type": ["arms_length"] * 3 + ["family"] + ["arms_length"] * 4,
            "arms_length": ["Y"] * 8,
        }
    )


def test_screens_reasons() -> None:
    sc = screen(_rows())
    why = dict(zip(sc.excluded["parcel_id"], sc.excluded["reason"], strict=True))
    assert why["d"] == "non_arms_length"  # sale_type family
    assert why["f"] == "nominal_price"
    assert why["h"] == "outlier_high_ratio"  # ratio 9.0 against a tight group
    assert set(sc.sales["parcel_id"]) == {"a", "b", "c", "e", "g"}


def test_duplicate_parcel_keeps_latest() -> None:
    df = _rows().iloc[:3].copy()
    df.loc[1, "parcel_id"] = "a"
    df.loc[0, "sale_date"] = "2024-01-01"
    sc = screen(df)
    dups = sc.excluded[sc.excluded["reason"] == "duplicate_parcel_earlier_sale"]
    assert list(dups.index) == [0]


def test_chasing_flags_only_sold_gain() -> None:
    n = 40
    sold = pd.DataFrame(
        {"neighborhood": "X", "assessed_prior": 100.0, "assessed_value": 115.0}, index=range(n)
    )
    unsold = pd.DataFrame(
        {"neighborhood": "X", "assessed_prior": 100.0, "assessed_value": 103.0}, index=range(n)
    )
    out = check(sold, unsold)
    assert out.loc[out["group"] == "X", "flag"].iloc[0] == "SALES CHASING SUSPECTED"
    same = check(unsold, unsold)
    assert (same["flag"] == "not enough data").sum() == 0 or "SALES" not in " ".join(same["flag"])


def test_demo_catches_planted_problems() -> None:
    df, truth = synth.generate(42)
    res = pipeline.run(df)
    st = res.strata.set_index("stratum")
    assert st.loc["Old Town", "verdict"] == "FAIL"
    assert st.loc["Maple Hills", "prb"] < -0.05
    flagged = set(res.chasing.loc[res.chasing["flag"] == "SALES CHASING SUSPECTED", "group"])
    assert "Ridgeview" in flagged
    assert set(truth.planted) == {"Maple Hills", "Old Town", "Riverbend", "Ridgeview"}
