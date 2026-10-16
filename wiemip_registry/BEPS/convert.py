from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "BEPS"
_OUTPUT = DATA_ROOT

MONTHLY = {"wetfrac"}


class BEPS(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = {Factorial.baseline.name: "_noDynVeg_noFire"}

    def land_carbon_variables(self) -> list[str]:
        return ["cVeg", "cLitter", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        suffix = self.FACTORIALS[factorial]
        cadence = (
            "yr" if core.is_annual(variable) and variable not in MONTHLY else "mon"
        )
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / MODEL
            / simulation
            / f"BEPS_{forcing}_{simulation}_{variable}_{cadence}{suffix}_1.nc"
        )

    def _time(self, ds: xr.Dataset):
        return ds["time"].values

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "stable", Factorial.baseline.name, "cVeg"),
            decode_times=self.DECODE,
        )
        area = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(area, self.LAT, self.LON)
