"""
Fire CH4, N2O and CO2 emissions (kg gas m-2 s-1) for any overshoot model.

    import wiemip_registry as wr
    ch4 = wr.fire_emission('CLM', 'hist', 'CH4', period=('1994', '2023'))
    n2o = wr.fire_emission('JSBACH', 'hl', 'N2O', forcing='ipsl')
    ch4.attrs['source']   # 'model', 'NEIVA pft_flux', 'NEIVA cveg_pft' or 'NEIVA latitude'

Returns the model's own output if it exists, otherwise fFire converted with NEIVA
emission ratios. The result is an xr.DataArray on the model's grid and time axis;
aggregation (monthly/annual, regional, global) is up to the user.

With `method=None` the first possible step is used (a model with `neiva_method` in
MODEL_SETTINGS uses that NEIVA method for every run instead of steps 2-4):

1. model    : fCH4Fire / fN2OFire, units converted from the `units` attribute
2. pft_flux : fFire * sum_pft fFirepft/sum(fFirepft) * f(pft)  (fFirepft + PFT table)
3. cveg_pft : fFire * sum_pft cVegpft/cVeg_tot * f(pft)        (cVegpft + PFT table)
4. latitude : fFire * f(fire type), forest where the hist mean cVeg over ref_period > 5 kg C m-2

| Fire type        | Criterion                   |
|------------------|-----------------------------|
| tropical forest  | forest, abs(lat) < 30       |
| temperate forest | forest, 30 <= abs(lat) < 60 |
| boreal forest    | abs(lat) >= 60              |
| savanna          | non-forest, abs(lat) < 60   |

Emission = fFire x NEIVA ratio of the fire type x molar mass ratio
(CH4 16.04/12.011, N2O 44.013/28.014, CO2 44.009/12.011).

What fFire contains is set per model in MODEL_SETTINGS (`ffire_basis`):

| ffire_basis   | fFire is              | ratios used                 | CO2                        |
|---------------|-----------------------|-----------------------------|----------------------------|
| 'C' (default) | all emitted carbon    | f_CH4-C/C, f_N2O-N/C        | fFire x f_CO2-C/C x 44/12  |
| 'CO2'         | carbon emitted as CO2 | f_CH4-C/C-CO2, f_N2O-N/C-CO2| fFire x 44/12              |

`neiva_pft_map.csv` (next to this module, `model;pft;neiva;comment`) maps each model PFT to a
NEIVA fire type, `forest` / `nonforest` (type from latitude) or `none`. `pft` is the PFT label
as `read()` returns it, or the position 1..n for numbered PFTs. Every PFT of the model needs a row.
Per-PFT fields in the adapter's `PER_PFT_AREA` are weighted by the run's landCoverFrac.

Missing NEIVA N2O values are taken from a similar fire type (tropical -> temperate forest;
peat -> boreal forest; crop, pasture -> savanna). With fixed ratios per fire type, relative
changes of CH4, N2O and CO2 follow fFire; the gases differ only where fire shifts between types.
"""

import warnings
from pathlib import Path

import pandas as pd
import xarray as xr

import wiemip_registry
from wiemip_registry import const, core

# ---------------------------------------------------------------- NEIVA table
#   f_CH4-C/C, f_N2O-N/C         : per kg C emitted in total
#   f_CH4-C/C-CO2, f_N2O-N/C-CO2 : per kg C emitted as CO2
# N2O is missing in NEIVA for tropical_forest, crop_residue, peat, pasture_maintenance
# -> taken from temperate_forest, savanna, boreal_forest, savanna.
#                        f_CH4-C/C  f_N2O-N/C  f_CH4-C/C-CO2  f_N2O-N/C-CO2
TABLE = {
    "savanna": (0.004105, 0.000173, 0.004730, 0.000199),
    "boreal_forest": (0.006975, 0.000254, 0.008153, 0.000297),
    "tropical_forest": (0.006826, 0.000191, 0.007905, 0.000229),
    "temperate_forest": (0.006874, 0.000191, 0.008233, 0.000229),
    "peat": (0.013890, 0.000254, 0.019372, 0.000297),
    "chaparral": (0.003805, 0.000315, 0.004279, 0.000354),
    "crop_residue": (0.003537, 0.000173, 0.004078, 0.000199),
    "pasture_maintenance": (0.012847, 0.000173, 0.015688, 0.000199),
}
# Factors applied to fFire, depending on what fFire contains:
#   'C'   : all emitted carbon    -> /C columns,     CO2-C/C = f_CH4-C/C / f_CH4-C/C-CO2
#   'CO2' : carbon emitted as CO2 -> /C-CO2 columns, CO2-C/fFire = 1
F = {
    "C": {t: {"CH4": a, "N2O": b, "CO2": a / c} for t, (a, b, c, d) in TABLE.items()},
    "CO2": {t: {"CH4": c, "N2O": d, "CO2": 1.0} for t, (a, b, c, d) in TABLE.items()},
}
M = {
    "CH4": 16.04 / 12.011,  # kg C -> kg CH4
    "N2O": 44.013 / 28.014,  # kg N -> kg N2O
    "CO2": 44.009 / 12.011,
}  # kg C -> kg CO2
UNITS = {g: f"kg {g} m-2 s-1" for g in M}
FOREST_THRESHOLD = 5.0  # kg C m-2

# ---------------------------------------------------------------- model settings
# Maintained centrally. Models not listed use DEFAULTS.
#   ffire_basis  : 'C' fFire = all emitted carbon | 'CO2' fFire = CO2-C only
#   model_factor : extra factor for the model's own gas output, per gas - only needed if
#                  the units attribute is missing or wrong (kg N / kg C are converted
#                  automatically from the units attribute, see _unit_factor)
#   use_pft_flux : False -> skip fFirepft (too large to load) and use cVegpft instead
#   retrieve     : extra arguments for retrieve_overshoot_variable, e.g. a factorial
#   neiva_method : one NEIVA method for every run of the model (no fallback), for models
#                  whose per-PFT inputs exist for some runs only
DEFAULTS = dict(
    ffire_basis="C", model_factor={}, use_pft_flux=True, retrieve={}, neiva_method=None
)
MODEL_SETTINGS = {
    # overshoot hist and ctrl have no fFirepft / cVegpft: pft_flux for the scenarios only
    # put a 34% step in CH4 per kg C at 2024 (0.0064 -> 0.0086)
    # ensure a single method is used across hist and future
    "JULES": dict(neiva_method="latitude"),
    # per-PFT files hold 5 slots whose PFT differs by cell (pft_code): the PFT table cannot be applied
    "BEPS": dict(neiva_method="latitude"),
    "LPX_Bern": dict(use_pft_flux=False),  # 30 PFTs, monthly: too large for long runs
    # 'MODEL': dict(ffire_basis='CO2'),        # if a model's fFire is CO2-carbon only
    # 'MODEL': dict(retrieve={'factorial': 'P0304'}),   # extra hub argument, if needed
}


def _fire_in_kgC(da):
    """fFire / fFirePFT in kg C m-2 s-1; converts if the units say kg CO2 (mass of CO2)."""
    if da is None:
        return None
    units = da.attrs.get("units") or ""
    u = units.replace("kg", " kg ").split()
    elem = u[u.index("kg") + 1] if "kg" in u and u.index("kg") + 1 < len(u) else None
    if elem == "CO2":
        return (da * (1 / M["CO2"])).assign_attrs(units="kg C m-2 s-1")
    if elem != "C":
        warnings.warn(
            f"fire flux units {units!r} not recognised - used as kg C m-2 s-1"
        )
    return da


def _unit_factor(units, gas):
    """Factor to kg gas from the units attribute: 'kg N ...' -> x M['N2O'],
    'kg C ...' -> x M['CH4'] / M['CO2']; 'kg <gas> ...' -> 1."""
    u = (units or "").replace("kg", " kg ").split()
    if "kg" not in u or u.index("kg") + 1 >= len(u):
        warnings.warn(
            f"f{gas}Fire: units {units!r} not recognised - used as kg {gas} m-2 s-1"
        )
        return 1
    elem = u[u.index("kg") + 1]
    if elem == gas:
        return 1
    if (gas, elem) in {("N2O", "N"), ("CH4", "C"), ("CO2", "C")}:
        return M[gas]
    warnings.warn(
        f"f{gas}Fire: units {units!r} not recognised - used as kg {gas} m-2 s-1"
    )
    return 1


# PFT -> NEIVA table: columns model, pft, neiva (optional: comment).
# neiva = a NEIVA fire type from TABLE, 'forest' / 'nonforest' (type from latitude)
# or 'none' (no fire). pft = PFT name as in the model files, or for numbered PFTs the
# position 1..n in file order (whether the file counts from 0 or from 1).
PFT_TABLE = Path(__file__).with_name("neiva_pft_map.csv")
TOKENS = {"forest", "nonforest"}


def pft_map_for(model, table=PFT_TABLE):
    """PFT label -> NEIVA type for one model from the central table ({} if none)."""
    if not Path(table).exists():
        return {}
    # separator from the header line (',' or ';' - e.g. Excel with German settings)
    with open(table, encoding="utf-8-sig") as fh:
        sep = ";" if ";" in fh.readline() else ","
    df = pd.read_csv(table, sep=sep, dtype=str, encoding="utf-8-sig").fillna("")
    df.columns = df.columns.str.strip().str.lower()
    out = {}
    for r in df[df["model"].str.strip() == model].itertuples():
        v = r.neiva.strip()
        if v.lower() in ("", "none"):
            v = None
        elif v not in TABLE and v not in TOKENS:
            raise ValueError(
                f"{table.name}: unknown NEIVA type {v!r} for {model} / {r.pft}"
            )
        out[r.pft.strip()] = v
    return out


# ---------------------------------------------------------------- conversion
def neiva(
    gas,
    fFire=None,
    fFirePFT=None,
    cVegPFT=None,
    cveg_ref=None,
    pft_map=None,
    landCoverFrac=None,
    ffire_basis="C",
):
    """
    NEIVA conversion -> kg gas m-2 s-1.
    Give fFirePFT (+ pft_map), or fFire with cVegPFT (+ pft_map) or with cveg_ref
    (time-mean cVeg, kg C m-2, same grid). Fluxes in kg C m-2 s-1.
    landCoverFrac (fraction) is applied to per-PFT fields if given.
    ffire_basis: 'C' if fFire is all emitted carbon, 'CO2' if it is CO2-carbon only.
    """
    Fb = F[ffire_basis]
    if fFirePFT is not None:
        E, d = fFirePFT, _pft_dim(fFirePFT)
        f = _pft_factor(E[d], E["lat"], gas, pft_map, Fb)
        lcf = (
            _grid(_match_pft(landCoverFrac, E), E)
            if landCoverFrac is not None
            else None
        )
        num = den = valid = None
        for k in range(E.sizes[d]):
            e = E.isel({d: k}, drop=True)
            if lcf is not None:
                e = e * _to_time(lcf.isel({d: k}, drop=True), e)
            ok = e.notnull()
            e = e.fillna(0)
            t = e * f.isel({d: k}, drop=True)
            num = t if num is None else num + t
            den = e if den is None else den + e
            valid = ok if valid is None else (valid | ok)
            del e, t, ok
        if fFire is not None:
            eff = (num / den.where(den > 0)).fillna(
                _lat_factor(E["lat"], gas, False, Fb)
            )
            out = fFire * _to_time(_grid(eff.where(valid), fFire), fFire)
        else:
            out = num.where(valid)
        method = "pft_flux"
    elif cVegPFT is not None:
        C, d = cVegPFT, _pft_dim(cVegPFT)
        if landCoverFrac is not None:
            C = C * _to_time(_grid(_match_pft(landCoverFrac, C), C), C)
        tot = C.sum(d)
        f = (
            ((C / tot.where(tot > 0)) * _pft_factor(C[d], C["lat"], gas, pft_map, Fb))
            .sum(d, min_count=1)
            .fillna(_lat_factor(C["lat"], gas, False, Fb))
        )
        out = fFire * _to_time(_grid(f, fFire), fFire)
        method = "cveg_pft"
    else:
        cveg_ref = _grid(cveg_ref, fFire)
        f = xr.where(
            cveg_ref > FOREST_THRESHOLD,
            _lat_factor(fFire["lat"], gas, True, Fb),
            _lat_factor(fFire["lat"], gas, False, Fb),
        )
        out = fFire * f.where(cveg_ref.notnull())
        method = "latitude"
    emission = (out * M[gas]).rename(f"f{gas}Fire")
    emission.attrs = dict(
        long_name=f"{gas} emission from fire (fFire x NEIVA emission ratio)",
        units=UNITS[gas],
        source=f"NEIVA {method}",
        ffire_basis=ffire_basis,
    )
    return emission


def _lat_factor(lat, gas, forest, Fb):
    """
    NEIVA factor by latitude band:
      forest     : |lat| < 30 tropical_forest, 30-60 temperate_forest, >= 60 boreal_forest
      non-forest : |lat| < 60 savanna,                                  >= 60 boreal_forest
    """
    a = abs(lat)
    if forest:
        return xr.where(
            a < 30,
            Fb["tropical_forest"][gas],
            xr.where(a < 60, Fb["temperate_forest"][gas], Fb["boreal_forest"][gas]),
        )
    return xr.where(a < 60, Fb["savanna"][gas], Fb["boreal_forest"][gas])


def _key(p):
    p = p.decode() if isinstance(p, bytes) else (p.item() if hasattr(p, "item") else p)
    if isinstance(p, float) and p.is_integer():
        p = int(p)  # 1.0 -> 1 (PFT labels stored as float)
    return str(p).strip()


def _pft_keys(labels):
    """PFT keys for the table: names as they are; numeric labels -> position 1..n
    in file order (files of the same model may count from 0 or from 1)."""
    keys = [_key(p) for p in labels.values]
    if all(k.lstrip("-").isdigit() for k in keys):
        return [str(i + 1) for i in range(len(keys))]
    return keys


def _pft_factor(labels, lat, gas, pft_map, Fb):
    pft_map = {str(k).strip(): v for k, v in pft_map.items()}
    keys = _pft_keys(labels)
    missing = [k for k in keys if k not in pft_map]
    if missing:
        raise KeyError(
            f"PFTs not in the PFT table (numeric PFTs = position 1..n): {missing}"
        )
    fs = []
    for k in keys:
        t = pft_map[k]
        if t is None:
            fs.append(xr.zeros_like(lat, dtype=float))
        elif t in TOKENS:
            fs.append(_lat_factor(lat, gas, t == "forest", Fb))
        else:
            fs.append(xr.full_like(lat, Fb[t][gas], dtype=float))
    return xr.concat(fs, labels)


def _pft_dim(da):
    extra = [d for d in da.dims if d not in ("time", "lat", "lon")]
    if len(extra) != 1:
        raise ValueError(f"cannot identify the PFT dimension in {da.dims}")
    return extra[0]


def _match_pft(lcf, ref):
    """Give landCoverFrac the same PFT dimension name and labels as ref."""
    d, dr = _pft_dim(lcf), _pft_dim(ref)
    if lcf.sizes[d] != ref.sizes[dr]:
        raise ValueError(
            f"landCoverFrac has {lcf.sizes[d]} PFTs, field has {ref.sizes[dr]}"
        )
    return (
        lcf.rename({d: dr}).assign_coords({dr: ref[dr]})
        if d != dr
        else lcf.assign_coords({dr: ref[dr]})
    )


def _grid(da, ref):
    return da.assign_coords(lat=ref["lat"], lon=ref["lon"])


def _to_time(da, ref):
    """Put da on ref's time axis (annual -> monthly by year)."""
    if "time" not in da.dims:
        return da
    if da.sizes["time"] != ref.sizes["time"]:
        da = (
            da.groupby("time.year")
            .mean()
            .sel(year=ref["time"].dt.year, method="nearest")
            .drop_vars("year")
        )
    return da.assign_coords(time=ref["time"])


# ---------------------------------------------------------------- registry access
VERBOSE = False  # True: print every read that is skipped as "not available"

# a registry answer that means "this input is not there", not a failure
NOT_AVAILABLE = (
    FileNotFoundError,
    core.MissingVariableError,
    core.ProvisionalDataError,
    core.InvalidSimulationError,
    core.MissingFactorialError,
)

OVERSHOOT = "overshoot"
ONE_PCT = const.ONE_PERCENT_CO2_KEY


def _load(experiment, model, forcing, sim, factorial, name, period=None, retrieve=None):
    """(DataArray, WIEFile) for one variable; (None, None) if it cannot be read."""
    try:
        if experiment == ONE_PCT:
            wiefile = wiemip_registry.retrieve_one_pct_variable(
                model=model,
                forcing=forcing,
                simulation=sim,
                factorial=factorial or "baseline",
                variable=name,
            )
        else:
            kwargs = dict(retrieve or {})
            if factorial is not None:
                kwargs["factorial"] = factorial
            wiefile = wiemip_registry.retrieve_overshoot_variable(
                model=model, forcing=forcing, simulation=sim, variable=name, **kwargs
            )
        da = wiefile.read()
    except NOT_AVAILABLE as e:
        if VERBOSE:
            print(
                f"[fire_emission] {experiment} {model} {forcing} {sim} {factorial} "
                f"{name}: not available ({type(e).__name__}: {e})"
            )
        return None, None
    except Exception as e:
        warnings.warn(
            f"{model} {sim} {name}: read failed "
            f"({type(e).__name__}: {e}) - treated as not available"
        )
        return None, None
    if period:  # by year: works beyond 2262 too
        y = da["time.year"]
        da = da.sel(time=(y >= int(period[0])) & (y <= int(period[1])))
    return da, wiefile


def _pft_area_fraction(da, wiefile):
    """Share of the registry's cell weight each PFT covers, for a PER_PFT_AREA variable."""
    if wiefile.variable not in wiefile._adapter.PER_PFT_AREA:
        return None
    cell_weights = wiefile._adapter.weights()
    pft_area = wiefile._pft_area_weights(da)
    return pft_area / cell_weights.where(cell_weights > 0)


# forest map of the latitude method: overshoot hist 1994-2023, 1pctCO2 the first
# REF_YEARS years of the same factorial's ctrl run
HIST_SIMULATION = "hist"
HIST_FORCING = "ukesm"  # hist is the same for all forcings; the registry needs one
HIST_REF_PERIOD = ("1994", "2023")
CTRL_SIMULATION = "ctrl"
CTRL_FORCING = "stable"
REF_YEARS = 30


class _NotAvailable(Exception):
    """Input for a NEIVA method is missing (not an error, just not possible)."""


METHODS = ("model", "pft_flux", "cveg_pft", "latitude")


def fire_emission(
    model,
    simulation,
    gas="CH4",
    forcing=None,
    period=None,
    method=None,
    force_neiva=False,
    ref_period=None,
    experiment=OVERSHOOT,
    factorial=None,
    **override,
):
    """
    Fire emissions of gas ('CH4', 'N2O' or 'CO2') in kg gas m-2 s-1 as xr.DataArray.

    simulation  : overshoot 'hist' or a scenario ('hl', 'ml', 'vl', ...);
                  1pctCO2 'bgc', 'cou', 'rad', 'ctrl' (and their _ndep runs)
    forcing     : overshoot scenarios 'ukesm', 'ipsl', 'gfdl' (ignored for hist);
                  1pctCO2 'stable' for bgc/ctrl, a GCM pattern for cou/rad
    period      : e.g. ('2003', '2020'), selects time after reading; `read()` still
                  loads the whole file
    method      : None (default) = model output if it exists, else best NEIVA method;
                  or force one: 'model', 'pft_flux', 'cveg_pft', 'latitude'
                  (raises FileNotFoundError if that method is not possible for the model)
    force_neiva : convert even if the model has its own output (= skip 'model')
    ref_period  : years of the cVeg mean for the latitude method's forest map; default
                  overshoot hist 1994-2023, 1pctCO2 the first 30 years of ctrl
    experiment  : 'overshoot' (default) or '1pctCO2'
    factorial   : the model's factorial; 1pctCO2 default 'baseline'. The 1pctCO2 forest
                  map comes from this factorial's own ctrl run
    override    : ffire_basis ('C' or 'CO2'); for testing also model_factor (number),
                  pft_map (dict), use_pft_flux, retrieve, neiva_method; otherwise taken from
                  MODEL_SETTINGS / neiva_pft_map.csv
    """
    if method is not None and method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if experiment not in (OVERSHOOT, ONE_PCT):
        raise ValueError(f"experiment must be {OVERSHOOT!r} or {ONE_PCT!r}")
    unknown = set(override) - {
        "ffire_basis",
        "model_factor",
        "pft_map",
        "use_pft_flux",
        "retrieve",
        "neiva_method",
    }
    if unknown:
        raise TypeError(f"fire_emission: unknown argument(s) {sorted(unknown)}")
    cfg = {**DEFAULTS, **MODEL_SETTINGS.get(model, {})}
    basis = override.get("ffire_basis", cfg["ffire_basis"])
    if basis not in F:
        raise ValueError(f"ffire_basis must be one of {list(F)}, not {basis!r}")
    extra = override.get("model_factor", cfg["model_factor"].get(gas, 1))
    pft_map = override.get("pft_map", pft_map_for(model))
    use_pft_flux = override.get("use_pft_flux", cfg["use_pft_flux"])
    retrieve = override.get("retrieve", cfg["retrieve"])
    neiva_method = override.get("neiva_method", cfg["neiva_method"])
    if neiva_method is not None and neiva_method not in METHODS[1:]:
        raise ValueError(f"neiva_method must be one of {METHODS[1:]}")
    if experiment == ONE_PCT:
        factorial = factorial or "baseline"
        if forcing is None:
            raise ValueError(
                f"{model} 1pctCO2 {simulation}: needs a forcing, e.g. 'stable'"
            )
        ref_simulation, ref_forcing = CTRL_SIMULATION, CTRL_FORCING
    else:
        if simulation != HIST_SIMULATION and forcing is None:
            raise ValueError(
                f'{model} {simulation}: scenarios need a forcing, e.g. forcing="ukesm"'
            )
        ref_simulation, ref_forcing = HIST_SIMULATION, HIST_FORCING
        ref_period = ref_period or HIST_REF_PERIOD

    def load(name, sim=simulation, p=period):
        if sim == ref_simulation:
            sim_forcing = ref_forcing
        else:
            sim_forcing = forcing
        return _load(experiment, model, sim_forcing, sim, factorial, name, p, retrieve)

    tag = f"{experiment} {model} {simulation} {forcing} {factorial}"

    # ---- model output
    if method == "model" or (method is None and not force_neiva):
        da, _ = load(f"f{gas}Fire")
        if da is not None:
            units_in = da.attrs.get("units")
            factor = _unit_factor(units_in, gas) * extra
            return (
                (da * factor)
                .rename(f"f{gas}Fire")
                .assign_attrs(
                    source="model", units=UNITS[gas], units_model=str(units_in)
                )
            )
        if method == "model":
            raise FileNotFoundError(f"{tag}: no own f{gas}Fire output")

    # ---- NEIVA methods
    cache = {}

    def get(key, name, sim=simulation, p=period, fire=False):
        if key not in cache:
            da, wiefile = load(name, sim, p)
            cache[key] = (_fire_in_kgC(da) if fire else da), wiefile
        if cache[key][0] is None:
            raise _NotAvailable(f"{tag}: no {key}")
        return cache[key]

    def pft_kw(da, wiefile):
        if not pft_map:
            raise _NotAvailable(f"{model}: no rows in the PFT table")
        return dict(
            ffire_basis=basis,
            pft_map=pft_map,
            landCoverFrac=_pft_area_fraction(da, wiefile),
        )

    def m_pft_flux():
        E, wiefile = get("fFirepft", "fFirepft", fire=True)
        kw = pft_kw(E, wiefile)
        try:
            fFire, _ = get("fFire", "fFire", fire=True)
        except _NotAvailable:
            fFire = None
        return neiva(gas, fFire=fFire, fFirePFT=E, **kw)

    def m_cveg_pft():
        fFire, _ = get("fFire", "fFire", fire=True)
        C, wiefile = get("cVegpft", "cVegpft")
        return neiva(gas, fFire=fFire, cVegPFT=C, **pft_kw(C, wiefile))

    def m_latitude():
        fFire, _ = get("fFire", "fFire", fire=True)
        try:
            cveg, _ = get("cVeg_ref", "cVeg", ref_simulation, ref_period)
        except _NotAvailable:
            cveg = None
        if cveg is not None and ref_period is None:
            years = cveg["time.year"]
            cveg = cveg.sel(time=years < int(years.min()) + REF_YEARS)
        if cveg is None or cveg.sizes.get("time", 1) == 0:
            raise FileNotFoundError(
                f"{tag}: no {ref_simulation} cVeg for the forest map of the latitude method"
            )
        return neiva(gas, fFire=fFire, cveg_ref=cveg.mean("time"), ffire_basis=basis)

    funcs = {"pft_flux": m_pft_flux, "cveg_pft": m_cveg_pft, "latitude": m_latitude}

    if method is None:  # the model's one NEIVA method, if it has one
        method = neiva_method
    if method in funcs:  # forced method: no fallback
        try:
            return funcs[method]()
        except _NotAvailable as e:
            raise FileNotFoundError(f"method {method} not possible - {e}") from None

    # automatic: pft_flux -> cveg_pft -> latitude
    for name in ["pft_flux", "cveg_pft"]:
        if name == "pft_flux" and not use_pft_flux:
            continue
        try:
            return funcs[name]()
        except _NotAvailable:
            continue
        except Exception as e:
            warnings.warn(
                f"{tag} {gas}: method {name} failed "
                f"({type(e).__name__}: {e}) - trying next method"
            )
    try:
        return m_latitude()
    except _NotAvailable as e:
        raise FileNotFoundError(str(e)) from None


def read_neiva(wiefile):
    """WIEFile.read() for the NEIVA fire gases: fFire x NEIVA ratios, never the model's own output."""
    gas = const.NEIVA_VARIABLES[wiefile.variable]
    return fire_emission(
        wiefile.model,
        wiefile.simulation,
        gas,
        forcing=wiefile.forcing,
        experiment=wiefile.experiment,
        factorial=wiefile.factorial,
        force_neiva=True,
    ).rename(wiefile.variable)
