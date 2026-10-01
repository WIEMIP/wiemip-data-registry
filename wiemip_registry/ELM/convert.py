"""ELM (E3SM Land Model) adapter.

Flat layout, `ELM_<forcing>_<sim>[_nofire]_<VAR>_mon_05.nc`. The 2026-09-30 upload
re-labelled bgc/ctrl `stable` and added `_ndep` and `nofire` runs; the older
`ELM_ukesm_bgc_*`/`ELM_ukesm_ctrl_*` (2026-09-28) are superseded and unreachable.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "ELM"
_OUTPUT = DATA_ROOT

_UNDECLARED_FILL = 1e20


class ELM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "_nofire",  # trails the sim token
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
    }

    def land_carbon_variables(self) -> list[str]:
        """
        Unconfirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def _get_variable(self, wiemip_variable: str) -> str:
        return self.wiemip_to_elm_variable_mapping.get(wiemip_variable, wiemip_variable)

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        fname = (
            f"{MODEL}_{forcing}_{simulation}{self.FACTORIALS[factorial]}_"
            f"{self._get_variable(variable)}_mon_05.nc"
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
