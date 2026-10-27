"""BiomeE adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "BiomeE"
_OUTPUT = DATA_ROOT
_RUN_SUFFIX = "_noCH4"
_HIST_FILE_FORCING = "ukesm"  # hist is forced by CRUJRA but mislabeled hist


class BiomeE(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True  # datetime time axis
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "noFire",
        Factorial.noNitrogen.name: "noNitrogen",
    }
    ANNUAL = {"cOther", "fvegHeightpft"}

    PROVISIONAL_DATA = (("1pctCO2", "ch4"), ("overshoot", "ch4"))

    def land_carbon_variables(self) -> list[str]:
        """
        Confirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        cad = "yr" if variable in self.ANNUAL or core.is_annual(variable) else "mon"
        is_fact = factorial != Factorial.baseline.name and factorial in self.FACTORIALS

        if simulation.split("_")[0] not in ("cou", "rad"):

            forcing = "stable"

        if is_fact:
            fname = f"BiomeE_{forcing}_fact_{simulation}_{self.FACTORIALS[factorial]}_{variable}_{cad}_05{_RUN_SUFFIX}.nc"
        else:
            fname = f"BiomeE_{forcing}_{simulation}_{variable}_{cad}_05{_RUN_SUFFIX}.nc"

        return str(_OUTPUT / "1pctCO2" / "output" / "BiomeE" / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        cad = "yr" if variable in self.ANNUAL or core.is_annual(variable) else "mon"
        if simulation == "hist":
            forcing = _HIST_FILE_FORCING
        fname = f"BiomeE_{forcing}_{simulation}_{variable}_{cad}_05{_RUN_SUFFIX}.nc"
        return str(_OUTPUT / "overshoot" / "output" / "BiomeE" / fname)

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
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    @property
    def area_weight_path(self):
        return _OUTPUT / "1pctCO2" / "output" / "BiomeE" / "veg_area.nc"

    def _compute_weights(self) -> xr.DataArray:
        """Provided vegetated-area raster [m²] (BiomeE README recipe)."""
        a = xr.open_dataset(self.area_weight_path)["veg_area"]
        a = a.drop_vars("time", errors="ignore")
        return core.rename_latlon(a, self.LAT, self.LON)
