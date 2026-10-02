from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "EDv3"
_OUTPUT = DATA_ROOT

_CRUJRA_FORCED_SIMULATIONS = ("hist", "hist_ctrl", "ctrl")
_CRUJRA_TOKEN = "crujra"


class EDv3(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = {Factorial.baseline.name: "", Factorial.noFire.name: "_nofire"}

    PROVISIONAL_DATA = (("overshoot", "cVegpft"),)

    wiemip_to_edv3_variable_mapping = {
        "tveg": "tran",
    }

    def land_carbon_variables(self) -> list[str]:
        return ["cVeg", "cSoil"]

    def _get_variable(self, wiemip_variable: str) -> str:
        return self.wiemip_to_edv3_variable_mapping.get(
            wiemip_variable, wiemip_variable
        )

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        run = f"{forcing}_{simulation}{self.FACTORIALS[factorial]}"
        cadence = "yr" if core.is_annual(variable) else "mon"
        fname = f"{MODEL}_{run}_{self._get_variable(variable)}_{cadence}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / f"1ptco2_{run}" / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        forcing_token = (
            _CRUJRA_TOKEN
            if simulation in _CRUJRA_FORCED_SIMULATIONS
            else forcing.lower()
        )
        run = f"{forcing_token}_{simulation}"
        cadence = "yr" if core.is_annual(variable) else "mon"
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
        return core.standardize(da, self.LAT, self.LON, ds["time"].values)

    @property
    def _area_weight_path(self):
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / MODEL
            / "overshoot_crujra_hist"
            / "EDv3_crujra_hist_landFrac_fx_05.nc"
        )

    def _compute_weights(self) -> xr.DataArray:
        ref = xr.open_dataset(self._area_weight_path)
        land_area = ref["landArea"].load()
        ref.close()
        return core.rename_latlon(land_area, self.LAT, self.LON).transpose("lat", "lon")
