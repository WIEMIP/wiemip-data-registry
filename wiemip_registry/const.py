
from pathlib import Path
from enum import Enum

DATA_ROOT = Path("/mnt/wiemip")

SPY = 365.25 * 86400.0   # seconds per year: flux rate -> annual integral
PG = 1e12                # 1 Pg = 1e12 kg
FILL_FLOOR = -1e3        # no physical stock/flux is below this; sentinel fills
# (BiomeE -1e5, JULES -9999, stray -99999) -> NaN.

# CMIP variable names treated as stocks (kg C m-2). Everything else is a flux
# (kg C m-2 s-1). Drives unit conversion in WIEFile.global_sum().
STOCKS = {"cVeg", "cSoil", "cLitter", "cWood", "cLeaf", "cRoot", "cCwd"}

class Cadence(Enum):
    mon = "mon"
    yr = "yr"

class Resolution(Enum):
    half_degree = "05deg"
    one_degree = "1deg"

class GCMPattern(Enum):
    ukesm = "ukesm"
    ipsl   = "ipsl"
    gfdl   = "gfdl"

class Experiment(Enum):
    one_percent_co2 = "onepctco2"
    overshoot = "overshoot"

class Simulation(Enum):
    """
    Enum for holding the different simulations.
    Will add factorials here when they are more fully fleshed out.
    """
    bgc = 0
    cou = 1
    rad = 2
    ctrl = 3
    bgc_ndep = 4
    cou_ndep = 5
    rad_ndep = 6

class Factorial(Enum):
    baseline = 0
