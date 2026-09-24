"""7R2C thermal model (VDI 6007) — FR-10.

Faithful port of the retained reference's ``ThermalZone._VDI6007_params``,
``calculate_zone_loads_VDI6007`` and ``sensible_balance_2C``, including the
equivalent outdoor temperature (sol-air + long-wave) forcing and the
AW (external) / IW (internal) two-capacitance network.

Simplifications inherited from the migration plan: the window inward solar
gain is split with fixed radiative/convective fractions instead of separate
angular SHGC splines.
"""

from __future__ import annotations

import numpy as np

from dt_prototype.common.constants import (
    RADIATIVE_HEAT_TRANSFER_COEF,
    SURFACE_HEAT_TRANSFER_COEF,
)
from dt_prototype.dynamic.simulation.model_base import ThermalModel, register_model
from dt_prototype.dynamic.simulation.wall_params import (
    impedance_parallel,
    long_wave_radiation,
    tri2star,
    vdi6007_surface_params,
)

_ALPHA_KON_A = 20.0  # VDI 6007 external convective coefficient [W/(m2 K)]


@register_model
class Model7R2C(ThermalModel):
    """VDI 6007 seven-resistances two-capacitances network."""

    name = "7R2C"
    aliases = ("2C",)
    n_sigma = 3

    # ------------------------------------------------------------------ #
    # Parameters (port of _VDI6007_params)
    # ------------------------------------------------------------------ #
    def _compute_parameters(self) -> None:
        """Aggregate surface data into the 7R2C network parameters."""
        h_rad = RADIATIVE_HEAT_TRANSFER_COEF

        R1AW_v, C1AW_v = [], []
        R1IW_v, C1IW_v = [], []
        HAW, HAF = [], []
        alphaKonAW, alphaKonIW, alphaKonAF = [], [], []
        RalphaStrAW, RalphaStrIW, RalphaStrAF = [], [], []
        AreaAW, AreaAF, AreaIW = [], [], []
        self.Araum_tot = self.Aaw_tot = 0.0

        for s in self.zone.surfaces:
            c = s.construction
            conv_int = SURFACE_HEAT_TRANSFER_COEF[c.construction_type]["inside"] - h_rad
            self.Araum_tot += s.gross_area
            if s.is_external:
                self.Aaw_tot += s.gross_area
                r1, c1 = vdi6007_surface_params(c, s.opaque_area, asim=True)
                C1AW_v.append(c1)
                HAW.append(c.u_value * s.opaque_area)
                alphaKonAW.append(s.opaque_area * conv_int)
                RalphaStrAW.append(1.0 / (max(s.opaque_area, 1e-7) * h_rad))
                if s.glazed_area > 1e-5 and s.window is not None:
                    # window: massless resistance in parallel with the wall R1
                    r_w_net = max(1.0 / s.window.u_value - c.r_si - c.r_se, 1e-5)
                    r_af = r_w_net / s.glazed_area
                    HAF.append(s.window.u_value * s.glazed_area)
                    alphaKonAF.append(s.glazed_area * conv_int)
                    RalphaStrAF.append(1.0 / (s.glazed_area * h_rad))
                else:
                    r_af = 1e15
                    HAF.append(0.0)
                    alphaKonAF.append(0.0)
                    RalphaStrAF.append(1e15)
                # the retained reference "ALTERNATIVA NORMA": R1 wall in parallel with 6/R window
                R1AW_v.append(1.0 / (1.0 / r1 + 6.0 / r_af))
                AreaAW.append(s.opaque_area)
                AreaAF.append(s.glazed_area)
            else:
                r1, c1 = vdi6007_surface_params(c, s.opaque_area, asim=False)
                R1IW_v.append(r1)
                C1IW_v.append(c1)
                alphaKonIW.append(s.opaque_area * conv_int)
                RalphaStrIW.append(1.0 / (max(s.opaque_area, 1e-7) * h_rad))
                AreaIW.append(s.gross_area)

        # The VDI 6007 network separates external (AW) from internal (IW)
        # components and inverts the conductance of each group, so a zone with
        # no surfaces on either side has no valid parametrisation. Fail with an
        # actionable message instead of a bare ZeroDivisionError several lines
        # down (geometries built via preprocessing.geometry always carry an
        # IntWall, but hand-built ZoneGeometry objects may not).
        if not alphaKonIW:
            raise ValueError(
                f"7R2C: zone '{self.zone.name}' has no internal-mass surfaces "
                "(IntWall/IntCeiling/IntFloor); the VDI 6007 network needs at "
                "least one. Add an IntWall surface, or use the 5R1C model."
            )
        if not (alphaKonAW or alphaKonAF):
            raise ValueError(
                f"7R2C: zone '{self.zone.name}' has no external surfaces "
                "(ExtWall/Roof/GroundFloor); the VDI 6007 network needs at least one."
            )

        self.R1AW, self.C1AW = impedance_parallel(np.array(R1AW_v), np.array(C1AW_v))
        self.R1IW, self.C1IW = impedance_parallel(np.array(R1IW_v), np.array(C1IW_v))

        self.RgesAW = 1.0 / (sum(HAW) + sum(HAF))  # eq 27
        RalphaKonAW = 1.0 / (sum(alphaKonAW) + sum(alphaKonAF))
        RalphaKonIW = 1.0 / sum(alphaKonIW)
        if sum(AreaAW) <= sum(AreaIW):
            RalphaStrAWIW = 1.0 / (
                sum(1.0 / np.array(RalphaStrAW)) + sum(1.0 / np.array(RalphaStrAF))
            )  # eq 29
        else:
            RalphaStrAWIW = 1.0 / sum(1.0 / np.array(RalphaStrIW))  # eq 31

        self.RrestAW = self.RgesAW - self.R1AW - 1.0 / (1.0 / RalphaKonAW + 1.0 / RalphaStrAWIW)
        RalphaGesAW_A = 1.0 / (_ALPHA_KON_A * (sum(AreaAF) + sum(AreaAW)))
        if self.RgesAW < RalphaGesAW_A:  # eq 28a-c
            self.RrestAW = RalphaGesAW_A
            self.R1AW = self.RgesAW - self.RrestAW - 1.0 / (
                1.0 / RalphaKonAW + 1.0 / RalphaStrAWIW
            )
            if self.R1AW < 1e-10:
                self.R1AW = 1e-10

        self.RalphaStarIL, self.RalphaStarAW, self.RalphaStarIW = tri2star(
            RalphaStrAWIW, RalphaKonIW, RalphaKonAW
        )
        self.UA_tot = sum(HAW) + sum(HAF)
        self.Htr_op = sum(HAW)
        self.Htr_w = sum(HAF)

    # ------------------------------------------------------------------ #
    # Loads (port of calculate_zone_loads_VDI6007)
    # ------------------------------------------------------------------ #
    def _compute_loads(self) -> None:
        """Equivalent outdoor temperature and load split (conv / AW / IW)."""
        zone = self.zone
        t_ext = self._t_ext
        n = self.weather.n_steps
        h_rad = RADIATIVE_HEAT_TRANSFER_COEF

        e_atm, e_ground, theta_ground, theta_sky = long_wave_radiation(t_ext)
        with np.errstate(divide="ignore", invalid="ignore"):
            alpha_str_lw = np.where(
                theta_sky != theta_ground, (e_atm + e_ground) / (theta_sky - theta_ground), 5.0
            )

        theta_eq_tot = np.zeros(n)
        q_sol_str_iw = np.zeros(n)
        q_sol_str_aw = np.zeros(n)
        q_sol_kon = np.zeros(n)

        for s in zone.surfaces:
            c = s.construction
            if s.surface_type in ("ExtWall", "Roof"):
                conv_ext = SURFACE_HEAT_TRANSFER_COEF[c.construction_type]["outside"] - h_rad
                alpha_a = conv_ext + h_rad
                phi = s.sky_view_factor
                direct = s.poa_direct
                diffuse = s.poa_global - s.poa_direct
                # long-wave and short-wave equivalent temperature increments
                d_lw = (
                    ((theta_ground - t_ext) * (1.0 - phi) + (theta_sky - t_ext) * phi)
                    * alpha_str_lw
                    * 0.9
                    / (0.93 * alpha_a)
                )
                d_kw = (direct + diffuse) * c.solar_absorptance / alpha_a
                theta_eq_tot += (t_ext + d_lw + d_kw) * c.u_value * s.opaque_area / self.UA_tot
                if s.glazed_area > 1e-5 and s.window is not None:
                    w = s.window
                    theta_eq_tot += (t_ext + d_lw) * w.u_value * s.glazed_area / self.UA_tot
                    eff_area = (1.0 - w.frame_factor) * s.glazed_area * w.shading_coef
                    inward = w.shgc * eff_area * (direct + zone.shgc_diffuse_factor * diffuse)
                    rad_in = inward * zone.shgc_radiative
                    conv_in = inward * (1.0 - zone.shgc_radiative)
                    # distribution of the radiative part to IW / AW nodes
                    denom = self.Araum_tot - s.gross_area
                    q_sol_str_iw += rad_in * (self.Araum_tot - self.Aaw_tot) / denom
                    q_sol_str_aw += rad_in * (self.Aaw_tot - s.gross_area) / denom
                    q_sol_kon += conv_in
            elif s.surface_type == "GroundFloor":
                theta_eq_tot += t_ext * c.u_value * s.opaque_area / self.UA_tot

        self.theta_eq_tot = theta_eq_tot
        # internal gains: radiative split between IW and AW by area shares
        q_int_rad = zone.gains_radiative
        self.Q_il_kon = zone.gains_convective + q_sol_kon
        self.Q_il_str_iw = q_sol_str_iw + q_int_rad * (self.Araum_tot - self.Aaw_tot) / self.Araum_tot
        self.Q_il_str_aw = q_sol_str_aw + q_int_rad * self.Aaw_tot / self.Araum_tot

    # ------------------------------------------------------------------ #
    # Balance (port of sensible_balance_2C)
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
        """Solve the VDI 6007 linear system for time step ``t``.

        See :meth:`ThermalModel.sensible_balance`. ``sigma`` is
        ``(radiative_to_IW, radiative_to_AW, convective)``.
        """
        r_lue_ve = 1e20 if hve[0] == 0.0 else 1.0 / hve[0]
        r_lue_inf = 1e20 if hve[1] == 0.0 else 1.0 / hve[1]
        q_kon = self.Q_il_kon[t]
        q_str_aw = self.Q_il_str_aw[t]
        q_str_iw = self.Q_il_str_iw[t]
        tau = self.tau
        c_air = self.zone.air_thermal_capacity
        theta_a_eq = self.theta_eq_tot[t]
        theta_lue = float(self._t_ext[t])
        theta_sup = self._t_sup  # ventilation supply (AHU output or outdoor air)

        if flag == "Tset":
            theta_i = t_set
            Y = np.zeros((6, 6))
            Y[0, 0] = -1 / self.RrestAW - 1 / self.R1AW - self.C1AW / tau
            Y[0, 1] = 1 / self.R1AW
            Y[1, 0] = 1 / self.R1AW
            Y[1, 1] = -1 / self.R1AW - 1 / self.RalphaStarAW
            Y[1, 2] = 1 / self.RalphaStarAW
            Y[1, 3] = sigma[1]
            Y[2, 1] = 1 / self.RalphaStarAW
            Y[2, 2] = -1 / self.RalphaStarAW - 1 / self.RalphaStarIL - 1 / self.RalphaStarIW
            Y[2, 4] = 1 / self.RalphaStarIW
            Y[3, 2] = 1 / self.RalphaStarIL
            Y[3, 3] = sigma[2]
            Y[4, 2] = 1 / self.RalphaStarIW
            Y[4, 3] = sigma[0]
            Y[4, 4] = -1 / self.RalphaStarIW - 1 / self.R1IW
            Y[4, 5] = 1 / self.R1IW
            Y[5, 4] = 1 / self.R1IW
            Y[5, 5] = -1 / self.R1IW - self.C1IW / tau

            q = np.zeros(6)
            q[0] = -theta_a_eq / self.RrestAW - self.C1AW * self.Tm0[0] / tau
            q[1] = -q_str_aw
            q[2] = -theta_i / self.RalphaStarIL
            q[3] = (
                theta_i / self.RalphaStarIL
                - q_kon
                - (theta_lue - theta_i) / r_lue_inf
                - (theta_sup - theta_i) / r_lue_ve
                + c_air * (theta_i - self.Ta0) / tau
            )
            q[4] = -q_str_iw
            q[5] = -self.C1IW * self.Tm0[1] / tau
            x = np.linalg.solve(Y, q)
            tm_aw, ts_aw, _t_star, phi_hc, ts_iw, tm_iw = (
                float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5]),
            )
            t_air = t_set
        elif flag == "phiset":
            q_hk_iw = phi_hc_set * sigma[0]
            q_hk_aw = phi_hc_set * sigma[1]
            q_hk_kon = phi_hc_set * sigma[2]

            Y = np.zeros((6, 6))
            Y[0, 0] = -1 / self.RrestAW - 1 / self.R1AW - self.C1AW / tau
            Y[0, 1] = 1 / self.R1AW
            Y[1, 0] = 1 / self.R1AW
            Y[1, 1] = -1 / self.R1AW - 1 / self.RalphaStarAW
            Y[1, 2] = 1 / self.RalphaStarAW
            Y[2, 1] = 1 / self.RalphaStarAW
            Y[2, 2] = -1 / self.RalphaStarAW - 1 / self.RalphaStarIL - 1 / self.RalphaStarIW
            Y[2, 3] = 1 / self.RalphaStarIL
            Y[2, 4] = 1 / self.RalphaStarIW
            Y[3, 2] = 1 / self.RalphaStarIL
            Y[3, 3] = -1 / self.RalphaStarIL - 1 / r_lue_inf - 1 / r_lue_ve - c_air / tau
            Y[4, 2] = 1 / self.RalphaStarIW
            Y[4, 4] = -1 / self.RalphaStarIW - 1 / self.R1IW
            Y[4, 5] = 1 / self.R1IW
            Y[5, 4] = 1 / self.R1IW
            Y[5, 5] = -1 / self.R1IW - self.C1IW / tau

            q = np.zeros(6)
            q[0] = -theta_a_eq / self.RrestAW - self.C1AW * self.Tm0[0] / tau
            q[1] = -q_hk_aw - q_str_aw
            q[2] = 0.0
            q[3] = (
                -q_hk_kon
                - q_kon
                - theta_lue / r_lue_inf
                - theta_sup / r_lue_ve
                - c_air * self.Ta0 / tau
            )
            q[4] = -q_hk_iw - q_str_iw
            q[5] = -self.C1IW * self.Tm0[1] / tau
            x = np.linalg.solve(Y, q)
            tm_aw, ts_aw, _t_star, t_air, ts_iw, tm_iw = (
                float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5]),
            )
            phi_hc = phi_hc_set
        else:
            raise ValueError(f"sensible_balance: flag must be 'Tset' or 'phiset', got {flag}")

        aw_share = self.Aaw_tot / self.Araum_tot
        t_mr = ts_aw * aw_share + ts_iw * (1.0 - aw_share)
        t_op = (t_mr + t_air) / 2.0
        return phi_hc, t_air, t_op, t_mr, np.array([tm_aw, tm_iw])
