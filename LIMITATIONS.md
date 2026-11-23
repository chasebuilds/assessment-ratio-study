# Limitations

- **Not an appraisal.** This is an analysis and education tool. A USPAP-compliant appraisal requires a licensed or certified appraiser. A ratio study judges the roll as a whole, never one property.
- **Synthetic demo.** The demo county is generated. The benchmark shows how the checks behave on that generator, not on any real county. Planted effects are large on purpose.
- **Target ranges.** The ranges are the 2013 IAAO ones as the author reads them, set in `targets.py`. Your state or office may use another edition or its own rules. Check before you rely on a pass or fail.
- **COD limits by class** use one choice per class (residential 15, commercial 20, vacant land 25). The standard distinguishes newer homogeneous areas, large and small jurisdictions, and more. Change the table to fit.
- **Outlier trimming can hide dispersion.** The IQR trim runs per property class. In the benchmark it removed enough of a high-dispersion neighborhood's tails that COD alone never failed. The report adds a trim-rate warning (over 10% of a stratum's sales trimmed) for this reason. Read the two together.
- **Trimming rule is one common choice** (1.5 x IQR fences on the ratio). It will also trim some legitimate sales (3.5% in the benchmark).
- **Non-arm's-length screening needs your flags.** The tool uses the `arms_length` and `sale_type` columns you give it. It cannot see a family sale that nobody flagged, beyond what the outlier trim happens to catch (99% of the planted half-price sales in the benchmark; real ones will be subtler).
- **Price-quartile strata** omit PRD and PRB, because grouping by sale price biases both.
- **PRB** uses the value-proxy regression described in the docstring in `stats.py`. It is only counted as a problem when the slope is statistically significant and outside +/-0.05.
- **Strata under 30 sales** are shown but not judged. Many tests across many strata will throw a few false alarms by chance (0.6% FAIL and 2.8% REVIEW on clean strata in the benchmark).
- **Sales-chasing check** needs a prior-year assessed value on every parcel, sold or not. It compares median percent change, sold versus unsold, inside each neighborhood. It cannot tell chasing from a legitimate reappraisal that happened to hit sold parcels.
- **Time adjustment** assumes one steady yearly trend for the whole county and a roll that did not change during the sale period. It is off unless you ask. `auto` needs at least 30 dated arm's-length sales and will read a mid-year reassessment as market movement. Markets that differ by neighborhood need a trend per area, which this does not do.
- **Column mapping and money parsing** cover renamed headers and `$1,234` style values. Other formats (accounting negatives, dates in odd layouts) are not handled.
- **One focus class** drives the neighborhood, price and age strata (default `residential`, change with `--focus-class`).
