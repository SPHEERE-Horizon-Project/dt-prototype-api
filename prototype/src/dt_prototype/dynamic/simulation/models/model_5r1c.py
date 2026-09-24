"""5R1C thermal model (ISO 13790) — FR-09.

Faithful port of the retained reference's ``ThermalZone._ISO13790_params``,
``calculate_zone_loads_ISO13790`` and ``sensible_balance_1C``.

Simplifications inherited from the migration plan: constant SHGC with a fixed
diffuse-incidence correction (instead of angular SHGC splines) and no urban
mutual shading.
"""

from __future__ import annotations

import numpy as np

from dt_prototype.dynamic.simulation.model_base import ThermalModel, register_model
from dt_prototype.dynamic.simulation.wall_params import iso13790_kappa

# ISO 13790 fixed coupling coefficients [W/(m2 K)]
_H_TR_MS = 9.1  # mass ↔ central surface node
_H_IS = 3.45  # central surface node ↔ air


@register_model
class Model5R1C(ThermalModel):
    """ISO 13790 five-resistances one-capacitance network."""

    name = "5R1C"
    aliases = ("1C",)
    n_sigma = 2

    # ------------------------------------------------------------------ #
    # Parameters (port of _ISO13790_params)
    # ------------------------------------------------------------------ #
    def _compute_parameters(self) -> None:
        """Aggregate surface data into the 5R1C network parameters."""
        Cm = DenAm = Atot = Htr_op = Htr_w = 0.0
        for s in self.zone.surfaces:
            k_int, k_est = iso13790_kappa(s.construction)
            # the retained reference uses the external-side capacity for IntFloor (the slab
            # mass is on the ceiling side), the internal side otherwise
            kappa = k_est if s.surface_type == "IntFloor" else k_int
            Cm += s.opaque_area * kappa
            DenAm += s.opaque_area * kappa**2
            Atot += s.gross_area
            if s.is_external:
                Htr_op += s.opaque_area * s.construction.u_value
                if s.glazed_area > 0.0 and s.window is not None:
                    Htr_w += s.glazed_area * s.window.u_value

        self.Cm = Cm  # [J/K]
        self.Am = Cm**2 / DenAm  # [m2] effective mass area
        self.Atot = Atot
        self.Htr_op = Htr_op
        self.Htr_w = Htr_w
        self.Htr_ms = self.Am * _H_TR_MS
        self.Htr_em = 1.0 / (1.0 / Htr_op - 1.0 / self.Htr_ms)
        self.Htr_is = _H_IS * Atot
        self.UA_tot = Htr_op + Htr_w

    # ------------------------------------------------------------------ #
    # Loads (port of calculate_zone_loads_ISO13790)
    # ------------------------------------------------------------------ #
    def _compute_loads(self) -> None:
        """Distribute internal and solar gains onto the ia/st/m nodes."""
        zone = self.zone
        n = self.weather.n_steps
        dt_sky = self.weather.average_dt_air_sky

        phi_sol = np.zeros(n)
        for s in zone.surfaces:
            if s.surface_type not in ("ExtWall", "Roof"):
                continue
            direct = s.poa_direct
            diffuse = s.poa_global - s.poa_direct
            # glazed gain: constant SHGC, diffuse correction factor
            if s.glazed_area > 0.0 and s.window is not None:
                w = s.window
                eff_area = (1.0 - w.frame_factor) * s.glazed_area * w.shading_coef
                phi_sol += w.shgc * eff_area * (direct + zone.shgc_diffuse_factor * diffuse)
            # opaque gain: absorbed solar minus long-wave extra flow (ISO 13790)
            c = s.construction
            r_se = c.r_se
            u_net = c.u_value_net
            phi_sol += (
                s.poa_global * c.solar_absorptance * r_se * u_net * s.opaque_area
                - s.sky_view_factor * r_se * u_net * s.opaque_area * zone.h_r_ext * dt_sky
            )

        self.phi_sol = phi_sol  # kept for the quasi-steady-state method
        gains_rad_tot = zone.gains_radiative + phi_sol
        self.phi_ia = zone.gains_convective
        self.phi_st = (
            1.0 - self.Am / self.Atot - self.Htr_w / (_H_TR_MS * self.Atot)
        ) * gains_rad_tot
        self.phi_m = self.Am / self.Atot * gains_rad_tot

    # ------------------------------------------------------------------ #
    # Balance (port of sensible_balance_1C)
    # ------------------------------------------------------------------ #
    def sensible_balance(
        self,
        flag: str,
        t: int,
        hve: tuple[float, float],
        sigma: tuple[float, ...],
        t_set: float = 20.0,
        phi_hc_set: float = 0.0,
    ) -> tuple[float, float, float, float, np.ndarray]:
        """Solve the 3-node linear system of ISO 13790 for time step ``t``.

        See :meth:`ThermalModel.sensible_balance`. ``sigma`` is
        ``(radiative_fraction, convective_fraction)``.
        """
        phi_ia, phi_st, phi_m = self.phi_ia[t], self.phi_st[t], self.phi_m[t]
        hve_vent, hve_inf = hve
        t_ext = float(self._t_ext[t])
        t_sup = self._t_sup  # ventilation supply (AHU output or outdoor air)
        tau = self.tau
        c_air = self.zone.air_thermal_capacity
        rad, conv = sigma[0], sigma[1]

        Y = np.zeros((3, 3))
        q = np.zeros(3)
        if flag == "Tset":
            Y[0, 0] = conv
            Y[0, 1] = self.Htr_is
            Y[1, 0] = rad
            Y[1, 1] = -(self.Htr_is + self.Htr_w + self.Htr_ms)
            Y[1, 2] = self.Htr_ms
            Y[2, 1] = self.Htr_ms
            Y[2, 2] = -self.Cm / tau - self.Htr_em - self.Htr_ms

            q[0] = (
                hve_inf * (t_set - t_ext)
                + hve_vent * (t_set - t_sup)
                - phi_ia
                + self.Htr_is * t_set
                + c_air * (t_set - self.Ta0) / tau
            )
            q[1] = -self.Htr_is * t_set - phi_st - self.Htr_w * t_ext
            q[2] = -self.Htr_em * t_ext - phi_m - self.Cm * self.Tm0[0] / tau
            x = np.linalg.solve(Y, q)
            phi_hc, t_air, t_s, t_m = float(x[0]), t_set, float(x[1]), float(x[2])
        elif flag == "phiset":
            Y[0, 0] = -(self.Htr_is + hve_inf + hve_vent) - c_air / tau
            Y[0, 1] = self.Htr_is
            Y[1, 0] = self.Htr_is
            Y[1, 1] = -(self.Htr_is + self.Htr_w + self.Htr_ms)
            Y[1, 2] = self.Htr_ms
            Y[2, 1] = self.Htr_ms
            Y[2, 2] = -self.Cm / tau - self.Htr_em - self.Htr_ms

            q[0] = -phi_hc_set * conv - hve_inf * t_ext - hve_vent * t_sup - phi_ia - c_air * self.Ta0 / tau
            q[1] = -phi_hc_set * rad - phi_st - self.Htr_w * t_ext
            q[2] = -self.Htr_em * t_ext - phi_m - self.Cm * self.Tm0[0] / tau
            x = np.linalg.solve(Y, q)
            phi_hc, t_air, t_s, t_m = phi_hc_set, float(x[0]), float(x[1]), float(x[2])
        else:
            raise ValueError(f"sensible_balance: flag must be 'Tset' or 'phiset', got {flag}")

        t_op = (t_air + t_s) / 2.0
        return phi_hc, t_air, t_op, t_s, np.array([t_m, t_m])
