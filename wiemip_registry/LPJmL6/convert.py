"""LPJmL6 adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJmL6"
_OUTPUT = DATA_ROOT


# Token suffixes the run dir AND trails the cadence in the filename:
# ukesm_cou_noNitrogen/LPJmL6_ukesm_cou_albedo_mon_noNitrogen_05.nc
_FACTORIALS = {
    Factorial.baseline.name: "",
    Factorial.noNitrogen.name: "_noNitrogen",
}


class LPJmL6(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = _FACTORIALS
    LAYERED_VARIABLES = {
        "soilT",
        "mrsoLayer",
        "cSoilLayers",
        "nOrgSoilLayer",
        "nInorgSoilLayer",
    }

    def land_carbon_variables(self) -> list[str]:
        """
        Unconfirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    yearly = {"alt", "fNHarvest", "cLeafpft", "cRootpft", "cWoodpft"}

    def _get_variable(self, wiemip_variable: str) -> str:
        return wiemip_variable

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
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
        post = self.FACTORIALS[factorial]

        z = str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "LPJmL6"
            / f"{run}{post}"
            / f"{prefix}_{variable}_{cadence}{post}_05.nc"
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

    @property
    def area_weight_path(self):
        return (
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "LPJmL6"
            / "stable_bgc"
            / "LPJmL6_stable_bgc_land_area_yr_05.nc"
        )

    def _compute_weights(self) -> xr.DataArray:
        """Provided land-area raster [m²], 1850 slice. Every run ships the same
        `land_area` file; it shrinks 0.2% by 2000 (132.04 -> 131.79 Mkm²) the same
        way in every run, so one static slice serves them all. Weights cVeg 1850
        at 800 Pg C where the full spherical cell area gave 904."""
        ref = xr.open_dataset(self.area_weight_path, decode_times=self.DECODE)
        a = ref["land_area"].isel(time=0).drop_vars("time").load()
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
