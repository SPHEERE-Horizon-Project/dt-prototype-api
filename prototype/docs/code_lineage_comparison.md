# Comparing DT-Prototype with the imported EUReCA snapshot

The repository contains a pre-refactor archive at
`archive/pre_refactor_sources_20260917.zip`. It is the best local comparison
baseline because it contains the source trees that were actually present before
the packages were consolidated and renamed. A comparison against the current
EUReCA GitHub branch would answer a different question: how the project differs
from a later upstream version.

Run the comparison from the project root:

```powershell
python scripts/compare_code_lineage.py --output outputs/code_lineage_comparison
```

The command writes a Markdown review table and a JSON record containing the
archive hash, source mapping, similarity scores and review bands. The output is
generated under `outputs/`, which is intentionally excluded from source
versioning.

The comparison maps these source trees:

| Current code | Archived source candidate |
|---|---|
| `src/dt_prototype/dynamic/` | `DYNAMIC RC/src/mypackage/` |
| `src/dt_prototype/monthly/` | `SEMI-STATIONARY/src/semistationary/` |
| `src/dt_prototype/integration/` | `SPREADSHEETS INTEGRATION/src/model3_integration/` |
| `src/dt_prototype/integration/model3/` | `SPREADSHEETS INTEGRATION/third_party/model3_legacy/` |
| `src/dt_prototype/common/` | the three relevant archived source trees, selecting the best match |

Package names, variable names, strings and numeric literals are normalized
before token comparison. This makes a copied module visible after a package
rename, but it is only an indicator. A high score is evidence to inspect the
file’s history and preserve attribution; a low score is not proof that no
copyrightable material remains. The report should be read alongside the
source inventory, exact file hashes and any available Git history.

The result cannot determine whether a file is legally a derivative work. It
also cannot identify copied material when the imported snapshot is incomplete.
In this project, the Model 3 snapshot has no known upstream licence, so its
provenance must be resolved independently even if the comparison shows heavy
modification.
