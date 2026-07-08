"""LPJmL6 adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJmL6"
_OUTPUT = DATA_ROOT


_FACTORIALS = {
    Factorial.baseline.name: ("", ""),
}


class LPJmL6(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = _FACTORIALS

    yearly = {"alt", "fNHarvest"}

    def _get_variable(self, wiemip_variable: str) -> str:
        return wiemip_variable

    def overshoot_path(self, simulation, forcing, variable) -> str:
        return "null"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        if simulation in ("ctrl", "bgc"):
            run = f"stable_{simulation}"
        else:
            run = f"{forcing}_{simulation}"

        cadence = "yr" if core.is_annual(variable) else "mon"

        if variable in self.yearly:
            cadence = "yr"

        prefix = f"LPJmL6_{run}"

        z = str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "LPJmL6"
            / run
            / f"{prefix}_{variable}_{cadence}_05.nc"
        )
        return z

    def _time(self, ds: xr.Dataset):
        return ds["time"].values  # already datetime64 (decode_times=True)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(variable)])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²]; ocean cells drop out via the data's
        NaN mask (no land-fraction raster shipped)."""
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
