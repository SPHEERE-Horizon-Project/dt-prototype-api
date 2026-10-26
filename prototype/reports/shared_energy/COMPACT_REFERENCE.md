# Compact monthly reference fixture

This directory contains selected monthly/annual summaries and the original
historical manifest. It supports the supplied monthly inverse example and
routine tests. It is not a complete run directory: detailed `cases/` interval
tables, some allocations and original figures are in the optional archive.

For the strict 318-table reproduction check, use
`validation_archive/reports/shared_energy` as the reference. Do not compare
the compact fixture to a complete run or remove checks to make it pass.
For hourly inverse fitting, generate a new forward run and point the source
at its completed `energy` directory.

See [archive instructions](../../docs/validation_archive.md).
