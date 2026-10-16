from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "CoLM"
_OUTPUT = DATA_ROOT

_CRUJRA_FORCED_SIMULATIONS = ("hist", "ctrl")


class CoLM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = {Factorial.baseline.name: ""}
    LAYERED_VARIABLES = {"soilT", "soilIce", "mrsoLayer", "cSoilLayers"}

    # annual on disk but not in const.ANNUAL
    ANNUAL = {"burntArea"}

    def land_carbon_variables(self) -> list[str]:
        """
        Unconfirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def _cadence(self, variable: str) -> str:
        return "yr" if variable in self.ANNUAL or core.is_annual(variable) else "mon"

    def _fname(self, run: str, variable: str) -> str:
        return f"{MODEL}_{run}_{variable}_{self._cadence(variable)}_1.nc"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        run = f"{forcing}_{simulation}"
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / MODEL
            / f"{MODEL}_{run}"
            / self._fname(run, variable)
        )

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        run = (
            simulation
            if simulation in _CRUJRA_FORCED_SIMULATIONS
            else f"{forcing}_{simulation}"
        )
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / MODEL
            / f"{MODEL}_{run}"
            / self._fname(run, variable)
        )

    def _time(self, ds: xr.Dataset, variable: str):
        time = core.to_datetime64(ds["time"].values)
        if self._cadence(variable) == "yr":
            return time - np.timedelta64(1, "D")
        return time

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds, variable))

    @property
    def area_weight_path(self):
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / MODEL
            / "CoLM_stable_bgc"
            / "CoLM_stable_bgc_sftlf_fx_1.nc"
        )

    def _compute_weights(self) -> xr.DataArray:
        """Spherical cell area × land fraction (`sftlf`, shipped in %)."""
        ref = xr.open_dataset(self.area_weight_path)
        cell = core.spherical_area(ref, self.LAT, self.LON)
        weights = (cell * ref["sftlf"] / 100.0).astype("float32").load()
        ref.close()
        return core.rename_latlon(weights, self.LAT, self.LON)
