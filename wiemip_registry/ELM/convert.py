"""ELM (E3SM Land Model) adapter."""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "ELM"
_OUTPUT = DATA_ROOT

_CONSTANT_CLIMATE_SIMULATIONS = ("bgc", "ctrl")
# provisional - reached out to Qing Zhu about if stable was actually used
# to drive bgc and ctrl
_CONSTANT_CLIMATE_TOKEN = "ukesm"

_UNDECLARED_FILL = 1e20


class ELM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False
    FACTORIALS = {Factorial.baseline.name: ""}

    wiemip_to_elm_variable_mapping = {
        "gpp": "GPP",
        "npp": "NPP",
        "nbp": "NBP",
        "ra": "Ra",
        "rh": "Rh",
        "lai": "LAI",
        "fNnetmin": "fNetmin",
        "fNHarvest": "fnHarvest",
    }

    def land_carbon_variables(self) -> list[str]:
        """
        Unconfirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def _get_variable(self, wiemip_variable: str) -> str:
        return self.wiemip_to_elm_variable_mapping.get(wiemip_variable, wiemip_variable)

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        if simulation.partition("_")[0] in _CONSTANT_CLIMATE_SIMULATIONS:
            forcing = _CONSTANT_CLIMATE_TOKEN
        fname = (
            f"{MODEL}_{forcing}_{simulation}_{self._get_variable(variable)}_mon_05.nc"
        )
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / fname)

    def _time(self, ds: xr.Dataset):
        epoch = core.cf_reference_month(ds["time"].attrs["units"])
        return epoch + np.arange(ds.sizes["time"]).astype("timedelta64[M]")

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(variable)])
        da = da.where(da < _UNDECLARED_FILL)
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    @property
    def _area_weight_path(self):
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / "landfrac.360x720.nc")

    def _compute_weights(self) -> xr.DataArray:
        """Land area per cell [m²] from the shipped `area` (km²) and `landfrac`."""
        ref = xr.open_dataset(self._area_weight_path)
        weights = (ref["area"] * 1e6 * ref["landfrac"]).load()
        ref.close()
        return core.rename_latlon(weights, self.LAT, self.LON)
