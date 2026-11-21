"""ORCHIDEE-MICT-CALIPSO adapter."""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import (
    DATA_ROOT,
    ONE_PERCENT_CO2_KEY,
    Factorial,
    GCMPattern,
)

MODEL = "ORCHIDEE-MICT-CALIPSO"
_PREFIX = "ORCHIDEE"
_OUTPUT = DATA_ROOT

_SIMULATION_TOKENS = {"bgc": "bgc", "cou": "cou", "ctrl": "stable_ctrl"}

_OVERSHOOT_SIMULATION_TOKENS = {"l": "low"}

_FIXED_RUN = "stable_ctrl_deepsoc"

_SOIL_CARBON_TERMS = ("cSoilpft", "maxvegetfrac")

_GLOBAL_LATITUDES = np.arange(89.5, -90, -1.0)

_TO_KG_PER_SECOND = {
    "gC/m^2/s": 1e-3,
    "gC/m^2 tot/pft/day": 1e-3 / 86400,
    "mm/d": 1 / 86400,
}


class ORCHIDEE_MICT_CALIPSO(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # bgc/ctrl time_counter restarts at 1850 every 240 months
    FACTORIALS = {
        Factorial.baseline.name: "deepsoc",
        "noPermafrostC": "no_deepsoc",
    }

    LAYERED_VARIABLES = {"soilT"}

    FIXED = {"sftlf", "Areas", "CONTFRAC", "RESOLUTION_X", "RESOLUTION_Y"}

    PROVISIONAL_DATA = (
        ("1pctCO2", "cSoilLayers"),
        ("1pctCO2", "cSoilPools"),
        ("1pctCO2", "cSoilAbove1m"),
        ("1pctCO2", "cSoilBelow1m"),
    )

    wiemip_to_orchidee_variable_mapping = {
        "sftlf": "CONTFRAC",
        "cOther": "cMisc",
        "cLitterpft": "cLitter_pft",
        "gpppft": "gpp_ORC",
        "laipft": "lai_ORC",
        "landCoverFrac": "VEGET_COV_MAX",
        "qsb": "drainage",
        "rainf": "rain",
    }

    def __init__(self):
        self._units_seen: dict[str, str] = {}

    def land_carbon_variables(self) -> list[str]:
        return ["cVeg", "cSoil", "cLitter"]

    def _get_variable(self, wiemip_variable: str) -> str:
        return self.wiemip_to_orchidee_variable_mapping.get(
            wiemip_variable, wiemip_variable
        )

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        if variable in self.FIXED:
            run = _FIXED_RUN
            cadence = "fx"
        else:
            simulation_token = _SIMULATION_TOKENS.get(simulation, simulation)
            # cou is UKESM-forced and its dirs carry no forcing token
            if simulation == "cou" and forcing != GCMPattern.ukesm.name:
                simulation_token = f"cou_{forcing}"
            run = f"{simulation_token}_{self.FACTORIALS[factorial]}"
            cadence = "mon"
        fname = f"{_PREFIX}_{run}_{self._get_variable(variable)}_{cadence}.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / f"{_PREFIX}_{run}" / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        simulation_token = _OVERSHOOT_SIMULATION_TOKENS.get(simulation, simulation)
        if forcing != GCMPattern.ukesm.name:
            simulation_token = f"{forcing}_{simulation_token}"
        fname = f"{variable}_{_PREFIX}_{simulation_token}_day_1deg.nc"
        return str(_OUTPUT / "overshoot" / "output" / MODEL / fname)

    def paths(self, experiment, simulation, forcing, factorial, variable) -> list[str]:
        if variable == "cSoil" and experiment == ONE_PERCENT_CO2_KEY:
            return [
                self.path(experiment, simulation, forcing, factorial, term)
                for term in _SOIL_CARBON_TERMS
            ]
        return super().paths(experiment, simulation, forcing, factorial, variable)

    def _time(self, ds: xr.Dataset):
        epoch = core.cf_reference_month(ds["time_counter"].attrs["units"])
        return epoch + np.arange(ds.sizes["time_counter"]).astype("timedelta64[M]")

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        if variable == "cSoil" and experiment == ONE_PERCENT_CO2_KEY:
            soil_by_pft, vegetation_fraction = (
                self.read(experiment, simulation, forcing, factorial, term)
                for term in _SOIL_CARBON_TERMS
            )
            soil_carbon = (soil_by_pft * vegetation_fraction).sum("veget", min_count=1)
            self._units_seen[variable] = soil_by_pft.attrs["units"]
            return soil_carbon.rename(variable).assign_attrs(
                units=soil_by_pft.attrs["units"]
            )

        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        name = (
            self._get_variable(variable)
            if experiment == ONE_PERCENT_CO2_KEY
            else variable
        )
        da = core.mask_fill(ds[name])
        self._units_seen[variable] = da.attrs.get("units", "")
        if variable in self.FIXED:
            return core.rename_latlon(da, self.LAT, self.LON).transpose("lat", "lon")
        da = da.drop_vars("time_centered", errors="ignore").rename(time_counter="time")
        if variable == "cSoilpft":
            da = da.sum("pool", min_count=1, keep_attrs=True)
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def to_pgc(self, total, variable):
        units = self._units_seen.get(variable, "")
        if core.kind_of(variable) == "flux" and units in _TO_KG_PER_SECOND:
            total = total * _TO_KG_PER_SECOND[units]
        return super().to_pgc(total, variable)

    @property
    def area_weight_path(self):
        return self.path("1pctCO2", "ctrl", "stable", "baseline", "Areas")

    def _compute_weights(self) -> xr.DataArray:
        """Provided cell area [m²] × continental fraction, spherical cell area elsewhere."""
        cell_area = self.read("1pctCO2", "ctrl", "stable", "baseline", "Areas").load()
        land_fraction = self.read(
            "1pctCO2", "ctrl", "stable", "baseline", "CONTFRAC"
        ).load()
        globe = xr.DataArray(
            dims=("lat", "lon"),
            coords={"lat": _GLOBAL_LATITUDES, "lon": cell_area["lon"]},
        )
        return (cell_area * land_fraction).combine_first(
            core.spherical_area(globe, "lat", "lon")
        )
