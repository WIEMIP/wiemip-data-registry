from pathlib import Path
from enum import Enum

DATA_ROOT = Path("/mnt/wiemip")

MODEL_PACKAGES = [
    # Populated models only (the other ~20 bucket dirs are empty placeholders).
    # Each name is BOTH the subpackage dir and the Python-safe namespace alias.
    "BiomeE", "CLASSIC", "DLEM", "JSBACH", "JULES", "LPX_Bern", "VISIT_UT",
]

# Experiment dir on disk  <->  Python-safe namespace alias (leading digit fix).
EXPERIMENT_ALIASES = {"1pctCO2": "one_percent_co2", "overshoot": "overshoot"}

SPY = 365.25 * 86400.0   # seconds per year: flux rate -> annual integral
PG = 1e12                # 1 Pg = 1e12 kg
FILL_FLOOR = -1e3        # no physical stock/flux is below this; sentinel fills
# (BiomeE -1e5, JULES -9999, stray -99999) -> NaN.

# CMIP variable names treated as stocks (kg C m-2). Everything else is a flux
# (kg C m-2 s-1). Drives unit conversion in WIEFile.global_sum().
STOCKS = {"cVeg", "cSoil", "cLitter", "cWood", "cLeaf", "cRoot", "cCwd"}

# The requested variable list lives in variables.py (auto-generated from the
# WIE-MIP data request). Regenerate: python .github/workflows/_sync_variables.py

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
    """The four real run types. Forcing (cou/rad) is the GCMPattern axis; the
    ndep / noFire / noNitrogen / … sensitivity runs are per-model FACTORIALS
    (declared on each adapter), not simulations — they vary in name and meaning
    by model, so each convert.py spells them itself."""
    bgc = 0
    cou = 1
    rad = 2
    ctrl = 3

# NOTE: there is no global Factorial enum. The factorial axis is validated
# per-model against each adapter's `FACTORIALS` dict (see core.WIEAdapter).
