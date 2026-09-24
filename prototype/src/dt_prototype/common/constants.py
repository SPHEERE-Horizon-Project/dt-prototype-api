"""Physical constants and standard surface heat-transfer coefficients (SI units).

Shared by the preprocessing layer (U-value / equivalent-layer derivation) and
the simulation layer (RC network parameters). Values migrated from
``reference_building.construction`` and ``reference_building.fluids_properties``.
"""

# Air properties at standard indoor conditions
AIR_DENSITY = 1.2  # [kg/m3]
AIR_SPECIFIC_HEAT = 1006.0  # [J/(kg K)]

# Water properties (the retained reference fluids_properties)
WATER_DENSITY = 1000.0  # [kg/m3]
WATER_SPECIFIC_HEAT = 4186.0  # [J/(kg K)]
# Domestic hot water delivery temperature (the retained reference schedule_properties)
DHW_TARGET_TEMPERATURE = 45.0  # [°C]

# Water vapour properties (the retained reference fluids_properties)
VAPOUR_LATENT_HEAT = 2_501_000.0  # [J/kg]
VAPOUR_SPECIFIC_HEAT = 1_875.0  # [J/(kg K)]

STEFAN_BOLTZMANN = 5.67e-8  # [W/(m2 K4)]

# Combined (convective + radiative) surface heat transfer coefficients
# [W/(m2 K)], per construction type, ISO 6946 as used in the retained reference.
# "outside" is the external film, "inside" the internal film.
SURFACE_HEAT_TRANSFER_COEF: dict[str, dict[str, float]] = {
    "ExtWall": {"outside": 25.0, "inside": 7.7},
    "Roof": {"outside": 25.0, "inside": 7.7},
    "GroundFloor": {"outside": 1000.0, "inside": 7.7},
    "IntWall": {"outside": 7.7, "inside": 7.7},
    "IntCeiling": {"outside": 6.7, "inside": 6.7},
    "IntFloor": {"outside": 6.7, "inside": 6.7},
}

# Radiative part of the internal film coefficient [W/(m2 K)] (VDI 6007 value)
RADIATIVE_HEAT_TRANSFER_COEF = 5.0

# Surface types treated as external (non-adiabatic, "AW" in VDI 6007 notation)
EXTERNAL_SURFACE_TYPES = ("ExtWall", "Roof", "GroundFloor")
# Surface types treated as internal (adiabatic, "IW" in VDI 6007 notation)
INTERNAL_SURFACE_TYPES = ("IntWall", "IntCeiling", "IntFloor")

# Ground reflectance (albedo) used for solar irradiance on tilted surfaces
GROUND_ALBEDO = 0.2
