import os
from pathlib import Path
from enum import Enum

# where the data lives. Can overwrite with export WIEMIP_DATA_ROOT=/your/value/here,
# though you'll have to run it in every session, so you can also add to .bashrc.
DATA_ROOT = Path(os.environ.get("WIEMIP_DATA_ROOT", "/mnt/wiemip"))
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

# Variable names that are a per-m2 AMOUNT rather than a per-second RATE. This is the
# only thing `core.kind_of` decides: an amount is integrated as `sum(x*area)/PG`, a rate
# as `sum(x*area)*SPY/PG`. Membership was set from the `units` attribute of the real
# uploads (one file per model x variable) — `kg <X> m-2` is here, `kg <X> m-2 s-1` is
# not — so the `n` prefix is not a guide: nVeg/nSoil are nitrogen POOLS, while
# nbp/npp are carbon FLUXES.
#
# The integral is Pg for the carbon pools, Pg N for the nitrogen pools and Gt for the
# water pools; `PG = 1e12` is just kg -> Pg and carries no species.
#
# NOT here, and deliberately: the intensive variables (albedo, lai, tas/soilT, wetfrac,
# landCoverFrac, burntArea, snowDepth/wtd/alt, the W m-2 energy terms). They are not
# rates, but an area-weighted SUM is the wrong reduction for them regardless — they want
# a mean, which `latitudinal_sum` does not offer. Leaving them out keeps them visibly
# wrong rather than plausibly wrong.
STOCKS = {
    # carbon pools [kg C m-2]
    "cVeg",
    "cSoil",
    "cLitter",
    "cWood",
    "cLeaf",
    "cRoot",
    "cCwd",
    "cOther",
    "cProduct",
    "cPoolVr",
    "cVegpft",
    "cSoilpft",
    "cLitterpft",
    "cSoilPools",
    "cSoilLayers",
    "cSoilAbove1m",
    "cSoilBelow1m",
    "cfuelTotal",
    # nitrogen pools [kg N m-2]
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
    "nOrgSoilLayer",
    "nInorgSoilLayer",
    # water pools [kg m-2]
    "mrso",
    "mrsoLayer",
    "swe",
    "soilMoist",
    "soilIce",
}
ONE_PERCENT_CO2_KEY = "1pctCO2"

# Variables written at ANNUAL cadence (the `yr`/`ann` filename token); everything
# else is monthly (`mon`). Cadence is INDEPENDENT of the STOCKS split above: a pool
# is usually annual but `landCoverFrac`/`wetfrac` are annual without being amounts,
# and some models write pools monthly. Derived from the bucket filenames. Per-model overrides win — VISIT-UT writes everything
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
    # Not required by the protocol, but driver data was provided for the rest of
    # ScenarioMIP and both LPX-Bern and VISIT-UT submitted ml (+ VISIT-UT ml_cf).
    ml = 16
    ml_cf = 17


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
    # CLM's second run set (vs the hh baseline)
    "flat",
)
