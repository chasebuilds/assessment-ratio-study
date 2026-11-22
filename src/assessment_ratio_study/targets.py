"""IAAO target ranges. Edit here (or pass a config) to match another edition or a state rule."""

from __future__ import annotations

from dataclasses import dataclass, field

SOURCE = (
    "IAAO Standard on Ratio Studies, 2013 edition (performance targets for level and uniformity)"
)


@dataclass(frozen=True)
class Targets:
    median_low: float = 0.90
    median_high: float = 1.10
    prd_low: float = 0.98
    prd_high: float = 1.03
    prb_ok: float = 0.05
    prb_fail: float = 0.10
    # COD upper limits (percent) by property class. Lower bound for all is 5.0 in the
    # standard; a COD below that is reported as a flag, not a failure.
    cod_low: float = 5.0
    cod_high: dict[str, float] = field(
        default_factory=lambda: {
            "residential": 15.0,  # single-family, older and more heterogeneous areas
            "commercial": 20.0,  # income-producing, smaller or rural jurisdictions
            "vacant_land": 25.0,
        }
    )
    cod_default: float = 15.0
    min_sales: int = 30  # below this, dispersion and bias stats are shown but not judged

    def cod_limit(self, property_class: str | None) -> float:
        return self.cod_high.get(property_class or "", self.cod_default)


DEFAULT = Targets()
