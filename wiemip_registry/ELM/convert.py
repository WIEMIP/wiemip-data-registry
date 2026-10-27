"""ELM (E3SM Land Model) adapter.

Flat layout, `ELM_<forcing>_<sim>[_nofire]_<VAR>_<mon|yr>_05.nc`. The 2026-10-19 rerun
replaced the baseline bgc/ctrl and added ukesm cou/rad; the 2026-09-30 baseline files and
the 2026-09-28 `ELM_ukesm_bgc_*`/`ELM_ukesm_ctrl_*` are superseded and unreachable.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import ANNUAL, DATA_ROOT, Factorial

MODEL = "ELM"
_OUTPUT = DATA_ROOT

_UNDECLARED_FILL = 1e20

# pulled directly from their layered files
_SOIL_LAYER_DEPTHS = (
    0.007101,
    0.027925,
    0.062259,
    0.118865,
    0.212193,
    0.366066,
    0.619758,
    1.038027,
    1.727635,
    2.864607,
    4.739157,
    7.829766,
    12.925321,
    21.326469,
    35.17762,
)


class ELM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "_nofire",  # trails the sim token
    }
    LAYERED_VARIABLES = {
        "soilT",
        "soilTemp",
        "soilIce",
        "soilMoist",
        "mrsoLayer",
        "soilRh",
        "rhLayers",
        "cSoilLayers",
        "nOrgSoilLayer",
        "nInorgSoilLayer",
    }

    wiemip_to_elm_variable_mapping = {
        "gpp": "GPP",
        "npp": "NPP",
        "nbp": "NBP",
        "ra": "Ra",
        "rh": "Rh",
        "lai": "LAI",
        "fNnetmin": "fNetmin",
        "fNHarvest": "fnHarvest",
        "sftlf": "landfrac",
    }

    # fixed fields: one raster at the model dir top serves every run
    FIXED = {"sftlf"}

    # the rerun writes cOther yearly and wetfrac monthly
    RERUN_ANNUAL = (ANNUAL | {"cOther"}) - {"wetfrac"}

    def land_carbon_variables(self) -> list[str]:
        """
        Unconfirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def _is_rerun(self, simulation: str, factorial: str) -> bool:
        return not simulation.endswith("_ndep")

    def _get_variable(
        self, simulation: str, factorial: str, wiemip_variable: str
    ) -> str:
        if self._is_rerun(simulation, factorial) and wiemip_variable not in self.FIXED:
            return wiemip_variable
        return self.wiemip_to_elm_variable_mapping.get(wiemip_variable, wiemip_variable)

    def _cadence(self, simulation: str, factorial: str, wiemip_variable: str) -> str:
        if (
            self._is_rerun(simulation, factorial)
            and wiemip_variable in self.RERUN_ANNUAL
        ):
            return "yr"
        return "mon"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        if variable in self.FIXED:
            return self.area_weight_path
        fname = (
            f"{MODEL}_{forcing}_{simulation}{self.FACTORIALS[factorial]}_"
            f"{self._get_variable(simulation, factorial, variable)}_"
            f"{self._cadence(simulation, factorial, variable)}_05.nc"
        )
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / fname)

    def _time(self, ds: xr.Dataset, step: str):
        epoch = core.cf_reference_month(ds["time"].attrs["units"])
        return epoch + np.arange(ds.sizes["time"]).astype(f"timedelta64[{step}]")

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(simulation, factorial, variable)])
        da = da.where(da < _UNDECLARED_FILL)
        if variable in self.FIXED:
            return core.rename_latlon(da, self.LAT, self.LON)
        if variable in self.LAYERED_VARIABLES:
            level = "levdcmp" if "levdcmp" in da.dims else "levgrnd"
            da = da.assign_coords(
                {level: (level, list(_SOIL_LAYER_DEPTHS), {"units": "m"})}
            )
        step = "Y" if self._cadence(simulation, factorial, variable) == "yr" else "M"
        return core.standardize(da, self.LAT, self.LON, self._time(ds, step))

    @property
    def area_weight_path(self):
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / "landfrac.360x720.nc")

    def _compute_weights(self) -> xr.DataArray:
        """Land area per cell [m²] from the shipped `area` (km²) and `landfrac`."""
        ref = xr.open_dataset(self.area_weight_path)
        weights = (ref["area"] * 1e6 * ref["landfrac"]).load()
        ref.close()
        return core.rename_latlon(weights, self.LAT, self.LON)
