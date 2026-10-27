"""JSBACH adapter.

Naming (verified on the bucket): nested run dirs holding same-named files.
bgc/ctrl carry a `stable_` tag (`JSBACH_stable_<sim>`), cou carries the GCM
(`JSBACH_<forcing>_cou`); the factorial is a trailing suffix, except the dynamic
vegetation runs (2026-09-23), which put a `dynveg` token before the sim in the
filename and a suffix on the dir only. path() is a pure transform — what exists is
decided by read() opening the file.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "JSBACH"
_OUTPUT = DATA_ROOT

# Overshoot hist/ctrl are CRUJRA-driven; the scenarios carry the GCM pattern.
_CRUJRA_FORCED_SIMULATIONS = ("hist", "ctrl")
_CRUJRA_TOKEN = "crujra3"

_OVERSHOOT_RUN_TOKENS = {"baseline": "", "dynVeg": "dynveg"}

_DYNVEG_FILE_FORCING = "ukesm"

_RUN_DIR_OVERRIDES = {
    ("cou", "ipsl", "dynVeg_noFire_noNitrogen"): (
        "wiemip_1pctCO2_dynveg_ipsl_nofire_cou_pftlevel"
    ),
}

# Layer middles [m] from the bucket README's 5-layer table, whose "depth" column is the
# layer bottom (0.065, 0.319, 1.232, 4.134, 9.834). The files carry bare indices.
_SOIL_LAYER_DEPTHS = (0.0325, 0.192, 0.7755, 2.683, 6.984)


def _stem(
    simulation, forcing, run_token: str = "", stable_token: str = "stable"
) -> str:
    if simulation.split("_")[0] in ("cou", "rad"):
        return f"JSBACH_{forcing}_{run_token}{simulation}"
    return f"JSBACH_{stable_token}_{run_token}{simulation}"  # bgc, ctrl (+ _ndep)


class JSBACH(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = {
        Factorial.baseline.name: ("", "", ""),
        Factorial.noNitrogen.name: ("_noNitrogen", "", "_noNitrogen"),
        Factorial.noFire.name: ("_noFire", "", "_noFire"),
        "dynVeg_noNitrogen": ("_dynveg_noNitrogen", "dynveg_", ""),
        "dynVeg_noFire_noNitrogen": ("_dynveg_noNitrogen_noFire", "dynveg_nofire_", ""),
    }
    OVERSHOOT_FACTORIALS = _OVERSHOOT_RUN_TOKENS
    LAYERED_VARIABLES = {"soilT", "mrsoLayer"}
    # fixed fields: one raster at the 1pctCO2 dir top serves every run in both arms
    FIXED = {"sftlf"}

    # fN2OFire is total fire N emissions, not only N2O
    PROVISIONAL_DATA = (("1pctCO2", "fN2OFire"), ("overshoot", "fN2OFire"))

    def land_carbon_variables(self) -> list[str]:
        """
        Aug 7: Confirmed with Beiyao Xu that our aggregations and
        definitions of land carbon stock are correct.
        They include cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        if variable in self.FIXED:
            return str(self.area_weight_path)
        dir_suf, run_token, post = self.FACTORIALS[factorial]
        run_dir = _RUN_DIR_OVERRIDES.get(
            (simulation, forcing, factorial), f"{_stem(simulation, forcing)}{dir_suf}"
        )
        stable_token = _DYNVEG_FILE_FORCING if run_token else "stable"
        file_stem = _stem(simulation, forcing, run_token, stable_token)
        cad = "yr" if core.is_annual(variable) else "mon"
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "JSBACH"
            / run_dir
            / f"{file_stem}_{variable}_{cad}{post}_1.nc"
        )

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        # Run dir is the bare simulation token, `_dynveg`-suffixed for that factorial.
        run_token = self.OVERSHOOT_FACTORIALS.get(factorial or Factorial.baseline.name)
        if run_token is None:
            raise core.MissingFactorialError(
                f"{MODEL} ran no '{factorial}' overshoot config "
                f"(has: {sorted(self.OVERSHOOT_FACTORIALS)})"
            )
        if variable in self.FIXED:
            return str(self.area_weight_path)
        forcing_token = forcing
        if simulation in _CRUJRA_FORCED_SIMULATIONS:
            forcing_token = _DYNVEG_FILE_FORCING if run_token else _CRUJRA_TOKEN
        run_dir = f"{simulation}_{run_token}" if run_token else simulation
        file_token = f"{run_token}_{simulation}" if run_token else simulation
        cadence = "yr" if core.is_annual(variable) else "mon"
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / "JSBACH"
            / run_dir
            / f"JSBACH_{forcing_token}_{file_token}_{variable}_{cadence}_1.nc"
        )

    def _time(self, ds: xr.Dataset):
        return ds["time"].values  # already datetime64 (decode_times=True)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        if variable in self.FIXED:
            # the raster spells latitude/longitude, unlike JSBACH's output
            return core.rename_latlon(da, "latitude", "longitude")
        if "pool" in da.dims:
            da = da.assign_coords(pool=np.arange(1, da.sizes["pool"] + 1))
        if variable in self.LAYERED_VARIABLES:
            da = da.assign_coords(
                layer=("layer", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
            )
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    @property
    def area_weight_path(self):
        return _OUTPUT / "1pctCO2" / "output" / "JSBACH" / "sftlf_1.nc"

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²] (ocean -> NaN on the data)."""
        ref = xr.open_dataset(
            self.path(
                "1pctCO2",
                "bgc",
                "ukesm",
                "baseline",
                "cVeg",
            ),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        sftlf = core.rename_latlon(
            xr.open_dataset(self.area_weight_path)["sftlf"], self.LAT, self.LON
        )
        return core.rename_latlon(
            (cell * sftlf.values).astype("float32"), self.LAT, self.LON
        )
