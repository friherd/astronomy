#!/usr/bin/env python3
"""Show the current date and time in France (Europe/Paris), nicely formatted."""

import math
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

# France (Nice, Paris, etc.) all share the Europe/Paris timezone.
PARIS = ZoneInfo("Europe/Paris")

# Nice, France.
LATITUDE = 43.680762
LONGITUDE = 7.21231

# Observation window: a body counts as "in window" when its azimuth and
# elevation both fall inside these (inclusive) ranges, in degrees.
AZIMUTH_WINDOW = (200.0, 270.0)
ELEVATION_WINDOW = (0.0, 16.0)

# How far ahead to look for the next window pass, and the coarse scan step.
WINDOW_HORIZON = timedelta(days=7)
WINDOW_STEP = timedelta(minutes=3)

# French names so the output reads naturally.
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def solar_position(when: datetime, lat: float, lon: float) -> tuple[float, float]:
    """Sun's azimuth and elevation (degrees) for a time and location.

    Uses the NOAA solar position algorithm. Azimuth is measured clockwise
    from true north; elevation is above the horizon (negative = below).
    """
    # Work in UTC for the astronomical math.
    utc = when.astimezone(timezone.utc)

    # Julian day (with fractional time of day).
    y, m = utc.year, utc.month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    day_frac = (utc.hour + utc.minute / 60 + utc.second / 3600) / 24
    jd = (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
          + utc.day + b - 1524.5 + day_frac)

    # Julian century since J2000.0.
    t = (jd - 2451545.0) / 36525.0

    # Sun's geometric mean longitude and anomaly (degrees).
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m_anom = 357.52911 + t * (35999.05029 - 0.0001537 * t)

    # Equation of center -> true longitude -> apparent longitude.
    m_rad = math.radians(m_anom)
    c = (math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * m_rad) * (0.019993 - 0.000101 * t)
         + math.sin(3 * m_rad) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    # Obliquity of the ecliptic (with correction).
    seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    eps0 = 23 + (26 + seconds / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))

    # Sun's declination.
    decl = math.degrees(math.asin(
        math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))

    # Equation of time (minutes).
    var_y = math.tan(math.radians(eps / 2)) ** 2
    l0_rad = math.radians(l0)
    eot = 4 * math.degrees(
        var_y * math.sin(2 * l0_rad)
        - 2 * 0.016708634 * math.sin(m_rad)
        + 4 * 0.016708634 * var_y * math.sin(m_rad) * math.cos(2 * l0_rad)
        - 0.5 * var_y * var_y * math.sin(4 * l0_rad)
        - 1.25 * 0.016708634 ** 2 * math.sin(2 * m_rad))

    # True solar time (minutes) and hour angle (degrees).
    minutes = utc.hour * 60 + utc.minute + utc.second / 60
    true_solar = (minutes + eot + 4 * lon) % 1440
    hour_angle = true_solar / 4 - 180
    if hour_angle < -180:
        hour_angle += 360

    # Solar zenith / elevation.
    lat_rad = math.radians(lat)
    decl_rad = math.radians(decl)
    ha_rad = math.radians(hour_angle)
    cos_zenith = (math.sin(lat_rad) * math.sin(decl_rad)
                  + math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad))
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.degrees(math.acos(cos_zenith))
    elevation = 90 - zenith

    # Solar azimuth (clockwise from north).
    if abs(math.sin(math.radians(zenith))) < 1e-9:
        azimuth = 0.0
    else:
        cos_az = ((math.sin(lat_rad) * math.cos(math.radians(zenith)) - math.sin(decl_rad))
                  / (math.cos(lat_rad) * math.sin(math.radians(zenith))))
        cos_az = max(-1.0, min(1.0, cos_az))
        azimuth = math.degrees(math.acos(cos_az))
        # NOAA convention: afternoon (HA > 0) sun is in the west.
        azimuth = (azimuth + 180) % 360 if hour_angle > 0 else (540 - azimuth) % 360

    return azimuth, elevation


def _rev(x: float) -> float:
    """Normalize an angle in degrees to [0, 360)."""
    return x % 360.0


def moon_position(when: datetime, lat: float, lon: float) -> tuple[float, float]:
    """Moon's azimuth and elevation (degrees) for a time and location.

    Uses Paul Schlyter's lunar theory with the main perturbation terms,
    plus a topocentric parallax correction (the Moon is close enough that
    its position shifts ~1° depending on where on Earth you stand).
    Azimuth is clockwise from true north; elevation is above the horizon.
    """
    utc = when.astimezone(timezone.utc)
    ut = utc.hour + utc.minute / 60 + utc.second / 3600

    # Day number from Schlyter's epoch (2000-01-00 = 1999-12-31 0:00 UT).
    d = (367 * utc.year - (7 * (utc.year + ((utc.month + 9) // 12))) // 4
         + (275 * utc.month) // 9 + utc.day - 730530 + ut / 24)

    ecl = math.radians(23.4393 - 3.563e-7 * d)

    # Moon's orbital elements (degrees / Earth radii).
    n_node = _rev(125.1228 - 0.0529538083 * d)
    incl = 5.1454
    arg_p = _rev(318.0634 + 0.1643573223 * d)
    a = 60.2666
    e = 0.054900
    m_anom = _rev(115.3654 + 13.0649929509 * d)

    # Sun's elements, needed for the perturbations.
    ms = _rev(356.0470 + 0.9856002585 * d)
    ws = _rev(282.9404 + 4.70935e-5 * d)
    ls = _rev(ms + ws)

    # Eccentric anomaly (iterate from a first approximation), degrees.
    e_anom = m_anom + math.degrees(e) * math.sin(math.radians(m_anom)) * (
        1 + e * math.cos(math.radians(m_anom)))
    for _ in range(10):
        er = math.radians(e_anom)
        delta = (e_anom - math.degrees(e) * math.sin(er) - m_anom) / (1 - e * math.cos(er))
        e_anom -= delta
        if abs(delta) < 1e-6:
            break
    er = math.radians(e_anom)

    # Position in the orbital plane, then true anomaly and distance.
    xv = a * (math.cos(er) - e)
    yv = a * math.sqrt(1 - e * e) * math.sin(er)
    r = math.hypot(xv, yv)
    v = _rev(math.degrees(math.atan2(yv, xv)))

    # Ecliptic longitude / latitude before perturbations.
    vw = math.radians(v + arg_p)
    nr, ir = math.radians(n_node), math.radians(incl)
    xe = r * (math.cos(nr) * math.cos(vw) - math.sin(nr) * math.sin(vw) * math.cos(ir))
    ye = r * (math.sin(nr) * math.cos(vw) + math.cos(nr) * math.sin(vw) * math.cos(ir))
    ze = r * math.sin(vw) * math.sin(ir)
    lon_ecl = _rev(math.degrees(math.atan2(ye, xe)))
    lat_ecl = math.degrees(math.atan2(ze, math.hypot(xe, ye)))

    # Perturbation arguments.
    lm = _rev(n_node + arg_p + m_anom)  # Moon's mean longitude
    elong = _rev(lm - ls)               # mean elongation
    f = _rev(lm - n_node)               # argument of latitude
    rad = math.radians

    lon_ecl += (-1.274 * math.sin(rad(m_anom - 2 * elong))
                + 0.658 * math.sin(rad(2 * elong))
                - 0.186 * math.sin(rad(ms))
                - 0.059 * math.sin(rad(2 * m_anom - 2 * elong))
                - 0.057 * math.sin(rad(m_anom - 2 * elong + ms))
                + 0.053 * math.sin(rad(m_anom + 2 * elong))
                + 0.046 * math.sin(rad(2 * elong - ms))
                + 0.041 * math.sin(rad(m_anom - ms))
                - 0.035 * math.sin(rad(elong))
                - 0.031 * math.sin(rad(m_anom + ms))
                - 0.015 * math.sin(rad(2 * f - 2 * elong))
                + 0.011 * math.sin(rad(m_anom - 4 * elong)))
    lat_ecl += (-0.173 * math.sin(rad(f - 2 * elong))
                - 0.055 * math.sin(rad(m_anom - f - 2 * elong))
                - 0.046 * math.sin(rad(m_anom + f - 2 * elong))
                + 0.033 * math.sin(rad(f + 2 * elong))
                + 0.017 * math.sin(rad(2 * m_anom + f)))
    r += (-0.58 * math.cos(rad(m_anom - 2 * elong))
          - 0.46 * math.cos(rad(2 * elong)))

    # Perturbed ecliptic -> equatorial rectangular coordinates.
    lonr, latr = math.radians(lon_ecl), math.radians(lat_ecl)
    xg = r * math.cos(lonr) * math.cos(latr)
    yg = r * math.sin(lonr) * math.cos(latr)
    zg = r * math.sin(latr)
    xeq = xg
    yeq = yg * math.cos(ecl) - zg * math.sin(ecl)
    zeq = yg * math.sin(ecl) + zg * math.cos(ecl)

    ra = _rev(math.degrees(math.atan2(yeq, xeq)))
    dec = math.degrees(math.atan2(zeq, math.hypot(xeq, yeq)))

    # Hour angle from local sidereal time, then horizontal coordinates.
    gmst0 = _rev(ls + 180)
    lst = _rev(gmst0 + ut * 15 + lon)
    ha = _rev(lst - ra)
    if ha > 180:
        ha -= 360

    har, decr, latr2 = math.radians(ha), math.radians(dec), math.radians(lat)
    xc = math.cos(har) * math.cos(decr)
    yc = math.sin(har) * math.cos(decr)
    zc = math.sin(decr)
    xhor = xc * math.sin(latr2) - zc * math.cos(latr2)
    yhor = yc
    zhor = xc * math.cos(latr2) + zc * math.sin(latr2)

    azimuth = _rev(math.degrees(math.atan2(yhor, xhor)) + 180)
    altitude = math.degrees(math.asin(zhor))

    # Topocentric correction: shift from Earth's center to the surface.
    parallax = math.degrees(math.asin(1 / r))
    altitude -= parallax * math.cos(math.radians(altitude))

    return azimuth, altitude


def _kepler(m_deg: float, e: float) -> float:
    """Solve Kepler's equation; return the eccentric anomaly in degrees."""
    m = math.radians(m_deg)
    ea = m_deg + math.degrees(e) * math.sin(m) * (1 + e * math.cos(m))
    for _ in range(12):
        er = math.radians(ea)
        delta = (ea - math.degrees(e) * math.sin(er) - m_deg) / (1 - e * math.cos(er))
        ea -= delta
        if abs(delta) < 1e-7:
            break
    return ea


def _heliocentric(n_node, incl, arg_p, a, e, m_anom):
    """Heliocentric ecliptic longitude, latitude (deg) and distance (AU)."""
    er = math.radians(_kepler(m_anom, e))
    xv = a * (math.cos(er) - e)
    yv = a * math.sqrt(1 - e * e) * math.sin(er)
    r = math.hypot(xv, yv)
    v = math.degrees(math.atan2(yv, xv))
    vw = math.radians(v + arg_p)
    nr, ir = math.radians(n_node), math.radians(incl)
    xh = r * (math.cos(nr) * math.cos(vw) - math.sin(nr) * math.sin(vw) * math.cos(ir))
    yh = r * (math.sin(nr) * math.cos(vw) + math.cos(nr) * math.sin(vw) * math.cos(ir))
    zh = r * math.sin(vw) * math.sin(ir)
    lon = _rev(math.degrees(math.atan2(yh, xh)))
    lat = math.degrees(math.atan2(zh, math.hypot(xh, yh)))
    return lon, lat, r


def _sun_rect(d: float) -> "tuple[float, float]":
    """Sun's geocentric rectangular ecliptic coordinates (AU)."""
    w = 282.9404 + 4.70935e-5 * d
    e = 0.016709 - 1.151e-9 * d
    m = _rev(356.0470 + 0.9856002585 * d)
    er = math.radians(_kepler(m, e))
    xv = math.cos(er) - e
    yv = math.sqrt(1 - e * e) * math.sin(er)
    r = math.hypot(xv, yv)
    lonsun = math.radians(_rev(math.degrees(math.atan2(yv, xv)) + w))
    return r * math.cos(lonsun), r * math.sin(lonsun)


def _local_sidereal(d: float, ut: float, lon: float) -> float:
    """Local sidereal time in degrees."""
    ls = _rev((356.0470 + 0.9856002585 * d) + (282.9404 + 4.70935e-5 * d))
    return _rev(_rev(ls + 180) + ut * 15 + lon)


def _to_horizontal(ra: float, dec: float, lst: float, lat: float):
    """Equatorial (RA/Dec) to horizontal (azimuth, elevation) in degrees."""
    ha = _rev(lst - ra)
    if ha > 180:
        ha -= 360
    har, decr, latr = math.radians(ha), math.radians(dec), math.radians(lat)
    xc = math.cos(har) * math.cos(decr)
    yc = math.sin(har) * math.cos(decr)
    zc = math.sin(decr)
    xhor = xc * math.sin(latr) - zc * math.cos(latr)
    yhor = yc
    zhor = xc * math.cos(latr) + zc * math.sin(latr)
    az = _rev(math.degrees(math.atan2(yhor, xhor)) + 180)
    alt = math.degrees(math.asin(zhor))
    return az, alt


# Orbital elements as functions of day number d (Schlyter).
PLANET_ELEMENTS = {
    "Mercury": lambda d: (_rev(48.3313 + 3.24587e-5 * d), 7.0047 + 5.00e-8 * d,
                          _rev(29.1241 + 1.01444e-5 * d), 0.387098,
                          0.205635 + 5.59e-10 * d, _rev(168.6562 + 4.0923344368 * d)),
    "Venus": lambda d: (_rev(76.6799 + 2.46590e-5 * d), 3.3946 + 2.75e-8 * d,
                        _rev(54.8910 + 1.38374e-5 * d), 0.723330,
                        0.006773 - 1.302e-9 * d, _rev(48.0052 + 1.6021302244 * d)),
    "Mars": lambda d: (_rev(49.5574 + 2.11081e-5 * d), 1.8497 - 1.78e-8 * d,
                       _rev(286.5016 + 2.92961e-5 * d), 1.523688,
                       0.093405 + 2.516e-9 * d, _rev(18.6021 + 0.5240207766 * d)),
    "Jupiter": lambda d: (_rev(100.4542 + 2.76854e-5 * d), 1.3030 - 1.557e-7 * d,
                          _rev(273.8777 + 1.64505e-5 * d), 5.20256,
                          0.048498 + 4.469e-9 * d, _rev(19.8950 + 0.0830853001 * d)),
    "Saturn": lambda d: (_rev(113.6634 + 2.38980e-5 * d), 2.4886 - 1.081e-7 * d,
                         _rev(339.3939 + 2.97661e-5 * d), 9.55475,
                         0.055546 - 9.499e-9 * d, _rev(316.9670 + 0.0334442282 * d)),
}


def planet_position(when: datetime, lat: float, lon: float, planet: str):
    """Azimuth and elevation (degrees) of a planet for a time and location.

    Uses Schlyter's heliocentric elements, converts to geocentric via the
    Sun's position, then to topocentric horizontal coordinates. Includes the
    main Jupiter/Saturn mutual perturbations. Planets are far enough that
    diurnal parallax is negligible, so no topocentric distance correction.
    """
    utc = when.astimezone(timezone.utc)
    ut = utc.hour + utc.minute / 60 + utc.second / 3600
    d = (367 * utc.year - (7 * (utc.year + ((utc.month + 9) // 12))) // 4
         + (275 * utc.month) // 9 + utc.day - 730530 + ut / 24)
    ecl = math.radians(23.4393 - 3.563e-7 * d)

    plon, plat, r = _heliocentric(*PLANET_ELEMENTS[planet](d))

    # Mutual perturbations from the two giant planets (degrees).
    if planet in ("Jupiter", "Saturn"):
        mj = _rev(19.8950 + 0.0830853001 * d)
        ms = _rev(316.9670 + 0.0334442282 * d)
        rad = math.radians
        if planet == "Jupiter":
            plon += (-0.332 * math.sin(rad(2 * mj - 5 * ms - 67.6))
                     - 0.056 * math.sin(rad(2 * mj - 2 * ms + 21))
                     + 0.042 * math.sin(rad(3 * mj - 5 * ms + 21))
                     - 0.036 * math.sin(rad(mj - 2 * ms))
                     + 0.022 * math.cos(rad(mj - ms))
                     + 0.023 * math.sin(rad(2 * mj - 3 * ms + 52))
                     - 0.016 * math.sin(rad(mj - 5 * ms - 69)))
        else:  # Saturn
            plon += (+0.812 * math.sin(rad(2 * mj - 5 * ms - 67.6))
                     - 0.229 * math.cos(rad(2 * mj - 4 * ms - 2))
                     + 0.119 * math.sin(rad(mj - 2 * ms - 3))
                     + 0.046 * math.sin(rad(2 * mj - 6 * ms - 69))
                     + 0.014 * math.sin(rad(mj - 3 * ms + 32)))
            plat += (-0.020 * math.cos(rad(2 * mj - 4 * ms - 2))
                     + 0.018 * math.sin(rad(2 * mj - 6 * ms - 49)))

    # Heliocentric -> geocentric (add the Sun's position) -> equatorial.
    lonr, latr = math.radians(plon), math.radians(plat)
    xh = r * math.cos(lonr) * math.cos(latr)
    yh = r * math.sin(lonr) * math.cos(latr)
    zh = r * math.sin(latr)
    xs, ys = _sun_rect(d)
    xg, yg, zg = xh + xs, yh + ys, zh
    xeq = xg
    yeq = yg * math.cos(ecl) - zg * math.sin(ecl)
    zeq = yg * math.sin(ecl) + zg * math.cos(ecl)

    ra = _rev(math.degrees(math.atan2(yeq, xeq)))
    dec = math.degrees(math.atan2(zeq, math.hypot(xeq, yeq)))
    return _to_horizontal(ra, dec, _local_sidereal(d, ut, lon), lat)


def ang_sep(az1: float, el1: float, az2: float, el2: float) -> float:
    """Angular separation (degrees) between two points given in horizontal coords."""
    a1, a2 = math.radians(el1), math.radians(el2)
    daz = math.radians(az2 - az1)
    return math.degrees(math.acos(max(-1.0, min(1.0,
        math.sin(a1) * math.sin(a2) + math.cos(a1) * math.cos(a2) * math.cos(daz)
    ))))


def compass(azimuth: float) -> str:
    """Nearest 16-point compass direction for an azimuth in degrees."""
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[round(azimuth / 22.5) % 16]


PositionFn = Callable[[datetime, float, float], "tuple[float, float]"]


def rise_set(position_fn: PositionFn, reference: datetime, lat: float, lon: float,
             h0: float = -0.833) -> "tuple[Optional[datetime], Optional[datetime]]":
    """Find a body's rise and set times on the local day of ``reference``.

    Scans the body's elevation across the day in 10-minute steps, then
    refines each horizon crossing by bisection. ``h0`` is the elevation
    that counts as the horizon (-0.833° = standard refraction + disk).
    Returns (rise, set); either may be None if no such event occurs today.
    """
    midnight = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    end = midnight + timedelta(days=1)
    step = timedelta(minutes=10)

    rise: Optional[datetime] = None
    setting: Optional[datetime] = None

    t = midnight
    prev = position_fn(t, lat, lon)[1] - h0
    while t < end:
        t2 = t + step
        cur = position_fn(t2, lat, lon)[1] - h0
        if (prev < 0) != (cur < 0):  # horizon crossing in this interval
            lo, hi, lo_val = t, t2, prev
            while (hi - lo) > timedelta(seconds=1):
                mid = lo + (hi - lo) / 2
                mid_val = position_fn(mid, lat, lon)[1] - h0
                if (lo_val < 0) != (mid_val < 0):
                    hi = mid
                else:
                    lo, lo_val = mid, mid_val
            crossing = lo + (hi - lo) / 2
            if cur > prev and rise is None:        # going up = rise
                rise = crossing
            elif cur < prev and setting is None:   # going down = set
                setting = crossing
        t, prev = t2, cur

    return rise, setting


def fmt_time(dt: Optional[datetime]) -> str:
    """Local HH:MM, or an em dash when the event doesn't happen today."""
    return dt.strftime("%H:%M") if dt else "—"


def in_window(az: float, el: float) -> bool:
    """True when azimuth and elevation both fall inside the observation window."""
    az_lo, az_hi = AZIMUTH_WINDOW
    el_lo, el_hi = ELEVATION_WINDOW
    return az_lo <= az <= az_hi and el_lo <= el <= el_hi


def _in_window_at(fn: PositionFn, t: datetime, lat: float, lon: float) -> bool:
    az, el = fn(t, lat, lon)
    return in_window(az, el)


def _window_edge(fn: PositionFn, a: datetime, b: datetime, lat: float, lon: float) -> datetime:
    """Refine the in/out transition bracketed by times a and b to ~1 second."""
    inside_a = _in_window_at(fn, a, lat, lon)
    while (b - a).total_seconds() > 1:
        mid = a + (b - a) / 2
        if _in_window_at(fn, mid, lat, lon) == inside_a:
            a = mid
        else:
            b = mid
    return a + (b - a) / 2


def next_window_pass(fn: PositionFn, start: datetime, lat: float, lon: float):
    """Next interval the body spends inside the window, searching forward up to
    WINDOW_HORIZON. Returns (entry, exit); entry may precede ``start`` when the
    body is already inside. (None, None) if there is no pass within the horizon.
    """
    end = start + WINDOW_HORIZON

    if _in_window_at(fn, start, lat, lon):
        # Already inside: walk back (capped at a day) for the true entry.
        entry = start
        back_cap = start - timedelta(days=1)
        tb = start
        while tb > back_cap:
            tb_prev, tb = tb, tb - WINDOW_STEP
            if not _in_window_at(fn, tb, lat, lon):
                entry = _window_edge(fn, tb, tb_prev, lat, lon)
                break
        tf = start
        while tf < end:
            tf_prev, tf = tf, tf + WINDOW_STEP
            if not _in_window_at(fn, tf, lat, lon):
                return entry, _window_edge(fn, tf_prev, tf, lat, lon)
        return entry, None

    # Not inside: scan forward for the entry, then the following exit.
    t = start
    while t < end:
        t_prev, t = t, t + WINDOW_STEP
        if _in_window_at(fn, t, lat, lon):
            entry = _window_edge(fn, t_prev, t, lat, lon)
            t2 = entry
            while t2 < end:
                t2_prev, t2 = t2, t2 + WINDOW_STEP
                if not _in_window_at(fn, t2, lat, lon):
                    return entry, _window_edge(fn, t2_prev, t2, lat, lon)
            return entry, None
    return None, None


def fmt_pass(entry: Optional[datetime], exit_: Optional[datetime], now: datetime) -> str:
    """Human-readable next-pass description, e.g. '13:39 → 13:50  (11 min)'."""
    if entry is None:
        return "—  (none in 7 days)"

    def stamp(dt: datetime) -> str:
        local = dt.astimezone(PARIS)
        if local.date() == now.astimezone(PARIS).date():
            return local.strftime("%H:%M")
        return local.strftime("%a %d %H:%M")

    if exit_ is None:
        return f"{stamp(entry)} → (ongoing)"
    mins = round((exit_ - entry).total_seconds() / 60)
    return f"{stamp(entry)} → {stamp(exit_)}  ({mins} min)"


def main() -> None:
    now = datetime.now(PARIS)

    jour = JOURS[now.weekday()]
    mois = MOIS[now.month - 1]

    date_str = f"{jour.capitalize()} {now.day} {mois} {now.year}"
    heure_str = now.strftime("%H:%M:%S")
    tz_str = now.strftime("%Z (UTC%z)")

    # (name, position function, horizon altitude for rise/set).
    # Sun uses -0.833° (upper limb + refraction); planets/stars use plain
    # refraction (-0.566°); the Moon's center crossing is close to -0.833°.
    bodies = [
        ("Sun", solar_position, -0.833),
        ("Moon", moon_position, -0.833),
        ("Mercury", lambda t, la, lo: planet_position(t, la, lo, "Mercury"), -0.566),
        ("Venus", lambda t, la, lo: planet_position(t, la, lo, "Venus"), -0.566),
        ("Jupiter", lambda t, la, lo: planet_position(t, la, lo, "Jupiter"), -0.566),
        ("Saturn", lambda t, la, lo: planet_position(t, la, lo, "Saturn"), -0.566),
        ("Mars", lambda t, la, lo: planet_position(t, la, lo, "Mars"), -0.566),
    ]

    az_lo, az_hi = AZIMUTH_WINDOW
    el_lo, el_hi = ELEVATION_WINDOW
    window_str = f"az {az_lo:.0f}–{az_hi:.0f}°, el {el_lo:.0f}–{el_hi:.0f}°"

    print()
    print("  🇫🇷  France — Nice (Europe/Paris)")
    print("  " + "─" * 62)
    print(f"  📅  {date_str}")
    print(f"  🕐  {heure_str}    🌍  {tz_str}")
    print(f"  🪟  Window: {window_str}")
    print()
    sun_az, sun_el = solar_position(now, LATITUDE, LONGITUDE)
    print(f"  {'Body':<9}{'Azimuth':<13}{'Elevation':<13}"
          f"{'Elong':>7}{'Rise':>6}{'Set':>8}{'Window':>10}")
    print("  " + "─" * 69)
    for name, fn, h0 in bodies:
        az, el = fn(now, LATITUDE, LONGITUDE)
        rise, setting = rise_set(fn, now, LATITUDE, LONGITUDE, h0)
        az_field = f"{az:5.1f}° {compass(az)}"
        mark = "↑ up" if el > 0 else "↓ down"
        el_field = f"{el:5.1f}° {mark}"
        elong_field = "—" if name == "Sun" else f"{ang_sep(sun_az, sun_el, az, el):5.1f}°"
        window_field = "✓ IN" if in_window(az, el) else "·"
        print(f"  {name:<9}{az_field:<13}{el_field:<13}"
              f"{elong_field:>7}{fmt_time(rise):>6}{fmt_time(setting):>8}{window_field:>10}")
    print()

    print(f"  Next window pass (within {WINDOW_HORIZON.days} days):")
    for name, fn, _ in bodies:
        entry, exit_ = next_window_pass(fn, now, LATITUDE, LONGITUDE)
        print(f"    {name:<9}{fmt_pass(entry, exit_, now)}")
    print()


if __name__ == "__main__":
    main()
