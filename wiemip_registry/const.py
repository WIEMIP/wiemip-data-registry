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

# Experiment dir on disk  <->  Python-safe namespace alias (leading digit fix).
EXPERIMENT_ALIASES = {"1pctCO2": "one_percent_co2", "overshoot": "overshoot"}

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
    ctrl = 2
    rad = 3


# Universal factorial buckets: the ONE canonical vocabulary every model maps into.
# Each adapter's `FACTORIALS` dict keys into THIS set (canonical bucket -> that
# model's path spelling), so a caller asks for a bucket uniformly — `noFire`,
# `ndep`, … — and each model resolves it to its own filename convention (CLASSIC
# `_noFire`, VISIT-UT `_noFire`, LPX-Bern `nofire_` prefix). A model that didn't
# run a bucket simply omits the key; selecting it raises at the factorial axis and
# lists what that model DOES have. Membership is enforced at import
# (wiemip_registry package init): an adapter key outside this set is a spelling
# drift and fails loudly, which is what keeps the buckets universal.
#
# Not every bucket is shared — the permafrost splits and JULES fire sweeps are
# genuinely model-specific — but they all live here so there's a single authority
# on the legal names. Add a new bucket here first, then map it in an adapter.
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
