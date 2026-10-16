"""Lander classes for the terminal-descent environment (lunar/Descent-v0).

Every constant carries a flag (Measured / Spec / Modelled / Assumed) and its source, as in the paper's
parameter tables. FRONTEND ports this file to JS line by line; keep it plain data.

The descent starts at the SPLICE robotic-reference "gate" (end of braking: 500 m slant range at 60 deg line
of sight, ~250 m downrange, ~430 m altitude, -15 m/s vertical, 30 m/s horizontal) and ends at touchdown.
Mass and propellant are therefore *at the gate*, not at launch.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict

G_MOON = 1.62          # m/s^2, Spec. NASA 2026 HLS touchdown paper uses 1.63:
                       # https://ntrs.nasa.gov/api/citations/20260001760/downloads/Apollo%2011%20LM%20Touchdown%20Dynamics%20VnV%20HLS.pdf
G0 = 9.80665           # m/s^2, Spec (standard gravity, defines Isp in seconds)

SPLICE_URL = "https://ntrs.nasa.gov/api/citations/20200002415/downloads/20200002415.pdf"
BE7_RELEASE_URL = "https://www.blueorigin.com/news/be7-engine-testing"
BE7_URLS = ["https://en.wikipedia.org/wiki/Blue_Moon_(spacecraft)", "https://en.wikipedia.org/wiki/BE-7",
            "https://newspaceeconomy.ca/2025/11/15/what-is-the-be-7/"]
APOLLO_DPS_URL = "https://www.lpi.usra.edu/lunar/documents/Bennett_NASA-TM-X-58040.pdf"
REPORT = "reports/Lunar landing and rover autonomy logistics.md"


@dataclass(frozen=True)
class LanderClass:
    name: str
    m_gate_kg: float          # total mass at the gate
    prop_gate_kg: float       # usable propellant left at the gate
    t_max_n: float            # maximum thrust
    t_min_n: float            # throttle floor (engine cannot run lower while lit)
    isp_s: float              # specific impulse
    tilt_max_deg: float       # largest thrust-axis tilt from vertical the vehicle may command
    tilt_rate_max_dps: float  # slew-rate limit of the thrust axis
    flags: Dict[str, str] = field(default_factory=dict)
    sources: Dict[str, str] = field(default_factory=dict)
    gate_overrides: Dict[str, float] = field(default_factory=dict)   # replaces GATE entries for this class

    @property
    def m_dry_kg(self) -> float:
        return self.m_gate_kg - self.prop_gate_kg

    @property
    def hover_tw(self) -> float:
        """Maximum thrust-to-weight at the gate."""
        return self.t_max_n / (self.m_gate_kg * G_MOON)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["m_dry_kg"] = self.m_dry_kg
        d["hover_tw"] = self.hover_tw
        return d


CLPS = LanderClass(
    name="CLPS", m_gate_kg=2000.0, prop_gate_kg=300.0, t_max_n=5000.0, t_min_n=1000.0, isp_s=311.0,
    tilt_max_deg=45.0, tilt_rate_max_dps=10.0,
    flags={"m_gate_kg": "Spec", "prop_gate_kg": "Assumed", "t_max_n": "Spec", "t_min_n": "Assumed",
           "isp_s": "Assumed", "tilt_max_deg": "Assumed", "tilt_rate_max_dps": "Assumed"},
    sources={"m_gate_kg": f"SPLICE robotic reference lander, 2,000 kg with a 5,000 N motor: {SPLICE_URL}",
             "t_max_n": SPLICE_URL,
             "t_min_n": "20 % throttle floor; Assumed (no CLPS throttle range published; Apollo DPS throttled to 10 %: "
                        f"{APOLLO_DPS_URL})",
             "isp_s": f"Apollo DPS full-thrust Isp 311 s used as a stand-in for a storable CLPS engine: {APOLLO_DPS_URL}",
             "prop_gate_kg": "15 % of gate mass; Assumed (terminal descent from the gate needs ~100 kg at Isp 311)",
             "tilt_max_deg": "Assumed", "tilt_rate_max_dps": "Assumed"},
)

MK1 = LanderClass(
    name="MK1", m_gate_kg=9000.0, prop_gate_kg=1000.0, t_max_n=44000.0, t_min_n=8900.0, isp_s=440.0,
    tilt_max_deg=45.0, tilt_rate_max_dps=8.0,
    flags={"m_gate_kg": "Assumed", "prop_gate_kg": "Assumed", "t_max_n": "Spec", "t_min_n": "Spec",
           "isp_s": "Assumed", "tilt_max_deg": "Assumed", "tilt_rate_max_dps": "Assumed"},
    sources={"m_gate_kg": "Blue Moon MK1 dry mass unpublished (21,350 kg fuelled, 3,000 kg payload); ~9,000 kg at "
                          f"the gate is Assumed: {BE7_URLS[0]}; a derived bound puts MK1's landed mass at 5.1-11.5 t, "
                          "which one BE-7 can hover in every case (verification_round_1.md item 3)",
             "t_max_n": f"BE-7 44 kN maximum, the one figure all sources agree on: {BE7_URLS[0]}; {BE7_URLS[1]}",
             "t_min_n": "BE-7 'throttling down to 2,000 lbf' (8.9 kN, 20 %): Blue Origin news release, 4 Dec 2020, "
                        f"{BE7_RELEASE_URL} (agrees with the 20-100 % in the BE-7 infobox; the 1,000 lbf figure has no source "
                        "and is dropped; research_notes/.../verification_round_1.md item 3)",
             "isp_s": f"BE-7 vacuum Isp 460 s is uncited and ~453 s is an estimate; 440 s Assumed: {BE7_URLS[1]}",
             "prop_gate_kg": "Assumed", "tilt_max_deg": "Assumed", "tilt_rate_max_dps": "Assumed"},
)

_LARGE_M = 60000.0
LARGE = LanderClass(
    name="LARGE", m_gate_kg=_LARGE_M, prop_gate_kg=5000.0, t_max_n=1.5 * _LARGE_M * G_MOON,
    t_min_n=0.25 * 1.5 * _LARGE_M * G_MOON, isp_s=350.0, tilt_max_deg=45.0, tilt_rate_max_dps=5.0,
    flags={"m_gate_kg": "Assumed", "prop_gate_kg": "Assumed", "t_max_n": "Modelled", "t_min_n": "Assumed",
           "isp_s": "Assumed", "tilt_max_deg": "Assumed", "tilt_rate_max_dps": "Assumed"},
    sources={"m_gate_kg": "Parametric 60 t cargo lander (Starship HLS / Blue Moon MK2 cargo class; dry masses "
                          f"unpublished, cargo 12-15 t per NASA IAC 2025): {REPORT}",
             "t_max_n": "hover T/W 1.5 at the gate mass (Modelled)", "t_min_n": "25 % throttle floor (Assumed)",
             "isp_s": "methalox landing engines, Assumed", "prop_gate_kg": "Assumed",
             "tilt_max_deg": "Assumed", "tilt_rate_max_dps": "Assumed",
             "gate_overrides": "Assumed: at T/W 1.5 the SPLICE robotic gate (250 m, 30 m/s) is past the stopping distance "
                               "(30^2 / (2 * 1.8 m/s^2) = 250 m at best), so the large class starts 400 m downrange at 25 m/s"},
    gate_overrides={"downrange_m": 400.0, "vh_mps": 25.0},
)

CLASSES: Dict[str, LanderClass] = {"CLPS": CLPS, "MK1": MK1, "LARGE": LARGE}

# --- the SPLICE gate and touchdown box (shared by all classes) -------------------------------------------
GATE = {  # Spec: SPLICE robotic reference braking target
    "slant_range_m": 500.0, "downrange_m": 250.0, "altitude_m": 430.0, "vz_mps": -15.0, "vh_mps": 30.0,
    "flag": "Spec", "source": SPLICE_URL,
}
TOUCHDOWN = {  # Spec: SPLICE multi-mission touchdown ground rules (3 sigma), "derived from past human lunar missions"
    "vz_max_mps": 2.0, "vh_max_mps": 1.0, "tilt_max_deg": 6.0, "rate_max_dps": 2.0,
    "delivery_radius_m": 50.0, "flag": "Spec", "source": SPLICE_URL,
}
TIPOVER_DEG = 12.0  # Spec/Measured: Apollo LM 12 deg effective-slope design limit; "If a lunar module came to rest at an
                    # angle beyond 12 degrees tilt the astronauts might not be able to launch" (ALHAT PM); Apollo 15 at 11 deg.
                    # https://ntrs.nasa.gov/api/citations/20205009125/downloads/Lunar%20Landing%20&%20Launch%20Pads%20v1.pdf
