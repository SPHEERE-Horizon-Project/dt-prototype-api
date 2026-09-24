# Remaining development gaps

The refactor removes package/input duplication and adds independent commands with shared inputs. It preserves these observed limitations:

- Dynamic and monthly cooling differ materially; closeness of annual heating does not establish accuracy. Use the saved component/monthly plots to investigate controls, gains, mass and AHU assumptions.
- Enabling plants changes emitter convective/radiative fractions and can therefore change useful demand. A future systems separation must preserve this behaviour explicitly before changing it.
- AHU conditioning can operate outside the zone heating season when airflow is scheduled. Confirm intended availability before changing the baseline.
- Signed net AHU loads do not expose every coil/reheat/latent component for all possible humidity-control settings. Current comparison uses the supplied cases.
- Weather processing supports a full 8,760-record non-leap year. Leap-year requests and missing/sentinel values in consumed weather fields now fail clearly; full leap-year support and independent solar-reference coverage remain future work.
- Ground treatment is a retained 0.7-U approximation; simplified mass classes, airflow and gain aggregation deliberately differ from detailed models.
- Initial state is 15 degrees C without a new warm-up procedure. Plant sizing changes carrier energy even where sensible loads match.
- Legacy Model 3 calibration is retained only for compatibility. Real-meter work should use the integration fitter that separates calibration from validation.
- The common CLI isolates per-building solver failures, but preprocessing still fails early on malformed district inputs; resumability and 10/100/1,000-building benchmarks are future work.
- CLI detail/mapping paths and 5P figure filenames are now bounded and hashed. Keep output roots reasonably short; the operating system can still limit total path length.
- Provenance/licence and normative-standard evidence remain incomplete. No compliance or empirical accuracy claim is made.

These findings do not justify changing physical assumptions during a structural cleanup. They are inputs to the next development stage.

See [the September 2026 audit](audit_20260919.md) for resolved defects and
[development guidance](development.md) for the remaining web-platform work.
