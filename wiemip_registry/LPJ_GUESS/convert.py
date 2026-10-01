"""LPJ-GUESS adapter."""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJ_GUESS"
_DIR = "LPJ-GUESS"
_OUTPUT = DATA_ROOT


_DIR_SIM_TOKENS = {"ctrl": "CRTL"}
_FILE_SIM_TOKENS = {"ctrl": "control"}

_GCM_FORCED = {"cou", "rad"}

_NDEP_EXPERIMENT_TOKENS = {"bgc": "1pctCo2"}


def _sim_tokens(simulation: str) -> tuple[str, str]:
    """Return the (run-dir, file-prefix) sim tokens for a simulation."""
    base, _, ndep = simulation.partition("_")
    suffix = "-ndep" if ndep else ""
    run = _DIR_SIM_TOKENS.get(base, base.upper()) + suffix
    fil = _FILE_SIM_TOKENS.get(base, base.upper()) + suffix
    return run, fil


class LPJ_GUESS(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False

    # Only the bgc run uses the dir-style prefix, and only on these two; the ctrl
    # equivalents are spelled like every other file in their run.
    _DIR_STYLE_PREFIX = {"cLitterpft", "landCoverFrac"}
    _DIR_STYLE_SIMULATIONS = {"bgc"}

    FACTORIALS = {
        Factorial.baseline.name: ("", ""),
        Factorial.noFire.name: ("-NoFire", "-Nofire"),
    }

    _FILENAME_OVERRIDES = {
        ("bgc", "baseline", "landCoverFrac"): "fpc_pft_ann_05deg",
        ("ctrl", "baseline", "landCoverFrac"): "landCOverFrac_yr_05deg",
        ("ctrl", "baseline", "nLitter"): "nLiter_yr_05deg",
        ("bgc_ndep", "baseline", "gpp"): "gpp_mon_05eg",
        ("bgc_ndep", "baseline", "cLitterpft"): "cLitterpft-yr_05deg",
        ("bgc_ndep", "baseline", "nLitterpft"): "nLitterpft_mon_05deg",
        ("bgc_ndep", "baseline", "nVegpft"): "nVegpgt_yr_05deg",
        ("bgc_ndep", "baseline", "rh"): "rh_05deg",
        ("cou_ndep", "baseline", "gpppft"): "gpppfr_mon_05deg",
        ("cou_ndep", "baseline", "nVegpft"): "nVegpft_05deg",
        ("bgc", "noFire", "mrro"): "mrro_mon_yr_05deg",
        ("cou", "noFire", "cLitterpft"): "clitterpft_yr_05deg",
        ("cou", "noFire", "laipft"): "laipft_yr_05deg",
        ("ctrl", "noFire", "evapotranspft"): "evapotranspft_mon_yr_05deg",
    }

    _RUN_OVERRIDES = {
        ("ctrl", "noFire"): (
            "LPJ_GUESS_Stable_1pctCO2_Control-Nofire",
            "LPJ-GUESS_Stable_1pctCO2_Control_Nofire",
        ),
    }

    _FIELD_NAMES = {"ch4": "mch4"}

    _PFT_STEMS = {
        "cVegpft": "cmass",
        "cLitterpft": "clitter",
        "nVegpft": "nmass",
        "nLitterpft": "nlitter",
        "landCoverFrac": "fpc",
        "gpppft": "mgpp",
        "laipft": "mlai",
        "evapotranspft": "maet",
    }

    def land_carbon_variables(self) -> list[str]:
        return ["cLitter", "cSoil", "cVeg"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        base, _, ndep = simulation.partition("_")
        run_sim, file_sim = _sim_tokens(simulation)
        run_factorial, file_factorial = self.FACTORIALS[factorial]
        gcm = forcing.upper() if base in _GCM_FORCED else forcing
        if (simulation, factorial) in self._RUN_OVERRIDES:
            run, prefix = self._RUN_OVERRIDES[(simulation, factorial)]
        elif factorial != Factorial.baseline.name:
            gcm = "Stable" if gcm == "stable" else gcm
            run = f"{MODEL}_{gcm}_{run_sim}{run_factorial}"
            prefix = f"{_DIR}_{gcm}_1pctCO2_{file_sim}{file_factorial}"
        elif ndep:
            run = f"{MODEL}_{gcm}_{run_sim}"
            experiment = _NDEP_EXPERIMENT_TOKENS.get(base, "1pctCO2")
            prefix = f"{_DIR}_{gcm}_{experiment}_{file_sim}"
        elif base in _GCM_FORCED:
            run = f"{MODEL}_{gcm}_1pctCO2-{run_sim}"
            prefix = f"{_DIR}_{gcm}_1pctCO2_{file_sim}"
        else:
            run = f"{_DIR}_{forcing}_1pctCO2-{run_sim}"
            dir_style = (
                base in self._DIR_STYLE_SIMULATIONS
                and variable in self._DIR_STYLE_PREFIX
            )
            prefix = run if dir_style else f"{_DIR}_{forcing}_1pctco2_{file_sim}"
        cadence = "yr" if core.is_annual(variable) else "mon"
        name = self._FILENAME_OVERRIDES.get(
            (simulation, factorial, variable), f"{variable}_{cadence}_05deg"
        )
        return str(_OUTPUT / "1pctCO2" / "output" / _DIR / run / f"{prefix}_{name}.nc")

    def _time(self, ds: xr.Dataset):
        tu = ds["time"].attrs.get("units", "")
        tv = np.asarray(ds["time"].values).astype("int64")
        base = core.cf_reference_month(tu)
        if "months since" in tu:
            return base + tv.astype("timedelta64[M]")
        return base + (tv * 12).astype("timedelta64[M]")

    def _stack_pfts(self, ds: xr.Dataset, variable: str) -> xr.DataArray:
        stem = self._PFT_STEMS[variable]
        names = [n for n in ds.data_vars if n.startswith(f"{stem}_")]
        if not names:
            raise core.MissingVariableError(
                f"{variable}: no '{stem}_*' fields in {ds.encoding.get('source', '?')}"
            )
        da = xr.concat([ds[n] for n in names], dim="pft")
        da = da.assign_coords(pft=[n[len(stem) + 1 :] for n in names])
        da.name = variable
        da.attrs = {"units": ds[names[0]].attrs.get("units", "")}
        return da

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = (
            self._stack_pfts(ds, variable)
            if variable in self._PFT_STEMS
            else ds[self._FIELD_NAMES.get(variable, variable)]
        )
        return core.standardize(core.mask_fill(da), self.LAT, self.LON, self._time(ds))

    @property
    def _area_weight_path(self):
        return self.path("1pctCO2", "bgc", "stable", "baseline", "cVeg")

    def _compute_weights(self) -> xr.DataArray:
        ref = xr.open_dataset(self._area_weight_path, decode_times=self.DECODE)
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return cell
