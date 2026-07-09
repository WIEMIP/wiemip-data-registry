import os
from pathlib import Path
from enum import Enum

DATA_ROOT = Path("/mnt/wiemip")

# Cached latitudinal-sum series are written here (a "csv/" mirror of the bucket
# tree). Defaults to a shared, world-readable dir on the JupyterHub so every user
# reuses the same cache instead of recomputing; override with the WIEMIP_CSV_PATH
# environment variable (e.g. point it at a local dir when running off the hub).
# Bucket persistence is deferred.
CSV_ROOT = Path(os.environ.get("WIEMIP_CSV_PATH", "/srv/wiemip-csv"))


SPY = 365.25 * 86400.0  # seconds per year: flux rate -> annual integral
PG = 1e12  # 1 Pg = 1e12 kg
FILL_FLOOR = -1e3  # no physical stock/flux is below this; sentinel fills
# (BiomeE -1e5, JULES -9999, stray -99999) -> NaN.

# CMIP variable names treated as stocks (kg C m-2). Everything else is a flux
# (kg C m-2 s-1). Drives unit conversion in WIEFile.global_sum().
STOCKS = {"cVeg", "cSoil", "cLitter", "cWood", "cLeaf", "cRoot", "cCwd"}

# Variables written at ANNUAL cadence (the `yr`/`ann` filename token); everything
# else is monthly (`mon`). Cadence is INDEPENDENT of stock/flux units: the
# nitrogen pools and per-PFT carbon are annual but are not carbon STOCKS. Derived
# from the bucket filenames. Per-model overrides win — VISIT-UT writes everything
# monthly and JULES everything annual, so their adapters ignore this set.
ANNUAL = {
    "cVeg",
    "cSoil",
    "cLitter",
    "cWood",
    "cLeaf",
    "cRoot",
    "cCwd",
    "cProduct",
    "cVegpft",
    "cSoilpft",
    "cLitterpft",
    "cSoilPools",
    "cSoilLayers",
    "cSoilAbove1m",
    "cSoilBelow1m",
    "nVeg",
    "nSoil",
    "nLitter",
    "nOrgSoil",
    "nInorgSoil",
    "nProduct",
    "nVegpft",
    "nSoilpft",
    "nLitterpft",
    "nOrgSoilpft",
    "nInOrgSoilpft",
    "nInorgSoilLayer",
    "nOrgSoilLayer",
    "landCoverFrac",
    "oceanCoverFrac",
    "wetfrac",
}


class Cadence(Enum):
    mon = "mon"
    yr = "yr"


class Resolution(Enum):
    half_degree = "05deg"
    one_degree = "1deg"


class GCMPattern(Enum):
    ukesm = "ukesm"
    ipsl = "ipsl"
    gfdl = "gfdl"
    stable = "stable"


class OnePctSimulation(Enum):

    bgc = 0
    cou = 1
    ctrl = 2
    rad = 3
    bgc_ndep = 4
    cou_ndep = 5
    rad_ndep = 6
    ctrl_ndep = 7


class OvershootSimulation(Enum):
    l = 7
    hl = 8
    hl_cf = 9
    m = 10
    hist = 11
    hist_ctrl = 12
    vl = 13
    vl_cf = 14
    ctrl = 15


class Factorial(Enum):

    baseline = 0
    noFire = 1
    # no nitrogen limitation
    noNitrogen = 2
    noPermafrost = 3
    noFire_noNitrogen = 4
    noFire_noPermafrost = 5
    noBVOC = 6


class Experiment(Enum):
    one_percent_co2 = "one_pct_co2"
    overshoot = "overshoot"


extra_factorials: tuple[str, ...] = (
    # fire
    "Fire0005",
    "Fire0249",
    "Fire0304",
    "Fire0336",
    "noBVOC",
    "noDynVeg",
    "noPermafrostC",
    "noPermafrostCN",
    "noPermafrostCNNinorg",
    "addPermafrostC",
    "addPermafrostCN",
    "addPermafrostCNNinorg",
    "noNitrogen_addPermafrostC",
    "noNitrogen_noPermafrostC",
)
