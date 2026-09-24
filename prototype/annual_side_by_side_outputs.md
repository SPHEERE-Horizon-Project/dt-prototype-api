# Side-by-side annual useful-energy comparison

Reference: validated ISO 13790-style semi-stationary implementation. Comparison: integrated, independently calculated Model 3 legacy adapter.

| Building ID | Building | Case | Semi-stationary heating (kWh) | Integrated Model 3 heating (kWh) | Heating difference (%) | Semi-stationary cooling (kWh) | Integrated Model 3 cooling (kWh) | Cooling difference (%) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Test building 1 | building_aggregate | 320,080.9 | 277,866.3 | -13.2 | 72,104.2 | 77,552.0 | 7.6 |
| 1 | Test building 1 | individual_zone:lower | 122,531.9 | 103,398.5 | -15.6 | 51,128.1 | 69,273.9 | 35.5 |
| 1 | Test building 1 | individual_zone:upper | 197,549.0 | 195,319.3 | -1.1 | 20,976.1 | 19,690.8 | -6.1 |
| 18 | Test building 2 | building_aggregate | 138,054.4 | 127,205.3 | -7.9 | 34,289.5 | 41,958.4 | 22.4 |
| 18 | Test building 2 | individual_zone:lower | 58,273.7 | 52,779.9 | -9.4 | 24,011.3 | 33,192.4 | 38.2 |
| 18 | Test building 2 | individual_zone:upper | 79,780.7 | 82,885.3 | 3.9 | 10,278.2 | 12,871.2 | 25.2 |
| 19 | Test building 3 | building_aggregate | 304,313.5 | 299,437.7 | -1.6 | 37,862.9 | 36,332.9 | -4.0 |
| 19 | Test building 3 | individual_zone:lower | 76,738.6 | 70,068.2 | -8.7 | 28,015.4 | 37,373.0 | 33.4 |
| 19 | Test building 3 | individual_zone:upper | 227,575.0 | 236,514.6 | 3.9 | 9,847.5 | 8,793.3 | -10.7 |
| 20 | Test building 4 | building_aggregate | 1,159,575.0 | 1,153,615.0 | -0.5 | 84,637.1 | 58,016.0 | -31.5 |
| 20 | Test building 4 | individual_zone:lower | 296,723.5 | 310,872.6 | 4.8 | 2,660.5 | 264.6 | -90.1 |
| 20 | Test building 4 | individual_zone:upper | 862,851.5 | 844,001.2 | -2.2 | 81,976.6 | 61,896.9 | -24.5 |
| 21 | Test building 5 | building_aggregate | 2,931,187.6 | 2,850,494.0 | -2.8 | 269,089.1 | 194,937.6 | -27.6 |

The values are a cross-model comparison, not empirical validation. Model 3 values are approximate because of the documented input and calculation-boundary mappings.
