# Raw Macro Series

This folder stores downloaded macroeconomic source series used to convert nominal Brazilian-currency IRPF values into nominal U.S. dollars and target-year U.S. dollars.

## Files

- `bcb_sgs_3694_usd_exchange_annual.csv`: Banco Central do Brasil SGS series 3694, annual U.S. dollar selling exchange rate, period average, in current domestic currency units per U.S. dollar.
- `fred_cpiaucsl_monthly.csv`: FRED `CPIAUCSL`, monthly U.S. Consumer Price Index for All Urban Consumers, all items, U.S. city average, index 1982-1984=100.

The files can be refreshed with:

```powershell
python scripts/build_adjusted_usd_tables.py --refresh-macro
```

The adjusted IRPF tables use series 3694 because it is the annual period-average counterpart of the monthly series 3698 originally identified for the exchange-rate conversion.
