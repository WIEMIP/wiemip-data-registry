"""BiomeE adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "BiomeE"
_OUTPUT = DATA_ROOT
_RUN_SUFFIX = "_noCH4"
_HIST_FILE_FORCING = "ukesm"  # hist is forced by CRUJRA but mislabeled hist
# the 11-02 hist re-upload stamps its 1850-2023 axis "days since 2024-01-01" (10-27 said 1850-01-01)
_HIST_MISSTAMPED_UNITS = "days since 2024-01-01"
_HIST_YEAR_SHIFT = 2024 - 1850
# transpft is labelled W m-2 but holds a water flux in kg m-2 s-1 (values ~1e-6);
# latent heat of vaporization turns it into the requested W m-2
_LATENT_HEAT_VAPORIZATION = 2.501e6  # J kg-1
_WATER_FLUX_AS_LATENT_HEAT = {"transpft"}

# overshoot hist only, the scenario runs hold both as requested (README notes 6 and 7):
# burntArea has the year's burned fraction in each of its 12 months, not a twelfth of it,
# and cVegpft is a twelfth of its value. Drop both when hist is re-uploaded without them.
_HIST_TWELVE_TIMES_TOO_HIGH = {"burntArea"}
_HIST_TWELVE_TIMES_TOO_LOW = {"cVegpft"}


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
    FRACTION_TO_PERCENT = {"burntArea"}

    PROVISIONAL_DATA = tuple(
        (experiment, variable)
        for experiment in ("1pctCO2", "overshoot")
        for variable in (
            "ch4",
            "fWoodLitter",
            "fRootLitter",
            "fVegLitter",
            "fLeafLitter",
        )
    )

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

    def _time(self, ds: xr.Dataset, experiment: str, simulation: str):
        time = ds["time"].values  # decoded noleap dates (decode_times=True)
        is_hist = (experiment, simulation) == ("overshoot", "hist")
        if is_hist and ds["time"].encoding.get("units") == _HIST_MISSTAMPED_UNITS:
            return [step.replace(year=step.year - _HIST_YEAR_SHIFT) for step in time]
        return time

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        if variable in _WATER_FLUX_AS_LATENT_HEAT:
            da = (da * _LATENT_HEAT_VAPORIZATION).assign_attrs(
                {**da.attrs, "units": "W m-2"}
            )
        is_hist = (experiment, simulation) == ("overshoot", "hist")
        if is_hist and variable in _HIST_TWELVE_TIMES_TOO_HIGH:
            da = (da / 12).assign_attrs(da.attrs)
        if is_hist and variable in _HIST_TWELVE_TIMES_TOO_LOW:
            da = (da * 12).assign_attrs(da.attrs)
        return core.standardize(
            da, self.LAT, self.LON, self._time(ds, experiment, simulation)
        )

    @property
    def area_weight_path(self):
        return _OUTPUT / "1pctCO2" / "output" / "BiomeE" / "veg_area.nc"

    def _compute_weights(self) -> xr.DataArray:
        """Provided vegetated-area raster [m²] (BiomeE README recipe)."""
        a = xr.open_dataset(self.area_weight_path)["veg_area"]
        a = a.drop_vars("time", errors="ignore")
        return core.rename_latlon(a, self.LAT, self.LON)
