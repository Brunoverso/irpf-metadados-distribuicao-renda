# Refined Macro Factors

This folder stores annual conversion factors derived from the raw macro series.

## Files

- `usd_2026_conversion_factors.csv`: one row per year, joining the selected BCB exchange-rate input with annual-average U.S. CPI. The file reports the exchange-rate source, timing, reported unit, CPI series, conversion method, and CPI multiplier used to express nominal dollars in target-year dollars.

The current target year is 2026. Because 2026 is not complete yet, the CPI target average uses the available months only and is marked as `partial`.

Current method hierarchy:

- `bcb_3694_cpiaucsl`: BCB SGS 3694 annual period-average exchange rate and FRED `CPIAUCSL`, used from 1947 onward when both are available.
- `bcb_3694_cpiaucns`: BCB SGS 3694 annual period-average exchange rate and FRED `CPIAUCNS`, used for 1943-1946 because `CPIAUCSL` begins in 1947.
- `bcb_3690_end_period_cpiaucns`: BCB SGS 3690 historical end-of-period exchange rate and FRED `CPIAUCNS`, used for pre-1942 years covered by the IRPF data.
- `missing_exchange_cpiaucns`: CPI is available, but no exchange-rate input is currently available for the year. In the present data package this applies to 1942.
