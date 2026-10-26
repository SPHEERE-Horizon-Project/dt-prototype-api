# Optional adiabatic surface boundaries

The shared geometry input supports `boundary_condition` on individual surfaces.
Use it to impose zero heat transfer across selected walls, roofs or floors
without changing their physical surface type, construction or inventory area.
All four thermal solver families receive the setting through shared inputs.

## Input values and compatibility

| Value | Meaning |
| --- | --- |
| `auto` | Default. `ExtWall`, `Roof`, `GroundFloor` retain their existing external/ground treatment. `IntWall`, `IntFloor`, `IntCeiling` retain their existing internal-mass/adiabatic treatment. |
| `adiabatic` | Exclude this surface from external transmission and direct outdoor solar/sky forcing. Keep its construction and physical area. |

The optional `surfaces.csv` column may be omitted entirely. A blank CSV cell
also means `auto`. Python/serialized geometry defaults to `auto` when the field
is omitted. Explicit JSON `null`, misspellings and unsupported conditions are
rejected. Values are lowercase. Existing project schema version 1.0 and runner
arguments remain valid. Canonical table/JSON writers now include the field, so
new serialized geometry contains extra metadata even when results are unchanged.

An extra column with this name was ignored before this addition. Check any
privately prepared files that already contain it: it now has a defined effect.
The supplied baseline geometry files contain no such column.

## CSV example

Use the normal tabular geometry route, selected by `geometry_format=tabular` in
the project configuration. Keep `buildings.csv` and `zones.csv` alongside
`surfaces.csv`. For a 60 m2 wall whose 20 m2 interface should be adiabatic:

```csv
building_id,zone_id,surface_index,surface_type,area_m2,azimuth_deg,tilt_deg,boundary_condition
example,single,0,ExtWall,40,180,90,auto
example,single,1,ExtWall,20,180,90,adiabatic
```

These are two surface records within a complete zone, not a complete input
dataset. Include its other real surfaces and internal mass as appropriate.
Surface indices must be unique within each building/zone. Areas must be positive.
Keep conditioned floor area, volume and schedules consistent with the selected
portion of the building. Do not set a surface's area or U-value to zero to
simulate the boundary.

The equivalent Python input is:

```python
SurfaceSpec("ExtWall", 20.0, azimuth=180.0, tilt=90.0,
            boundary_condition="adiabatic")
```

Serialized `BuildingGeometry`/`BuildingInput` also retains the field in each
surface object. GeoJSON/cadastral extrusion still generates its established
one/two-zone geometry with default boundaries; it does not infer cut surfaces,
party walls or arbitrary room subdivisions. Prepare explicit surface tables or
geometry objects when applying this setting to a subset.

## Calculation boundary

For a surface i, the contribution to external transmission is:

\[
H_i = b_i\left(U_{op,i}A_{op,i}+U_{w,i}A_{w,i}\right),
\qquad b_i=0\text{ for an adiabatic boundary}.
\]

The physical opaque/glazed split remains that obtained from the envelope.
An override does not invent an all-opaque surface or alter its material layers.
Adiabatic glazing contributes neither outdoor window transmission nor outdoor
solar gains. The existing massless-window approximation remains in use.

Dynamic_RC 5R1C and Monthly_SS retain the original opaque surface's effective
capacity and total area. Dynamic_RC 7R2C puts the surface into its internal-mass
network, using the original construction with its existing internal-element
parameterisation. Its equivalent network capacitances can change when a
surface moves between external and internal networks. This is the same
uncoupled/adiabatic convention used for internal elements, not an inter-zone
heat-flow calculation.

Monthly_SS_simplified receives updated transmission, ground, gains and capacity
through its existing adapter. Its mass-class and monthly-airflow approximations
remain unchanged. Monthly_SS_VBDD receives the boundary through its prepared
monthly inputs for the monthly, linear-solar and fixed-utilisation variants.
The verification spreadsheets consume prepared monthly coefficients and gains;
they do not read this surface column directly. See
[workbook instructions](workbook_instructions.md).

The flag changes thermal exposure only. Physical surface area, source identity,
construction and derived glazing are retained. Roof irradiance remains available
for PV and solar-thermal production on a physical `Roof`, so its thermal override
does not silently remove renewable generation. To represent a middle-storey
ceiling without a real roof/renewable resource, use the appropriate physical
surface type and subset allocation. Review equipment and renewable ownership
separately. LCC/LCA/MCI inventories must not discard physical assets because
their thermal boundary is adiabatic.

## Limits

- Existing zones remain thermally uncoupled. No heat transfer, air transfer or
  adjacent-space temperature is introduced by this setting.
- Adiabatic is a modelling assumption, not a guarantee that a subset reproduces
  the whole-building result. Omitted spaces may have different temperatures,
  controls or gains. Unheated-space and neighbour-temperature boundary models
  are separate developments.
- Fully enclosed dynamic zones remain unsupported: 5R1C needs positive exposed
  opaque conductance; 7R2C needs both external and internal surface networks.
  Unsupported inputs now fail with an actionable error. Do not add fictitious
  exposure to bypass it. Monthly methods still require valid positive
  conductance/time-constant inputs where their equations demand them.
- Subsetting does not automatically allocate ventilation, DHW, appliance gains,
  HVAC capacity, PV ownership or external asset assessments. Do not duplicate
  shared interfaces in the internal-mass estimates.

## Verification

`tests/test_adiabatic_boundaries.py` covers the optional input, legacy
serialization, invalid settings, partial surfaces, unchanged construction and
capacity, suppressed outdoor forcing, both ground adapters, controlled monthly
balances, independent zones, renewable preservation and explicit rejection of
unsupported dynamic geometry.

The controlled no-gain/no-airflow case retains the same construction and mass.
Making half a 100 m2 wall with U=0.5 W/(m2 K) adiabatic changes H from 50 to
25 W/K. At 20 C indoors and 0 C outdoors, January demand changes from 744 to
372 kWh in Monthly_SS, Monthly_SS_simplified and Monthly_SS_VBDD.

The implementation report and machine-readable evidence are in
[the boundary verification report](../reports/adiabatic_boundaries_20261015/implementation_report.md).
