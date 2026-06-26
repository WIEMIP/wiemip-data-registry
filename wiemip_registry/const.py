
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

# Variable short-names from the WIE-MIP data request (colligant/wiemip-data-request).
# The `variable` axis is free-form (any name resolves, erroring only at read if the file
# is absent) — this list is for iteration / completion, NOT a gating schema.
# >>> AUTO-GENERATED VARIABLES — regenerate with: python wiemip_registry/_sync_variables.py
VARIABLES = [
    "LWalbedo",
    "SWalbedo",
    "SoilRH",
    "acetone",
    "acetonepft",
    "albedo",
    "albedopft",
    "alt",
    "burntArea",
    "burntareaPft",
    "burntareaTotal",
    "burntareapeatTotal",
    "cCwd",
    "cLeaf",
    "cLitter",
    "cLitterpft",
    "cPoolVr",
    "cProduct",
    "cRoot",
    "cSoil",
    "cSoilAbove1m",
    "cSoilBelow1m",
    "cSoilLayers",
    "cSoilPools",
    "cSoilpft",
    "cVeg",
    "cVegpft",
    "cWood",
    "canopyheightTotal",
    "ccfuelTotal",
    "cfuelTotal",
    "ch4",
    "docFlux",
    "evapo",
    "evapotrans",
    "evapotranspft",
    "fAllocLeaf",
    "fAllocRoot",
    "fAllocWood",
    "fBNF",
    "fCH4Fire",
    "fFire",
    "fFireCH4pft",
    "fFireCOpft",
    "fFireCsoil",
    "fFireCveg",
    "fFireLitter",
    "fFirepft",
    "fLeafLitter",
    "fLitterSoil",
    "fN2",
    "fN2O",
    "fN2OFire",
    "fN2Odenit",
    "fN2Onit",
    "fN2Opft",
    "fNGraz",
    "fNH3vol",
    "fNHarvest",
    "fNLitterSoil",
    "fNOx",
    "fNdenitri",
    "fNdep",
    "fNleach",
    "fNloss",
    "fNnetmin",
    "fNnitri",
    "fNup",
    "fRootLitter",
    "fVegLitter",
    "fVegSoil",
    "fWoodLitter",
    "fch4layer",
    "fch4soil",
    "fdepth",
    "ffirech4",
    "ffirepeatTotal",
    "firePrescribed",
    "firedurationTotal",
    "fireintsTotal",
    "firemortalityTotal",
    "firenrTotal",
    "firenrperc95Total",
    "firerosTotal",
    "firesizeTotal",
    "firesizeperc95Total",
    "fluch4",
    "fpar",
    "fpftch4",
    "fwetch4",
    "gpp",
    "gpppft",
    "highcoverTotal",
    "ignlightTotal",
    "isopr",
    "isoprpft",
    "lai",
    "laipft",
    "landCoverFrac",
    "lowcoverTotal",
    "lwnet",
    "methanol",
    "methanolpft",
    "mfuelTotal",
    "mrro",
    "mrso",
    "mrsoLayer",
    "nInOrgSoilpft",
    "nInorgSoil",
    "nInorgSoilLayer",
    "nLitter",
    "nLitterpft",
    "nOrgSoil",
    "nOrgSoilLayer",
    "nOrgSoilpft",
    "nVeg",
    "nVegpft",
    "nbp",
    "nbppft",
    "npp",
    "npppft",
    "oceanCoverFrac",
    "pch4",
    "pco2",
    "pr",
    "qair",
    "qh",
    "qle",
    "qsb",
    "ra",
    "rainf",
    "rh",
    "rhLayers",
    "rhPools",
    "rhpft",
    "rnpft",
    "rsds",
    "shflxpft",
    "snowDepth",
    "snow_depthpft",
    "snowf",
    "soilIce",
    "soilMoist",
    "soilR",
    "soilRh",
    "soilT",
    "soilTemp",
    "soilWet",
    "sulfApp",
    "suppressedIgnit",
    "swalbedo",
    "swe",
    "swnet",
    "tair",
    "tas",
    "tcan",
    "terp",
    "terppft",
    "transpft",
    "tveg",
    "wetCH4",
    "wetfrac",
    "wind",
    "wtd",
]
# <<< AUTO-GENERATED VARIABLES

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
