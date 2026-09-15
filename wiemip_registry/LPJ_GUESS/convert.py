"""LPJ-GUESS adapter."""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT

MODEL = "LPJ_GUESS"
_DIR = "LPJ-GUESS"
_OUTPUT = DATA_ROOT


# The ctrl run (uploaded 2026-09-14) carries two spelling slips: the run dir says
# CRTL and the file prefix says `control`, where every other run repeats the dir's
# sim token. Flagged to the group for a rename on the bucket.
_DIR_SIM_TOKENS = {"ctrl": "CRTL"}
_FILE_SIM_TOKENS = {"ctrl": "control"}


def _sim_tokens(simulation: str) -> tuple[str, str]:
    """Return the (run-dir, file-prefix) sim tokens for a simulation."""
    base, _, ndep = simulation.partition("_")
    suffix = "-Ndep" if ndep else ""
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

    # Per-run filename slips: (sim, wiemip variable) -> (name token, cadence token
    # or None to take const.ANNUAL). ctrl mistypes two names in the FILENAME only -
    # the fields inside are spelled right - so this maps the name, not the read;
    # drop those two once the group re-uploads. bgc names the same PFT-cover field
    # by LPJ-GUESS's own `fpc_pft`, on an `ann` cadence token, where ctrl renamed it
    # to the vocab's landCoverFrac. Both hold the same 42 `fpc_<PFT>` fields.
    _FILENAME_OVERRIDES = {
        ("bgc", "landCoverFrac"): ("fpc_pft", "ann"),
        ("ctrl", "landCoverFrac"): ("landCOverFrac", None),
        ("ctrl", "nLitter"): ("nLiter", None),
    }

    _PFT_STEMS = {
        "cVegpft": "cmass",
        "cLitterpft": "clitter",
        "nVegpft": "nmass",
        "nLitterpft": "nlitter",
        "landCoverFrac": "fpc",
    }

    def land_carbon_variables(self) -> list[str]:
        return ["cLitter", "cSoil", "cVeg"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        base = simulation.partition("_")[0]
        run_sim, file_sim = _sim_tokens(simulation)
        run = f"{_DIR}_{forcing}_1pctCO2-{run_sim}"
        dir_style = (
            base in self._DIR_STYLE_SIMULATIONS and variable in self._DIR_STYLE_PREFIX
        )
        prefix = run if dir_style else f"{_DIR}_{forcing}_1pctco2_{file_sim}"
        name, cad = self._FILENAME_OVERRIDES.get((base, variable), (variable, None))
        cad = cad or ("yr" if core.is_annual(variable) else "mon")
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / _DIR
            / run
            / f"{prefix}_{name}_{cad}_05deg.nc"
        )

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
            else ds[variable]
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
