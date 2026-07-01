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

# The requested variable list lives in variables.py (auto-generated from the
# WIE-MIP data request). Regenerate: python .github/workflows/_sync_variables.py

# WIE-MIP variable short-name  ->  CMIP7 branded variable name (the 2nd dotted
# token of the "CMIP7 Compound Name", e.g. `burntFractionAll` in
# `land.burntFractionAll.tavg-u-hxy-u.mon.glb`). WIE-MIP accepts BOTH names, so
# this lets us fold the CMIP7-named uploads onto the TRENDY-style keys the rest
# of the registry uses. Derived from ../wiemip-data-request/variables/*/*.json;
# keys mirror variables.VARIABLES. Several WIE-MIP names collapse to one CMIP7
# name (burntArea/burntareaTotal -> burntFractionAll, soilT/soilTemp -> tsl,
# soilRh/SoilRH -> rhSoilVr), so this mapping is NOT invertible.
WIEMIP_TO_CMIP7 = {
    "LWalbedo": "albedoLw",
    "SWalbedo": "albedoSw",
    "SoilRH": "rhSoilVr",
    "acetone": "acetone",
    "acetonepft": "acetoneVgt",
    "albedo": "albedo",
    "albedopft": "albedoVgt",
    "alt": "alt",
    "burntArea": "burntFractionAll",
    "burntareaPft": "burntFractionVgt",
    "burntareaTotal": "burntFractionAll",
    "burntareapeatTotal": "burntFractionPeat",
    "cCwd": "cCwd",
    "cLeaf": "cLeaf",
    "cLitter": "cLitter",
    "cLitterpft": "cLitterVgt",
    "cPoolVr": "cSoilPoolsVr",
    "cProduct": "cProduct",
    "cRoot": "cRoot",
    "cSoil": "cSoil",
    "cSoilAbove1m": "cSoilAbove1m",
    "cSoilBelow1m": "cSoilBelow1m",
    "cSoilLayers": "cSoilLayers",
    "cSoilPools": "cSoilPools",
    "cSoilpft": "cSoilVgt",
    "cVeg": "cVeg",
    "cVegpft": "cVegVgt",
    "cWood": "cWood",
    "canopyheightTotal": "canopyHeight",
    "ccfuelTotal": "combustCompleteFuelClass",
    "cfuelTotal": "cFuelClass",
    "ch4": "ch4",
    "docFlux": "docFlux",
    "evapo": "evapVgt",
    "evapotrans": "evspsbl",
    "evapotranspft": "evspsblVgt",
    "fAllocLeaf": "fAllocLeafVgt",
    "fAllocRoot": "fAllocRootVgt",
    "fAllocWood": "fAllocWoodVgt",
    "fBNF": "fBNF",
    "fCH4Fire": "fCH4Fire",
    "fFire": "fFire",
    "fFireCH4pft": "fCH4FireVgt",
    "fFireCOpft": "fCOFireVgt",
    "fFireCsoil": "fFirecSoil",
    "fFireCveg": "fFirecVeg",
    "fFireLitter": "fFireLitter",
    "fFirepft": "fFireVgt",
    "fLeafLitter": "fLeafLitter",
    "fLitterSoil": "fLitterSoil",
    "fN2": "fN2Vgt",
    "fN2O": "fN2O",
    "fN2OFire": "fN2OFire",
    "fN2Odenit": "fN2Odenit",
    "fN2Onit": "fN2Onit",
    "fN2Opft": "fN2OVgt",
    "fNGraz": "fNGraz",
    "fNH3vol": "fNH3vol",
    "fNHarvest": "fNHarvest",
    "fNLitterSoil": "fNLitterSoil",
    "fNOx": "fNOx",
    "fNdenitri": "fNdenitri",
    "fNdep": "fNdep",
    "fNleach": "fNleach",
    "fNloss": "fNloss",
    "fNnetmin": "fNnetmin",
    "fNnitri": "fNnitri",
    "fNup": "fNup",
    "fRootLitter": "fRootLitter",
    "fVegLitter": "fVegLitter",
    "fVegSoil": "fVegSoil",
    "fWoodLitter": "fWoodLitter",
    "fch4layer": "fCH4SoilLayer",
    "fch4soil": "fCH4Soil",
    "fdepth": "freezeDepth",
    "ffirech4": "fCH4Fire",
    "ffirepeatTotal": "fFirePeat",
    "firePrescribed": "firePrescribedFrac",
    "firedurationTotal": "fireDuration",
    "fireintsTotal": "fireIntensity",
    "firemortalityTotal": "fireMortality",
    "firenrTotal": "fireNumber",
    "firenrperc95Total": "fireNumberP95",
    "firerosTotal": "fireRos",
    "firesizeTotal": "fireSize",
    "firesizeperc95Total": "fireSizeP95",
    "fluch4": "fCH4Lut",
    "fpar": "fpar",
    "fpftch4": "fCH4Vgt",
    "fwetch4": "wetCH4",
    "gpp": "gpp",
    "gpppft": "gppVgt",
    "highcoverTotal": "highVegCoverFrac",
    "ignlightTotal": "ignLightning",
    "isopr": "isopr",
    "isoprpft": "isoprVgt",
    "lai": "lai",
    "laipft": "laiVgt",
    "landCoverFrac": "landCoverFrac",
    "lowcoverTotal": "lowVegCoverFrac",
    "lwnet": "rln",
    "methanol": "methanol",
    "methanolpft": "methanolVgt",
    "mfuelTotal": "fuelMoistureFuelClass",
    "mrro": "mrro",
    "mrso": "mrso",
    "mrsoLayer": "mrso",
    "nInOrgSoilpft": "nInOrgSoilVgt",
    "nInorgSoil": "nMineral",
    "nInorgSoilLayer": "nInorgSoilLayer",
    "nLitter": "nLitter",
    "nLitterpft": "nLitterVgt",
    "nOrgSoil": "nOrgSoil",
    "nOrgSoilLayer": "nOrgSoilLayer",
    "nOrgSoilpft": "nOrgSoilVgt",
    "nVeg": "nVeg",
    "nVegpft": "nVegVgt",
    "nbp": "nbp",
    "nbppft": "nbpVgt",
    "npp": "npp",
    "npppft": "nppVgt",
    "oceanCoverFrac": "oceanCoverFrac",
    "pch4": "pch4",
    "pco2": "pco2",
    "pr": "pr",
    "qair": "huss",
    "qh": "hflsSens",
    "qle": "hflsLat",
    "qsb": "qsb",
    "ra": "ra",
    "rainf": "prLiquid",
    "rh": "rh",
    "rhLayers": "rhLayer",
    "rhPools": "rhPool",
    "rhpft": "rhVgt",
    "rnpft": "rnVgt",
    "rsds": "rsds",
    "shflxpft": "shflxVgt",
    "snowDepth": "snowDepth",
    "snow_depthpft": "snowdepthVgt",
    "snowf": "prsn",
    "soilIce": "soilIce",
    "soilMoist": "mrsoLayer",
    "soilR": "soilR",
    "soilRh": "rhSoilVr",
    "soilT": "tsl",
    "soilTemp": "tsl",
    "soilWet": "soilWetness",
    "sulfApp": "sulfateApplied",
    "suppressedIgnit": "fireIgnitionsSuppressed",
    "swalbedo": "albedoSw",
    "swe": "swe",
    "swnet": "rsn",
    "tair": "tas",
    "tas": "tas",
    "tcan": "tCanopy",
    "terp": "terp",
    "terppft": "terpVgt",
    "transpft": "transVgt",
    "tveg": "tran",
    "wetCH4": "wetCH4",
    "wetfrac": "wetlandFrac",
    "wind": "sfcWind",
    "wtd": "wtd",
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


# NOTE: there is no global Factorial enum. The factorial axis is validated
# per-model against each adapter's `FACTORIALS` dict (see core.WIEAdapter).
