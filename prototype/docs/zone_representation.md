# Single-zone support and comparison terminology

The same distinction applies to Monthly_SS_VBDD: solve each independent zone then sum,
or conserve monthly heat-loss moments/gains/capacity and solve a collapsed
alternative. `native_single_zone` remains distinct from `single_zone_collapsed`.
`Dynamic_RC` and `Monthly_SS` reference cases use the native topology. In the
[shared energy layer](shared_energy_layer.md), services are converted at the
building plant after zone summation; PV and grid exchange belong to one building
meter. Zone-service reports expose allocations, not separate zone PV meters.
The [current workbooks](workbook_instructions.md) retain individual-zone thermal
formulas and separate zone-sum/collapsed energy rows.

| Label | Input meaning | Calculation |
|---|---|---|
| Monthly_SS_simplified single zone | Native one-zone building | One Monthly_SS_simplified case; no second-zone input |
| Monthly_SS_simplified collapsed | Complete two-zone building mapped to one equivalent zone | Combine physical and operating inputs, then solve once |
| Monthly_SS_simplified zone sum | Two distinct zones retained | Solve each zone independently and add demands |

Test buildings 1–4 have two zones. Test building 5 is natively single-zone and is not collapsed even when shown in the same comparison column. CSV `representation` fields make this explicit.

The independent single-zone execution check removes both `Lower End Use` and
`Upper End Use` from a copied Test building 5 input while preserving
`End Use=services` and all physics. Both Dynamic_RC networks, Monthly_SS routes
and Monthly_SS_simplified reproduce the prior outputs. This behavior is retained
in the current regression suite; the dated verification artifact remains in
the user's backup.

The common geometry parser generates a second zone only when a nonempty lower end use differs from the upper/main end use and the building has at least two floors. To define one zone, supply the main `End Use` and omit the lower/upper split. No zero-area or dummy zone is required.

The mapper flags `two_zone_to_single_zone` only for a complete multi-zone collapse. Deleting part of a genuine two-zone input is not equivalent: it loses the separate end-use assumptions. CLI `--zone-mode collapsed` performs the explicit mapping; `sum` retains independent solves; `both` saves both and uses the zone sum for headline outputs.

The existing engines use independent zones, not coupled multi-zone airflow/heat transfer. That limitation is unchanged.
