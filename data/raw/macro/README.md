# Raw Macro Series

This folder stores downloaded macroeconomic source series used to convert nominal Brazilian-currency IRPF values into nominal U.S. dollars and target-year U.S. dollars.

## Files

- `bcb_sgs_3694_usd_exchange_annual.csv`: Banco Central do Brasil SGS series 3694, annual U.S. dollar selling exchange rate, period average, in current domestic currency units per U.S. dollar.
- `bcb_sgs_3692_usd_exchange_end_period_annual.csv`: Banco Central do Brasil SGS series 3692, annual U.S. dollar selling exchange rate, end of period, in current domestic currency units per U.S. dollar. This is retained as a documented fallback series.
- `bcb_sgs_3690_usd_exchange_mil_reis_end_period_annual.csv`: Banco Central do Brasil SGS series 3690, U.S. dollar exchange rate in mil-reis per U.S. dollar, end of period, covering 1901-1941. The script scales the raw SGS values by 0.001 to express values such as `16599` as `16.599` mil-reis per U.S. dollar.
- `fred_cpiaucsl_monthly.csv`: FRED `CPIAUCSL`, monthly U.S. Consumer Price Index for All Urban Consumers, all items, U.S. city average, seasonally adjusted, index 1982-1984=100.
- `fred_cpiaucns_monthly.csv`: FRED `CPIAUCNS`, monthly U.S. Consumer Price Index for All Urban Consumers, all items, U.S. city average, not seasonally adjusted, index 1982-1984=100. This series extends the CPI input before 1947.

The files can be refreshed with:

```powershell
python scripts/build_adjusted_usd_tables.py --refresh-macro
```

The adjusted IRPF tables prefer series 3694 because it is the annual period-average counterpart of the monthly series 3698 originally identified for the exchange-rate conversion. For years before the modern BCB annual exchange series, the conversion uses SGS 3690 and records that the rate is end-of-period rather than annual average.
