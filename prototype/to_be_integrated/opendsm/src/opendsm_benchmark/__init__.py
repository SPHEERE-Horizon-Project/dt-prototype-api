"""
opendsm_benchmark - OpenDSM hourly models as the benchmark of the energy_insight project.

Reads the cleaned hourly datasets of energy_insight, or one plain CSV file per period (stand-alone use),
converts them to OpenDSM's input (local standard time, °F, weather), fits OpenDSM's hourly model with the
solar (temperature + irradiance) and the temperature-only variants, and predicts the load in sample and out
of sample on the folds that energy_insight also uses. It runs on its own (python run_benchmark.py) in its
own environment and does not import energy_insight.

    settings.py        config.toml (checked), standard time of a site
    inputs.py          the data, from either source (read, checked)
    preprocess.py      dedicated pre-processing to OpenDSM's input
    folds.py           blocked cross-validation folds
    opendsm_runner.py  OpenDSM fit / predict (library used unchanged)
    response.py        daily temperature response per temporal cluster (figure of energy_insight)
    metrics.py         accuracy measures
    pipeline.py        the run, end to end (CLI)
"""
__version__ = "1.2.0"
