"""Coordinates for the shared map (B-92; research note 02 sections C1, C2, E1, E2): MOON_ME planetocentric latitude /
east longitude / height on the 1,737.4 km sphere <-> Cartesian <-> local east-north-up at the base datum; the LOLA
south polar stereographic grid (the frame lunarsim/terrain.py reads) <-> latitude / longitude; and the PA-versus-ME
frame mix-up.

Datum O (note 02 C2): the BASE site of the Connecting Ridge pack, grid X = x + origin_x, Y = y + origin_y
(data/terrain/connecting_ridge/meta.json: origin (-19,000, -20,000) m), height from the terrain (sphere-relative).
Heights stay relative to the sphere, never to a tangent plane (a plane drops below it by d^2 / 2R: 0.29 m at 1 km).

PA versus ME: MOON_ME (DE421 mean-Earth / polar axis) and MOON_PA (principal axes) differ by a constant rotation; the
NAIF frame kernel gives it as three angles, 67.8526", 78.6944", 0.2785" about axes 3, 2, 1 [NAIF-FK], composed as
SPICE composes TK frames (frame rotations). Note 02 E1: |delta| = 662.86 m at the south pole, 659.22 m at the tile
centre (89.4632 S, 222.5104 E), 875.23 m at latitude 0, longitude 0 (SPICE pxform, checked in note 02).
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np

R_MOON = 1737400.0                           # note 02 D "Reference sphere radius" [LROWP08]
ORIGIN_XY = (-19000.0, -20000.0)             # data/terrain/connecting_ridge/meta.json origin_xy_m
ARCSEC = math.pi / (180.0 * 3600.0)
PA_ME_ANGLES_ARCSEC = (67.8526, 78.6944, 0.2785)   # [NAIF-FK] moon_de440_250416.tf TKFRAME_31009_ANGLES, axes (3, 2, 1)
                                             # (note 02 E1's 0.2914" is the x component of the composed rotation
                                             # vector, not the kernel's third angle; corrected 11 Nov, B-99)
PA_ME_AXES = (3, 2, 1)


def latlon_to_cart(lat_deg, lon_deg, h_m=0.0, R: float = R_MOON) -> np.ndarray:
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    r = R + np.asarray(h_m, float)
    return np.stack([r * np.cos(lat) * np.cos(lon), r * np.cos(lat) * np.sin(lon), r * np.sin(lat)], axis=-1)


def cart_to_latlon(xyz, R: float = R_MOON) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    xyz = np.asarray(xyz, float)
    x, y, z = xyz[..., 0], xyz[..., 1], xyz[..., 2]
    r = np.sqrt(x * x + y * y + z * z)
    lat = np.degrees(np.arcsin(z / r))
    lon = np.degrees(np.arctan2(y, x)) % 360.0
    return lat, lon, r - R


def enu_basis(lat0_deg: float, lon0_deg: float) -> np.ndarray:
    """Q with rows e, n, u at (lat0, lon0) (note 02 E1); orthonormal."""
    p, l = math.radians(lat0_deg), math.radians(lon0_deg)
    e = [-math.sin(l), math.cos(l), 0.0]
    n = [-math.sin(p) * math.cos(l), -math.sin(p) * math.sin(l), math.cos(p)]
    u = [math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p)]
    return np.array([e, n, u])


class Datum:
    """A site datum O: MOON_ME (lat0, lon0, h0) and its local east-north-up frame."""

    def __init__(self, lat0_deg: float, lon0_deg: float, h0_m: float = 0.0, name: str = "SITE-connecting_ridge-v1"):
        self.lat0, self.lon0, self.h0, self.name = float(lat0_deg), float(lon0_deg), float(h0_m), name
        self.Q = enu_basis(lat0_deg, lon0_deg)
        self.r0 = latlon_to_cart(lat0_deg, lon0_deg, h0_m)

    def me_to_enu(self, lat_deg, lon_deg, h_m=0.0) -> np.ndarray:
        return (latlon_to_cart(lat_deg, lon_deg, h_m) - self.r0) @ self.Q.T

    def enu_to_me(self, enu) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        return cart_to_latlon(self.r0 + np.asarray(enu, float) @ self.Q)


# ------------------------------------------------------------------------------------------------ polar stereographic
def grid_to_latlon(X, Y, R: float = R_MOON) -> Tuple[np.ndarray, np.ndarray]:
    """LOLA south polar stereographic (k0 = 1, +Y along longitude 0): X = rho sin(lon), Y = rho cos(lon),
    rho = 2 R tan(c / 2), c the angle from the south pole (note 02 E1, E2)."""
    X, Y = np.asarray(X, float), np.asarray(Y, float)
    rho = np.hypot(X, Y)
    c = 2.0 * np.arctan(rho / (2.0 * R))
    return np.degrees(c) - 90.0, np.degrees(np.arctan2(X, Y)) % 360.0


def latlon_to_grid(lat_deg, lon_deg, R: float = R_MOON) -> Tuple[np.ndarray, np.ndarray]:
    c = np.radians(np.asarray(lat_deg, float) + 90.0)
    rho = 2.0 * R * np.tan(c / 2.0)
    lon = np.radians(lon_deg)
    return rho * np.sin(lon), rho * np.cos(lon)


def grid_scale(X, Y, R: float = R_MOON):
    """Point scale k = sec^2(c / 2) of the stereographic map (note 02 E2)."""
    rho = np.hypot(np.asarray(X, float), np.asarray(Y, float))
    return 1.0 + (rho / (2.0 * R)) ** 2


def site_to_latlon(x, y):
    """Local terrain frame (x, y metres) -> (lat, lon)."""
    return grid_to_latlon(np.asarray(x, float) + ORIGIN_XY[0], np.asarray(y, float) + ORIGIN_XY[1])


# ------------------------------------------------------------------------------------------------ PA versus ME
def _frame_rot(axis: int, a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    if axis == 1:
        return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    if axis == 2:
        return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def me_to_pa_matrix() -> np.ndarray:
    """Matrix taking MOON_ME vectors to MOON_PA (TK frame angles composed as [a1]_3 [a2]_2 [a3]_1; [NAIF-FK])."""
    a = [x * ARCSEC for x in PA_ME_ANGLES_ARCSEC]
    M = _frame_rot(PA_ME_AXES[0], a[0]) @ _frame_rot(PA_ME_AXES[1], a[1]) @ _frame_rot(PA_ME_AXES[2], a[2])
    return M.T          # the TK matrix maps the TK frame (ME) to its relative frame (PA) as its transpose here


def frame_mixup_shift(lat_deg: float, lon_deg: float, h_m: float = 0.0, datum: "Datum" = None) -> np.ndarray:
    """ENU shift (m) at a point when MOON_ME numbers are read as MOON_PA (note 02 E1, its sign convention: at the
    tile centre east -444.3 m, north +487.0 m, up -0.125 m): the point moves by (M - I) r, M = me_to_pa_matrix();
    the opposite reading moves it by the opposite vector. Expressed in the ENU frame of the datum (default: the
    point itself)."""
    r = latlon_to_cart(lat_deg, lon_deg, h_m)
    M = me_to_pa_matrix()
    d = (M - np.eye(3)) @ r
    Q = (datum.Q if datum is not None else enu_basis(lat_deg, lon_deg))
    return Q @ d


def base_datum(terrain=None) -> Datum:
    """The BASE datum of the Connecting Ridge pack (site BASE at local [7450, 7510])."""
    x, y = 7450.0, 7510.0
    lat, lon = site_to_latlon(x, y)
    h = 0.0
    if terrain is not None:
        h = float(terrain.height(x, y))
    return Datum(float(lat), float(lon), h)
