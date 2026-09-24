"""Dynamic wall parameters for the RC thermal networks.

Faithful ports of the transfer-matrix mathematics from the retained reference:

- :func:`iso13790_kappa` — areal heat capacities k_int / k_est
  (``reference_building.construction.Construction._ISO13790_params``);
- :func:`vdi6007_surface_params` — R1/C1 of one surface
  (``Construction._VDI6007_params`` + ``_VDI6007_surface_params``);
- :func:`impedance_parallel`, :func:`tri2star`, :func:`long_wave_radiation`
  (``reference_building._VDI6007_auxiliary_functions``).

All functions are pure (no side effects, NFR-04). SI units.
"""

from __future__ import annotations

import numpy as np

from dt_prototype.common.preprocessing.archetypes import ConstructionSpec


def iso13790_kappa(construction: ConstructionSpec) -> tuple[float, float]:
    """Internal/external areal heat capacity [J/(m2 K)] of a construction
    (ISO 13786 transfer matrix, period 24 h), as in the retained reference.

    Parameters
    ----------
    construction : ConstructionSpec
        Layered construction (outside → inside).

    Returns
    -------
    tuple of float
        ``(k_int, k_est)``: heat capacity seen from the inside / outside.
    """
    period = 86400.0
    thick = np.array([l.thickness for l in construction.layers])
    cond = np.array([l.conductivity for l in construction.layers])
    dens = np.array([l.density for l in construction.layers])
    cp = np.array([l.specific_heat for l in construction.layers])

    sigma = np.sqrt((period / np.pi) * cond / (dens * cp))  # penetration depth
    eps = thick / sigma

    n = len(construction.layers)
    Z = np.zeros((2, 2, n), complex)
    for i in range(n):
        ch, sh, c, s = np.cosh(eps[i]), np.sinh(eps[i]), np.cos(eps[i]), np.sin(eps[i])
        Z[0, 0, i] = ch * c + 1j * sh * s
        Z[1, 1, i] = Z[0, 0, i]
        Z[0, 1, i] = -(sigma[i] / (2 * cond[i])) * (sh * c + ch * s + 1j * (ch * s - sh * c))
        Z[1, 0, i] = -(cond[i] / sigma[i]) * (sh * c - ch * s + 1j * (sh * c + ch * s))
    Z_si = np.eye(2)
    Z_si[0, 1] = -construction.r_si
    Z_se = np.eye(2)
    Z_se[0, 1] = -construction.r_se
    M = Z[:, :, -1]
    for i in range(n - 2, -1, -1):
        M = np.matmul(M, Z[:, :, i])
    M = np.matmul(Z_se, np.matmul(M, Z_si))

    k_est = (period / (2 * np.pi)) * np.abs((M[0, 0] - 1) / M[0, 1])
    k_int = (period / (2 * np.pi)) * np.abs((M[1, 1] - 1) / M[0, 1])
    return float(k_int), float(k_est)


def _vdi6007_layer_matrix(construction: ConstructionSpec) -> dict[str, np.ndarray]:
    """VDI 6007 complex chain matrices of a construction for the two
    reference periods (2 and 7 days), outside → inside."""
    matrices = {}
    for days in (2, 7):
        omega = 2.0 * np.pi / (86400.0 * days)
        M = None
        for layer in construction.layers:
            r, c = layer.thermal_resistance, layer.areal_heat_capacity
            arg = np.sqrt(0.5 * omega * r * c)
            ch, sh, co, si = np.cosh(arg), np.sinh(arg), np.cos(arg), np.sin(arg)
            A = np.zeros((2, 2), complex)
            A[0, 0] = ch * co + 1j * sh * si
            A[1, 1] = A[0, 0]
            A[0, 1] = r / (2 * arg) * (ch * si + sh * co) + 1j * (r / (2 * arg)) * (ch * si - sh * co)
            A[1, 0] = -arg / r * (ch * si - sh * co) + 1j * (arg / r) * (ch * si + sh * co)
            M = A if M is None else np.matmul(M, A)
        matrices[days] = M
    return matrices


def vdi6007_surface_params(
    construction: ConstructionSpec, area: float, asim: bool
) -> tuple[float, float]:
    """Dynamic resistance R1 [K/W] and capacitance C1 [J/K] of one surface
    (VDI 6007 section 6.4), as in the retained reference.

    Parameters
    ----------
    construction : ConstructionSpec
        Layered construction.
    area : float
        Surface (opaque) area [m2].
    asim : bool
        True for asymmetrically loaded components (external, "AW"): the
        corrected capacitance C1_korr is used. False for internal ("IW").

    Returns
    -------
    tuple of float
        ``(R1, C1)``.
    """
    if area <= 0.0:
        area = 1e-7
    rw = construction.net_resistance / area
    matrices = _vdi6007_layer_matrix(construction)

    results = {}
    for days, a in matrices.items():
        omega = 2.0 * np.pi / (86400.0 * days)
        re11, im11 = np.real(a[1, 1]), np.imag(a[1, 1])
        re01, im01 = np.real(a[0, 1]), np.imag(a[0, 1])
        R1 = (1.0 / area) * ((re11 - 1) * re01 + im11 * im01) / ((re11 - 1) ** 2 + im11**2)
        if not asim:
            C1 = area * ((re11 - 1) ** 2 + im11**2) / (omega * (re01 * im11 - (re11 - 1) * im01))
        else:
            C1 = (
                area
                * (1.0 / (omega * R1 * area))
                * (rw * area - re01 * re11 - im11 * im01)
                / (re11 * im01 - re01 * im11)
            )
        results[days] = (R1, C1)

    # Choice of the reference period (VDI 6007 criterion, as in the retained reference)
    rr = results[2][0] / results[7][0]
    cr = results[2][1] / results[7][1]
    if (rr > 0.99 and cr < 0.95) or ((rr < 0.95 and cr < 0.95) and abs(rr - cr) > 0.3):
        return results[2]
    return results[7]


def impedance_parallel(R: np.ndarray, C: np.ndarray, t_ra: float = 5.0) -> tuple[float, float]:
    """Equivalent (R1, C1) of surfaces in parallel via complex impedances
    (VDI 6007 eq. 22; reference period ``t_ra`` days), as in the retained reference.

    Parameters
    ----------
    R, C : numpy.ndarray
        Per-surface resistances [K/W] and capacitances [J/K].
    t_ra : float
        Reference period [days].

    Returns
    -------
    tuple of float
        Equivalent ``(R1, C1)``.
    """
    omega = 2.0 * np.pi / (86400.0 * t_ra)
    z = R + 1j / (omega * np.asarray(C))
    z_eq = 1.0 / np.sum(1.0 / z)
    return float(np.real(z_eq)), float(1.0 / (omega * np.imag(z_eq)))


def tri2star(t1: float, t2: float, t3: float) -> tuple[float, float, float]:
    """Triangle → star transformation of three resistances (VDI 6007)."""
    total = t1 + t2 + t3
    return t2 * t3 / total, t1 * t3 / total, t2 * t1 / total


def long_wave_radiation(theta_a: np.ndarray, ssw: float = 1.0) -> tuple[np.ndarray, ...]:
    """Sky/ground long-wave irradiance and equivalent temperatures (VDI 6007),
    as in the retained reference.

    Parameters
    ----------
    theta_a : numpy.ndarray
        Outdoor air temperature [°C].
    ssw : float
        Clear-sky factor [0-1] (1 = clear sky).

    Returns
    -------
    tuple of numpy.ndarray
        ``(E_atm, E_ground, theta_ground, theta_sky)``: irradiance from the
        sky vault and ground [W/m2], ground and sky equivalent temperatures
        [°C].
    """
    t_k = 273.15 + theta_a
    ea_1 = 9.9 * 5.671e-14 * t_k**6
    alpha_l = 2.30 - 7.37e-3 * t_k
    alpha_m = 2.48 - 8.23e-3 * t_k
    alpha_h = 2.89 - 1.00e-2 * t_k
    cloud = (1.0 - ssw) / 3.0
    ea = ea_1 * (1 + (alpha_l + (1 - cloud) * alpha_m + ((1 - cloud) ** 2) * alpha_h) * cloud**2.5)
    ee = -(0.93 * 5.671e-8 * t_k**4 + (1 - 0.93) * ea)
    theta_ground = ((-ee / (0.93 * 5.67)) ** 0.25) * 100.0 - 273.15
    theta_sky = ((ea / (0.93 * 5.67)) ** 0.25) * 100.0 - 273.15
    return ea, ee, theta_ground, theta_sky
