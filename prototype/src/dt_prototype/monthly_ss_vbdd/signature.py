"""Fixed-factor physics signature coefficients (paper model type 1)."""
from .model import MonthlyInput, VBOptions


def physics_coefficients(row: MonthlyInput, solar_e0_W: float,
                         solar_e1_W_K: float, options: VBOptions) -> dict:
    """Return kW intercepts, kW/K slopes and finite balance points.

    Schedules, internal gains and offsets are held fixed at the supplied month.
    Monthly adaptive utilisation does not define constant regression parameters.
    """
    if options.utilisation != 'fixed':
        raise ValueError('Constant signature coefficients require fixed utilisation')
    hh = row.H_heating_W_K*(1-options.attenuation_heating)
    hc = row.H_cooling_W_K*(1-options.attenuation_cooling)
    oh = row.heating_offset_W*(1-options.attenuation_heating)
    oc = row.cooling_offset_W*(1-options.attenuation_cooling)
    eh,ec=options.eta_heating,options.eta_cooling
    a0=(hh*row.heating_setpoint_C+oh-eh*(solar_e0_W+row.internal_gain_W))/1000
    a1=-(hh+eh*solar_e1_W_K)/1000
    c0=(solar_e0_W+row.internal_gain_W-ec*(hc*row.cooling_setpoint_C+oc))/1000
    c1=(solar_e1_W_K+ec*hc)/1000
    return dict(heating_intercept_kW=a0,heating_slope_kW_K=a1,
                cooling_intercept_kW=c0,cooling_slope_kW_K=c1,
                heating_breakpoint_C=-a0/a1 if a1 else None,
                cooling_breakpoint_C=-c0/c1 if c1 else None,
                conventional_slope_signs=a1<0 and c1>0)
