"""Thermal model implementations. Every module in this package is imported
automatically so that models self-register (open/closed principle, FR-11)."""

import importlib
import pkgutil

# EXTENSION POINT (FR-11): to add a new thermal model, create a new module in
# this package that defines a ThermalModel subclass decorated with
# @register_model. The loop below imports it automatically — no edits to any
# existing simulation module are required.
for _mod_info in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_mod_info.name}")
