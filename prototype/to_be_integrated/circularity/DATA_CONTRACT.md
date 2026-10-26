# Circularity data contract

## Material/component mode

Each record in `materials` represents one material belonging to one construction component. Required identity and quantity fields are `component_id`, `component_name`, `material_id`, `material_name`, and `mass_kg`. Fractions are numbers from 0 to 1:

- `recycled_input_fraction` ($F_R$) and `reused_input_fraction` ($F_U$), whose sum must not exceed 1.
- `collected_for_recycling_fraction` ($C_R$) and `collected_for_reuse_fraction` ($C_U$), whose sum must not exceed 1.
- `recycled_feedstock_efficiency` ($E_F$), which must be positive when recycled input is used.
- `end_of_use_recycling_efficiency` ($E_C$).

Utility inputs are `service_life_years`, `industry_average_life_years`, `use_intensity`, and `industry_average_use_intensity`. The two intensity values default to 1 in Python. A component score is the mass-weighted mean of its material scores.

## Building mode

Each record in `components` requires `component_id`, `mass_kg`, and a pre-computed `mci` from 0 to 1. `component_name` and `building_layer` support reporting. The building and layer scores are mass-weighted means. Economic value, environmental impact and floor area are not weighting factors in this method.

Future integration should pass stable component IDs, measured or modelled mass, the MCI scenario provenance, and a flag distinguishing demonstrated recovery from future design assumptions.

Component IDs must be unique in building mode. Material mode rejects duplicate
`(component_id, material_id)` pairs and inconsistent names for the same component.
All required identities are non-null and non-empty. Reusing a material ID across
different components is allowed; duplicating one row within a component would
otherwise add its mass twice.
