from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, ONE_PERCENT_CO2_KEY, Factorial

MODEL = "EDv3"
_OUTPUT = DATA_ROOT

_CRUJRA_FORCED_SIMULATIONS = ("hist", "hist_ctrl", "ctrl")
_CRUJRA_TOKEN = "crujra"

_ONE_PCT_YEARS = slice("1850", "2000")


class EDv3(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = {Factorial.baseline.name: "", Factorial.noFire.name: "_nofire"}

    PROVISIONAL_DATA = (("1pctCO2", "cVegpft"), ("overshoot", "cVegpft"))

    wiemip_to_edv3_variable_mapping = {
        "tveg": "tran",
        "sftlf": "landFrac",
    }

    # fixed fields, `_fx_` on disk and no time axis
    FIXED = {"sftlf"}

    def land_carbon_variables(self) -> list[str]:
        return ["cVeg", "cSoil"]

    def _get_variable(self, wiemip_variable: str) -> str:
        return self.wiemip_to_edv3_variable_mapping.get(
            wiemip_variable, wiemip_variable
        )

    def _cadence(self, variable: str) -> str:
        if variable in self.FIXED:
            return "fx"
        return "yr" if core.is_annual(variable) else "mon"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        run = f"{forcing}_{simulation}{self.FACTORIALS[factorial]}"
        cadence = self._cadence(variable)
        fname = f"{MODEL}_{run}_{self._get_variable(variable)}_{cadence}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / f"1ptco2_{run}" / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        forcing_token = (
            _CRUJRA_TOKEN
            if simulation in _CRUJRA_FORCED_SIMULATIONS
            else forcing.lower()
        )
        run = f"{forcing_token}_{simulation}"
        cadence = self._cadence(variable)
        fname = f"{MODEL}_{run}_{self._get_variable(variable)}_{cadence}_05.nc"
        return str(
            _OUTPUT / "overshoot" / "output" / MODEL / f"overshoot_{run}" / fname
        )

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(variable)])
        if variable in self.FIXED:
            return core.rename_latlon(da, self.LAT, self.LON).transpose("lat", "lon")
        da = core.standardize(da, self.LAT, self.LON, ds["time"].values)
        if experiment == ONE_PERCENT_CO2_KEY:
            da = da.sel(time=_ONE_PCT_YEARS)
        return da

    @property
    def area_weight_path(self):
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / MODEL
            / "overshoot_crujra_hist"
            / "EDv3_crujra_hist_landFrac_fx_05.nc"
        )

    def _compute_weights(self) -> xr.DataArray:
        ref = xr.open_dataset(self.area_weight_path)
        land_area = ref["landArea"].load()
        ref.close()
        return core.rename_latlon(land_area, self.LAT, self.LON).transpose("lat", "lon")
