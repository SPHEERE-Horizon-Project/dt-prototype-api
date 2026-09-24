# Third-Party Notices

## EUReCA — MIT Licence

This distribution contains portions derived from and adapted from EUReCA,
including retained or adapted Dynamic RC thermal-balance,
construction-parameter, photovoltaic, and solar-thermal calculation code.

DT-Prototype substantially reorganises and extends that material. It uses a
new `dt_prototype` package structure; shared typed input contracts; JSON,
GeoJSON, and tabular-CSV input adapters; independently runnable Dynamic,
monthly, and simplified tools; reporting; validation; and test infrastructure.
It does not import the original `eureca_building` or `eureca_ubem` packages as
runtime dependencies.

Copyright (c) 2024 BETALAB

EUReCA is licensed under the MIT Licence:

MIT License

Copyright (c) 2024 BETALAB

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The EUReCA attribution and MIT Licence impose no research-only or
non-commercial-use restriction.

## DT-Prototype Contributions

Copyright (c) 2026 [LEGAL COPYRIGHT HOLDER]

Except for third-party material identified in this file, DT-Prototype
contributions are licensed under the project MIT Licence in `LICENSE`.

## Semi-stationary Reference Snapshot

The project includes material originating from
`SEMI-STATIONARY/src/semistationary/`, declared as version `1.0.0`.

Imported metadata declares this component to be MIT licensed, but a complete
licence text and authoritative upstream source reference were not supplied.
Before redistributing this component, record the applicable licence text and
upstream provenance.

## Model 3 Legacy Snapshot

The project includes the preserved Model 3 pipeline in
`src/dt_prototype/integration/model3/`.

The imported material has no recorded upstream licence or source repository.
It must not be redistributed until a licence or written permission from its
copyright holder has been obtained and recorded.

## Example Climate Data

The example EPW weather file
`data/examples/ITA_Venezia-Tessera.161050_IGDG.epw` is reproduced from the
imported EUReCA snapshot.

Confirm and record its source and redistribution terms before distributing the
file. Alternatively, exclude it from release packages and require users to
obtain weather data from an authorised source.