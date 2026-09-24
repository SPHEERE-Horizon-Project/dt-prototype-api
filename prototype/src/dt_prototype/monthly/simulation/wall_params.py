"""ISO 13790 construction heat-capacity parameters."""

from __future__ import annotations

import numpy as np

from dt_prototype.common.preprocessing.archetypes import ConstructionSpec


def iso13790_kappa(construction: ConstructionSpec) -> tuple[float, float]:
    """Return internal/external areal heat capacity (J/(m² K)) for a 24 h period."""
    period = 86400.0
    thickness = np.array([layer.thickness for layer in construction.layers])
    conductivity = np.array([layer.conductivity for layer in construction.layers])
    density = np.array([layer.density for layer in construction.layers])
    specific_heat = np.array([layer.specific_heat for layer in construction.layers])
    sigma = np.sqrt((period / np.pi) * conductivity / (density * specific_heat))
    epsilon = thickness / sigma

    matrices = np.zeros((2, 2, len(construction.layers)), complex)
    for index, value in enumerate(epsilon):
        ch, sh, cosine, sine = np.cosh(value), np.sinh(value), np.cos(value), np.sin(value)
        matrices[0, 0, index] = matrices[1, 1, index] = ch * cosine + 1j * sh * sine
        matrices[0, 1, index] = -(sigma[index] / (2 * conductivity[index])) * (
            sh * cosine + ch * sine + 1j * (ch * sine - sh * cosine)
        )
        matrices[1, 0, index] = -(conductivity[index] / sigma[index]) * (
            sh * cosine - ch * sine + 1j * (sh * cosine + ch * sine)
        )
    inside = np.eye(2)
    outside = np.eye(2)
    inside[0, 1] = -construction.r_si
    outside[0, 1] = -construction.r_se
    matrix = matrices[:, :, -1]
    for index in range(len(construction.layers) - 2, -1, -1):
        matrix = matrix @ matrices[:, :, index]
    matrix = outside @ matrix @ inside
    k_external = period / (2 * np.pi) * abs((matrix[0, 0] - 1) / matrix[0, 1])
    k_internal = period / (2 * np.pi) * abs((matrix[1, 1] - 1) / matrix[0, 1])
    return float(k_internal), float(k_external)
