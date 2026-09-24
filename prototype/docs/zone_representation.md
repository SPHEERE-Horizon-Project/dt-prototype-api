# Single-zone support and comparison terminology

| Label | Input meaning | Calculation |
|---|---|---|
| Simplified single zone | Native one-zone building | One Model 3 case; no second-zone input |
| Simplified single zone collapsed | Complete two-zone building mapped to one equivalent zone | Combine physical and operating inputs, then solve once |
| Simplified zone sum | Two distinct zones retained | Solve each zone independently and add demands |

Test buildings 1–4 have two zones. Test building 5 is natively single-zone and is not collapsed even when shown in the same comparison column. CSV `representation` fields make this explicit.

The independent single-zone execution check removed both `Lower End Use` and `Upper End Use` from a copied Test building 5 input while preserving `End Use=services` and all physics. Both dynamic networks, monthly QSS routes and simplified Model 3 ran and reproduced the prior outputs. Evidence: `outputs/20260917_dt_prototype_single_zone/verification.json`.

The common geometry parser generates a second zone only when a nonempty lower end use differs from the upper/main end use and the building has at least two floors. To define one zone, supply the main `End Use` and omit the lower/upper split. No zero-area or dummy zone is required.

The mapper flags `two_zone_to_single_zone` only for a complete multi-zone collapse. Deleting part of a genuine two-zone input is not equivalent: it loses the separate end-use assumptions. CLI `--zone-mode collapsed` performs the explicit mapping; `sum` retains independent solves; `both` saves both and uses the zone sum for headline outputs.

The existing engines use independent zones, not coupled multi-zone airflow/heat transfer. That limitation is unchanged.
