# Shared systems, carriers and renewable energy: comparison report

> Publication copy: some detailed evidence is in the [optional full archive](../../docs/validation_archive.md).

Fresh calculations for the supplied building cases. All four thermal solver families use the same downstream system equations, ancillary schedules, renewable production and carrier-factor configuration. Results are engineering model comparisons and software verification, not validation against metered consumption or the future ISO spreadsheet.

## Calculation boundary and assumptions

- Thermal loads: sensible zone plus separate net sensible AHU heating/cooling, positive kWh; ideal emitter settings preserve the earlier thermal benchmark. Latent conditioning and extra gross AHU reheat/cooling are outside this comparison.
- Additional loads: actual shared DHW, appliance/lighting and AHU fan schedules. Monthly_SS_simplified's mapped thermal gains are never treated as appliance consumption.
- Systems: the resolved JSON records all generation curves, distribution/emission/regulation efficiencies and explicit auxiliary coefficients. AHU coils use generation/distribution only. DHW solar heat is allocated at the generator bus before fuel/electricity conversion.
- Dynamic: conversion and no-storage PV/ST matching at each weather/thermal time step. Monthly: conversion at monthly mean outdoor temperature and the explicitly supplied PV/ST factors. Dynamic and monthly grid exchange therefore have intentionally different matching assumptions.
- The example uses supplied constant system efficiencies. PR, collector parameters, monthly matching factors, primary/carbon factors and prices are labelled illustrative inputs. They are not inferred national values or validated ISO factors. Costs exclude standing charges, taxes and demand tariffs.
- Renewable/meter balances operate once per building. Zone service outputs allocate the common plant energy by each zone's useful demand. They are not separate PV meters. Collapsed cases remain separate alternative building representations.

See [resolved configuration](energy_config_resolved.json), [monthly outputs](energy_monthly.csv), [annual outputs](energy_annual.csv), [annual service outputs](service_annual.csv), [annual zone service allocations](zone_service_annual.csv), and [manifest](manifest.json).

## Verification

| Check | Value |
| --- | --- |
| cases | 51 |
| building_model_months | 612 |
| buildings | 5 |
| zone_allocation_max_abs_kWh | 8.731149137020111e-11 |
| maximum_interval_balance_residual_kWh | 1.1641532182693481e-10 |
| common_inputs_max_spread_kWh | 1.4551915228366852e-11 |
| historical_values_compared | 50 |
| historical_within_rounding | 50 |
| historical_max_abs_difference_MWh | 0.004989227716123423 |
| historical_source_sha256 | dabb855aa2af931eded2f3ddc148651b9b6c21347221a809ddd66c28580121f1 |
| baseline_all_curves_constant | True |
| baseline_aggregation_max_abs_kWh | 1.1641532182693479e-10 |
| vb_monthly_vs_qss_max_abs_kWh | 1.1641532182693481e-10 |

The balance tolerance is 1e-6 kWh + 1e-9 times the relevant energy magnitude. Cross-model differences have no arbitrary pass threshold. The historical reconciliation checks only useful heating/cooling against comparison_report.md's rounded figures; the old report does not validate the new delivered-energy results.

## Systems and renewable sizing

| Building | Heating | Cooling | PV kWp | ST m² |
| --- | --- | --- | --- | --- |
| Test building 1 | Traditional Gas Boiler, Centralized, Low Temp Radiator | A-A split | 0.000 | 37.254 |
| Test building 2 | Condensing Gas Boiler, Single, High Temp Radiator | A-W chiller, Single, Fan coil | 32.473 | 15.334 |
| Test building 3 | A-W Heat Pump, Single, Fan coil | A-W chiller, Centralized, Fan coil | 0.000 | 0.000 |
| Test building 4 | Traditional Gas Boiler, Centralized, Radiant surface | A-W chiller, Centralized, Fan coil | 178.139 | 0.000 |
| Test building 5 | Condensing Gas Boiler, Centralized, High Temp Radiator | A-A split | 0.000 | 182.285 |

## Building-by-building annual results

Energy columns below are MWh/year. Imported carrier energy is final energy at the building boundary. Primary energy and carbon use import factors; export credits are reported separately in the CSVs. No fuel is offset by exported PV.

### Test building 1

| Model | Electricity imported | Gas imported | PV self-use | PV exported | ST used |
| --- | --- | --- | --- | --- | --- |
| Dynamic_RC 5R1C | 225.640 | 634.987 | 0.000 | 0.000 | 18.108 |
| Dynamic_RC 7R2C | 225.235 | 653.604 | 0.000 | 0.000 | 18.108 |
| Monthly_SS | 229.298 | 663.669 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_simplified zone sum | 228.017 | 658.151 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_simplified collapsed | 227.020 | 631.269 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_VBDD monthly zone sum | 229.298 | 663.669 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_VBDD monthly collapsed | 227.508 | 642.678 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_VBDD linear zone sum | 229.506 | 663.509 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_VBDD linear collapsed | 227.891 | 642.550 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_VBDD fixed zone sum | 223.067 | 626.385 | 0.000 | 0.000 | 10.869 |
| Monthly_SS_VBDD fixed collapsed | 219.950 | 621.874 | 0.000 | 0.000 | 10.869 |

| Model | Imported primary MWh | Import carbon tCO2e | Net energy cost, thousand EUR |
| --- | --- | --- | --- |
| Dynamic_RC 5R1C | 1,240.023 | 183.408 | 113.559 |
| Dynamic_RC 7R2C | 1,259.527 | 187.029 | 115.133 |
| Monthly_SS | 1,280.352 | 190.058 | 117.055 |
| Monthly_SS_simplified zone sum | 1,271.208 | 188.634 | 116.238 |
| Monthly_SS_simplified collapsed | 1,239.244 | 183.009 | 113.569 |
| Monthly_SS_VBDD monthly zone sum | 1,280.352 | 190.058 | 117.055 |
| Monthly_SS_VBDD monthly collapsed | 1,252.965 | 185.413 | 114.718 |
| Monthly_SS_VBDD linear zone sum | 1,280.675 | 190.078 | 117.092 |
| Monthly_SS_VBDD linear collapsed | 1,253.744 | 185.483 | 114.802 |
| Monthly_SS_VBDD fixed zone sum | 1,224.385 | 181.044 | 112.141 |
| Monthly_SS_VBDD fixed collapsed | 1,211.941 | 179.362 | 110.956 |

[Archived figure: Monthly carrier and renewable results — full archive](../../docs/validation_archive.md#reports-shared-energy-figures-1-6b86b273ff34fce1-monthly-png)

[Individual-zone and collapsed-case service tables](zone_reports/1-6b86b273ff34fce1.md) show useful and delivered heating/cooling separately, DHW conversion, solar heat allocation and common zone electrical loads.

### Test building 2

| Model | Electricity imported | Gas imported | PV self-use | PV exported | ST used |
| --- | --- | --- | --- | --- | --- |
| Dynamic_RC 5R1C | 56.741 | 247.491 | 28.422 | 2.097 | 7.440 |
| Dynamic_RC 7R2C | 56.362 | 260.285 | 28.551 | 1.968 | 7.440 |
| Monthly_SS | 67.448 | 261.900 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_simplified zone sum | 67.512 | 261.532 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_simplified collapsed | 66.568 | 248.581 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_VBDD monthly zone sum | 67.448 | 261.900 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_VBDD monthly collapsed | 67.107 | 254.009 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_VBDD linear zone sum | 67.764 | 261.647 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_VBDD linear collapsed | 67.473 | 253.811 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_VBDD fixed zone sum | 64.301 | 248.287 | 19.837 | 10.682 | 4.474 |
| Monthly_SS_VBDD fixed collapsed | 63.173 | 244.219 | 19.837 | 10.682 | 4.474 |

| Model | Imported primary MWh | Import carbon tCO2e | Net energy cost, thousand EUR |
| --- | --- | --- | --- |
| Dynamic_RC 5R1C | 408.418 | 63.683 | 36.334 |
| Dynamic_RC 7R2C | 421.581 | 66.147 | 37.398 |
| Monthly_SS | 449.966 | 69.242 | 39.792 |
| Monthly_SS_simplified zone sum | 449.713 | 69.184 | 39.775 |
| Monthly_SS_simplified collapsed | 433.202 | 66.358 | 38.373 |
| Monthly_SS_VBDD monthly zone sum | 449.966 | 69.242 | 39.792 |
| Monthly_SS_VBDD monthly collapsed | 440.466 | 67.579 | 38.997 |
| Monthly_SS_VBDD linear zone sum | 450.446 | 69.271 | 39.848 |
| Monthly_SS_VBDD linear collapsed | 441.127 | 67.630 | 39.070 |
| Monthly_SS_VBDD fixed zone sum | 427.439 | 65.733 | 37.780 |
| Monthly_SS_VBDD fixed collapsed | 420.255 | 64.637 | 37.132 |

[Archived figure: Monthly carrier and renewable results — full archive](../../docs/validation_archive.md#reports-shared-energy-figures-18-4ec9599fc203d176-monthly-png)

[Individual-zone and collapsed-case service tables](zone_reports/18-4ec9599fc203d176.md) show useful and delivered heating/cooling separately, DHW conversion, solar heat allocation and common zone electrical loads.

### Test building 3

| Model | Electricity imported | Gas imported | PV self-use | PV exported | ST used |
| --- | --- | --- | --- | --- | --- |
| Dynamic_RC 5R1C | 256.055 | 0.000 | 0.000 | 0.000 | 0.000 |
| Dynamic_RC 7R2C | 260.982 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS | 259.068 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_simplified zone sum | 257.886 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_simplified collapsed | 252.632 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_VBDD monthly zone sum | 259.068 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_VBDD monthly collapsed | 253.262 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_VBDD linear zone sum | 259.014 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_VBDD linear collapsed | 253.419 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_VBDD fixed zone sum | 248.660 | 0.000 | 0.000 | 0.000 | 0.000 |
| Monthly_SS_VBDD fixed collapsed | 242.368 | 0.000 | 0.000 | 0.000 | 0.000 |

| Model | Imported primary MWh | Import carbon tCO2e | Net energy cost, thousand EUR |
| --- | --- | --- | --- |
| Dynamic_RC 5R1C | 614.532 | 64.014 | 64.014 |
| Dynamic_RC 7R2C | 626.358 | 65.246 | 65.246 |
| Monthly_SS | 621.762 | 64.767 | 64.767 |
| Monthly_SS_simplified zone sum | 618.925 | 64.471 | 64.471 |
| Monthly_SS_simplified collapsed | 606.318 | 63.158 | 63.158 |
| Monthly_SS_VBDD monthly zone sum | 621.762 | 64.767 | 64.767 |
| Monthly_SS_VBDD monthly collapsed | 607.829 | 63.315 | 63.315 |
| Monthly_SS_VBDD linear zone sum | 621.633 | 64.753 | 64.753 |
| Monthly_SS_VBDD linear collapsed | 608.205 | 63.355 | 63.355 |
| Monthly_SS_VBDD fixed zone sum | 596.785 | 62.165 | 62.165 |
| Monthly_SS_VBDD fixed collapsed | 581.683 | 60.592 | 60.592 |

[Archived figure: Monthly carrier and renewable results — full archive](../../docs/validation_archive.md#reports-shared-energy-figures-19-9400f1b21cb527d7-monthly-png)

[Individual-zone and collapsed-case service tables](zone_reports/19-9400f1b21cb527d7.md) show useful and delivered heating/cooling separately, DHW conversion, solar heat allocation and common zone electrical loads.

### Test building 4

| Model | Electricity imported | Gas imported | PV self-use | PV exported | ST used |
| --- | --- | --- | --- | --- | --- |
| Dynamic_RC 5R1C | 141.072 | 1,613.558 | 89.173 | 78.249 | 0.000 |
| Dynamic_RC 7R2C | 137.988 | 1,673.470 | 90.197 | 77.225 | 0.000 |
| Monthly_SS | 132.090 | 1,586.202 | 103.008 | 64.413 | 0.000 |
| Monthly_SS_simplified zone sum | 130.520 | 1,574.638 | 102.502 | 64.920 | 0.000 |
| Monthly_SS_simplified collapsed | 130.704 | 1,567.479 | 102.416 | 65.006 | 0.000 |
| Monthly_SS_VBDD monthly zone sum | 132.090 | 1,586.202 | 103.008 | 64.413 | 0.000 |
| Monthly_SS_VBDD monthly collapsed | 131.706 | 1,578.978 | 102.804 | 64.618 | 0.000 |
| Monthly_SS_VBDD linear zone sum | 133.153 | 1,585.636 | 102.450 | 64.972 | 0.000 |
| Monthly_SS_VBDD linear collapsed | 132.672 | 1,578.189 | 102.307 | 65.115 | 0.000 |
| Monthly_SS_VBDD fixed zone sum | 120.917 | 1,572.358 | 100.818 | 66.604 | 0.000 |
| Monthly_SS_VBDD fixed collapsed | 120.137 | 1,567.267 | 100.818 | 66.604 | 0.000 |

| Model | Imported primary MWh | Import carbon tCO2e | Net energy cost, thousand EUR |
| --- | --- | --- | --- |
| Dynamic_RC 5R1C | 2,113.487 | 357.980 | 175.793 |
| Dynamic_RC 7R2C | 2,171.989 | 369.191 | 180.476 |
| Monthly_SS | 2,061.839 | 350.263 | 171.916 |
| Monthly_SS_simplified zone sum | 2,045.349 | 347.558 | 170.452 |
| Monthly_SS_simplified collapsed | 2,037.918 | 346.172 | 169.849 |
| Monthly_SS_VBDD monthly zone sum | 2,061.839 | 350.263 | 171.916 |
| Monthly_SS_VBDD monthly collapsed | 2,052.970 | 348.722 | 171.157 |
| Monthly_SS_VBDD linear zone sum | 2,063.766 | 350.415 | 172.097 |
| Monthly_SS_VBDD linear collapsed | 2,054.421 | 348.806 | 171.298 |
| Monthly_SS_VBDD fixed zone sum | 2,019.795 | 344.701 | 167.745 |
| Monthly_SS_VBDD fixed collapsed | 2,012.323 | 343.488 | 167.092 |

[Archived figure: Monthly carrier and renewable results — full archive](../../docs/validation_archive.md#reports-shared-energy-figures-20-f5ca38f748a1d6ea-monthly-png)

[Individual-zone and collapsed-case service tables](zone_reports/20-f5ca38f748a1d6ea.md) show useful and delivered heating/cooling separately, DHW conversion, solar heat allocation and common zone electrical loads.

### Test building 5

| Model | Electricity imported | Gas imported | PV self-use | PV exported | ST used |
| --- | --- | --- | --- | --- | --- |
| Dynamic_RC 5R1C | 793.836 | 3,774.425 | 0.000 | 0.000 | 67.125 |
| Dynamic_RC 7R2C | 789.161 | 3,868.674 | 0.000 | 0.000 | 67.125 |
| Monthly_SS | 816.881 | 3,682.104 | 0.000 | 0.000 | 52.469 |
| Monthly_SS_simplified zone sum | 810.372 | 3,657.499 | 0.000 | 0.000 | 52.469 |
| Monthly_SS_VBDD monthly zone sum | 816.881 | 3,682.104 | 0.000 | 0.000 | 52.469 |
| Monthly_SS_VBDD linear zone sum | 818.253 | 3,683.232 | 0.000 | 0.000 | 52.469 |
| Monthly_SS_VBDD fixed zone sum | 787.132 | 3,646.670 | 0.000 | 0.000 | 52.469 |

| Model | Imported primary MWh | Import carbon tCO2e | Net energy cost, thousand EUR |
| --- | --- | --- | --- |
| Dynamic_RC 5R1C | 6,057.075 | 953.344 | 538.157 |
| Dynamic_RC 7R2C | 6,149.528 | 971.025 | 545.471 |
| Monthly_SS | 6,010.829 | 940.641 | 535.610 |
| Monthly_SS_simplified zone sum | 5,968.142 | 934.093 | 531.768 |
| Monthly_SS_VBDD monthly zone sum | 6,010.829 | 940.641 | 535.610 |
| Monthly_SS_VBDD linear zone sum | 6,015.362 | 941.210 | 536.054 |
| Monthly_SS_VBDD fixed zone sum | 5,900.454 | 926.117 | 524.983 |

[Archived figure: Monthly carrier and renewable results — full archive](../../docs/validation_archive.md#reports-shared-energy-figures-21-6f4b6612125fb3a0-monthly-png)

[Individual-zone and collapsed-case service tables](zone_reports/21-6f4b6612125fb3a0.md) show useful and delivered heating/cooling separately, DHW conversion, solar heat allocation and common zone electrical loads.

## Differences and temporal approximation

[differences_vs_qss.csv — full archive](../../docs/validation_archive.md#reports-shared-energy-differences-vs-qss-csv) contains annual signed/percentage differences, monthly RMSE and the largest differing month for every model/building and selected carrier/impact quantities. A collapsed case is compared with the QSS independent-zone sum and is a distinct approximation.

[dynamic_monthly_aggregation.csv — full archive](../../docs/validation_archive.md#reports-shared-energy-dynamic-monthly-aggregation-csv) holds an isolated check: identical dynamic thermal loads are converted at native time steps and again after monthly aggregation, with PV/ST removed. Constant efficiency must commute with aggregation. The additional sensitivity uses the supplied Model 3 example linear heat-pump/chiller curves; these curves are not calibrated to these buildings. With variable performance, sum(Q/COP(T)) generally differs from sum(Q)/COP(mean(T)).

[linear_sensitivity_annual.csv](linear_sensitivity_annual.csv) and [its resolved configuration](linear_sensitivity_config.json) show the resulting whole-building carrier/impact sensitivity. Polynomial curves are supported and covered by analytical tests; no equipment-specific polynomial coefficients are invented for the baseline.

[pv_factor_sensitivity.csv](pv_factor_sensitivity.csv) reports overlap factors 0, 0.65 and 1 for the PV buildings. They span zero self-use to the maximum monthly overlap. Dynamic matching can be assessed alongside these cases, but the illustrative monthly factor is not fitted to the dynamic result.

[pv_matching_diagnostics.csv — full archive](../../docs/validation_archive.md#reports-shared-energy-pv-matching-diagnostics-csv) reports each month's achieved overlap factor, fraction of PV production self-consumed and electrical self-sufficiency. For dynamic results these factors are derived from actual interval matching and provide an independent diagnostic for later ISO-factor comparison; they are not reused as monthly input factors.

## Individual zones and collapsed buildings

[thermal_zone_monthly.csv](thermal_zone_monthly.csv) retains original zone heating/cooling and separate AHU demands. [zone_service_monthly.csv — full archive](../../docs/validation_archive.md#reports-shared-energy-zone-service-monthly-csv) adds technology/carrier conversion, DHW and the proportional solar-thermal allocation. Its sums are checked against building service totals. A collapsed result has one synthetic zone; it cannot reconstruct separate upper/lower-zone demands.

Annual forms are also provided in [thermal_zone_annual.csv](thermal_zone_annual.csv), [zone_service_annual.csv](zone_service_annual.csv) and [service_annual.csv](service_annual.csv). [zone_ancillary_annual.csv](zone_ancillary_annual.csv) and its monthly counterpart expose actual appliance and fan energy for each physical zone, common to every solver. Building base auxiliaries remain a building-level quantity.

## Reproducibility and limits

Run `python -m dt_prototype.energy_carriers.cli --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/<new-directory>` with `src` on PYTHONPATH, or use the installed `dt-energy-carriers` command. Each case directory retains its input energies, evaluated performance, clipping flags and result balances; dynamic interval tables are gzip-compressed CSVs. The manifest records all input/code hashes and software versions.

The new layer is a deterministic performance-curve model without capacity limits, plant staging, heat recovery between heating/cooling, or thermal/electrical storage. Generator-bus solar heat in monthly calculations uses an explicit utilisation factor, not a simulated tank. Renewable production uses the existing roof irradiance mapping. Future ISO-derived monthly matching can replace the input factors without changing the thermal solvers or meter equations.

## Automated test evidence

The completed regression suite contains 273 tests, 0 failures, 0 errors and 0 skips. See [machine-readable test results](test_results.xml) and [delivery audit](delivery_audit.json). The audit also verifies the run's source/input/configuration hashes against the delivered files and checks all generated report links.
