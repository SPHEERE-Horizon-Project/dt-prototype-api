# DT-Prototype source inventory

The starting workspace contained three tools with duplicated packages and inputs. A source archive was created before migration: `archive/pre_refactor_sources_20260917.zip`. The migration inventory records file mappings and archive identity. The workspace has no established source Git commit; source hashes identify the executed code.

| Retained component | Original local version | Current ownership and evidence |
|---|---|---|
| Dynamic RC | 0.3.0 package | `dt_prototype.dynamic`; existing dynamic suite plus all hourly-option numeric regression |
| Semi-stationary | 1.0.0 | `dt_prototype.monthly`; original five-building test preserved; duplicated integration copy archived |
| Integration | 0.2.0 | `dt_prototype.integration`; independent Model 3 adapter, mappings, weather checks, reporting and 5P tests |
| Model 3 | Received standalone module | `dt_prototype.integration.model3`; complete source pipeline and reference CSVs preserved together; byte-for-byte golden-output reproduction test |
| Spreadsheet | Seasonal/AHU formula companion | 13 original sheets and 156 monthly result rows; reissued labels, preserved formulas/numeric inputs; artifact-tool recalculation |

Current distribution: DT-Prototype 0.4.0. Dependencies: NumPy, pandas, matplotlib; pytest for development. Exact executed versions are recorded in run manifests and `requirements-verified.txt`.

The original independent suites passed before migration. The retained consolidated suites have 163 tests; six new common-input/independent-execution tests bring the total to 169. One identical monthly regression and one unavailable external-fixture skip were removed from active collection. Their originals remain in the archive.

Source lineage does not establish independent validation. The monthly solver and dynamic static parameterisation share lineage; preprocessing is shared. Model 3 retains separate heat-balance equations. Required attribution is in the licence notices. Exact upstream commit/standard-clause evidence and the legacy Model 3 licence chain remain incomplete and should be resolved before external distribution claims.

The archived pre-refactor source snapshot can be compared with the current
package using `scripts/compare_code_lineage.py`. Its normalized token scores are
screening evidence for likely copied or lightly modified files, not a legal
classification. The comparison must be run against the exact imported snapshot
when assessing provenance; a later upstream EUReCA release is a separate
comparison baseline.

The current case mapping uses generic display names and unchanged stable IDs. Historical source names can be recovered only from the archive when needed for audit.
