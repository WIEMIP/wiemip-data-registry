from pathlib import Path
from enum import Enum

DATA_ROOT = Path("/mnt/wiemip")
CSV_ROOT = Path("csv")  # local mirror of the bucket tree; cached latitudinal-sum
# series land here ("csv/" prefix). Repoint to a shared writable dir on the box
# (e.g. /srv/wiemip-csv) for cross-user reuse. Bucket persistence is deferred.

MODEL_PACKAGES = [
    # Populated models only (the other ~20 bucket dirs are empty placeholders).
    # Each name is BOTH the subpackage dir and the Python-safe namespace alias.
    "BiomeE",
    "CLASSIC",
    "DLEM",
    "JSBACH",
    "JULES",
    "LPX_Bern",
    "VISIT_UT",
    "CLM_FATES",
]


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


class Simulation(Enum):
    """Run types across both experiments. 1pctCO2 uses bgc/cou/ctrl/rad (forcing
    cou/rad is the GCMPattern axis). Overshoot uses the scenario codes
    vl/l/m/hl (+ `_cf` constant-fire variants), hist / hist_ctrl, and ctrl. The
    ndep / noFire / noNitrogen / … sensitivity runs are per-model FACTORIALS
    (declared on each adapter), not simulations — they vary in name and meaning
    by model, so each convert.py spells them itself."""

    bgc = 0
    cou = 1
    ctrl = 2
    rad = 3
    l = 4
    hl = 5
    hl_cf = 6
    m = 7
    hist = 8
    hist_ctrl = 9
    vl = 10
    vl_cf = 11


FACTORIAL_BUCKETS: tuple[str, ...] = (
    "baseline",
    # fire
    "noFire",
    "Fire0005",
    "Fire0249",
    "Fire0304",
    "Fire0336",
    # nitrogen
    "noNitrogen",
    "ndep",
    "noNdep",
    #
    "noBVOC",
    "noDynVeg",
    # permafrost
    "noPermafrost",
    "noPermafrostC",
    "noPermafrostCN",
    "noPermafrostCNNinorg",
    "addPermafrostC",
    "addPermafrostCN",
    "addPermafrostCNNinorg",
    # combined sensitivities
    "ndep_noFire",
    "noFire_noNitrogen",
    "noPermafrost_noFire",
    "noNitrogen_addPermafrostC",
    "noNitrogen_noPermafrostC",
)
