# Remaining development gaps

Current implementation: [24 October 2026](reliability_improvements_20261023.md),
following the [22 October review](reliability_review_20261022.md).
The run instructions for all current paths are [here](running_forward_and_inverse.md).

The [15 October 2026 code audit](code_audit_20261015.md) records corrected input,
asset-assessment, standalone-module and reproduction-tool defects. The expanded
322-test suite and a fresh 318-table energy reproduction passed. The items below
remain model-development limitations rather than defects corrected by that audit.

Current extension status: the [shared energy layer](shared_energy_layer.md) and
[monthly energy workbooks](workbook_instructions.md) now cover service conversion,
carriers, renewables and impacts. The limitations below remain physical/model
development questions. Monthly ISO-factor provenance, measured validation,
storage and more complex dispatch remain future work; spreadsheet agreement
does not resolve them.

The refactor removes package/input duplication and adds independent commands with shared inputs. It preserves these observed limitations:

- Dynamic and monthly cooling differ materially; closeness of annual heating does not establish accuracy. Use the saved component/monthly plots to investigate controls, gains, mass and AHU assumptions.
- Enabling plants changes emitter convective/radiative fractions and can therefore change useful demand. A future systems separation must preserve this behaviour explicitly before changing it.
- AHU conditioning can operate outside the zone heating season when airflow is scheduled. Confirm intended availability before changing the baseline.
- Signed net AHU loads do not expose every coil/reheat/latent component for all possible humidity-control settings. Current comparison uses the supplied cases.
- Weather processing supports a full 8,760-record non-leap year. Leap-year requests and missing/sentinel values in consumed weather fields now fail clearly; full leap-year support and independent solar-reference coverage remain future work.
- Ground treatment is a retained 0.7-U approximation; simplified mass classes, airflow and gain aggregation deliberately differ from detailed models.
- Optional [adiabatic surface overrides](adiabatic_boundaries.md) now allow selected boundaries without retyping their construction. Zones remain uncoupled; arbitrary geometry cuts, adjacent-space temperatures and fully enclosed dynamic networks remain future work.
- Initial state is 15 degrees C without a new warm-up procedure. Plant sizing changes carrier energy even where sensible loads match.
- The historical Model 3 calibration path is retained for compatibility. Current measured-meter work uses `Inverse_models`, exposing the retained monthly 5P fitter and OpenDSM billing/hourly with explicit train/validation and prediction contracts.
- The [OpenDSM compatibility layer](opendsm_compatibility.md) resolves the native zero-coefficient hourly-metrics exception for buildings 1 and 18. All requested fits complete; native qualification warnings remain inspectable. Native uncertainty is still missing in these supplied cases and has not been recalibrated.
- The common CLI isolates per-building solver failures, but preprocessing still fails early on malformed district inputs; resumability and 10/100/1,000-building benchmarks are future work.
- CLI detail/mapping paths and 5P figure filenames are now bounded and hashed. Keep output roots reasonably short; the operating system can still limit total path length.
- Provenance/licence and normative-standard evidence remain incomplete. No compliance or empirical accuracy claim is made.

These findings do not justify changing physical assumptions during a structural cleanup. They are inputs to the next development stage.

The September audit's resolved defects remain protected by regression tests and
[development guidance](development.md) for the remaining web-platform work.
