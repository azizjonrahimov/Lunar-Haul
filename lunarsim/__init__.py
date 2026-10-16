"""LunarSim: a discrete-event testbed for lunar surface cargo logistics.

The package models landers delivering cargo to landing pads near a south-pole
Moon base, a heterogeneous fleet of rovers owned by several operators, Earth
teleoperation under signal delay, the lunar day/night cycle, vehicle failures,
and a set of dispatch mechanisms ranging from "each company moves only its own
cargo" to a pooled marketplace with bundling, team-lift and backhaul.
"""
from .world import World, Site, build_default_world
from .assign import min_cost_assignment
from .config import load_scenario, save_scenario, scenario_to_dict, scenario_from_dict
__version__ = "3.0.0"
from .entities import Cargo, Vehicle, VehicleClass, VEHICLE_CLASSES
from .scenario import Scenario, BulkFlow, make_scenario
from .engine import Simulation, run
from . import dispatch
