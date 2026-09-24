"""Small shared guards for the supported annual input contract."""
import calendar
from numbers import Integral


def validate_calendar(year):
    if isinstance(year, bool) or not isinstance(year, Integral) or not 1 <= year <= 9998:
        raise ValueError("calendar_year must be an integer between 1 and 9998")
    if calendar.isleap(year):
        raise ValueError("calendar_year must be non-leap: only 8760-hour years are supported")


def validate_resolution(time_steps_per_hour, azimuth_subdivisions=None):
    # Weather and schedules currently use whole-minute intervals.
    if (isinstance(time_steps_per_hour, bool)
            or not isinstance(time_steps_per_hour, Integral)
            or time_steps_per_hour < 1 or 60 % time_steps_per_hour):
        raise ValueError("time_steps_per_hour must be a positive integer divisor of 60")
    if azimuth_subdivisions is not None and (
            isinstance(azimuth_subdivisions, bool)
            or not isinstance(azimuth_subdivisions, Integral)
            or not 1 <= azimuth_subdivisions <= 360):
        raise ValueError("azimuth_subdivisions must be an integer between 1 and 360")
