"""TEM (TEM-MDM) adapter.

"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "TEM-MDM"
_OUTPUT = DATA_ROOT

_MONTH_START = np.array([0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334])

_CRUJRA_FORCED_SIMULATIONS = ("hist", "hist_ctrl", "ctrl")
_CRUJRA_TOKEN = "crujra3"


class TEM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = False  # noleap "days since 1850-01-01" -> decode by hand
    # Only the bare baseline runs were uploaded — no sensitivity factorials.
    FACTORIALS = {Factorial.baseline.name: ""}

    def land_carbon_variables(self) -> list[str]:
        """Confirmed with Shuo Chen on 10/08/2026. cVeg and cSoil."""
        return ["cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        # bgc/ctrl are not GCM-forced ("stable"); cou/rad carry the GCM name.
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        second = forcing.lower() if gcm_forced else "stable"
        cad = "yr" if core.is_annual(variable) else "mon"
        run_dir = simulation.upper()  # BGC / COU / CTRL
        fname = f"TEM-MDM_{second}_{simulation}_{variable}_{cad}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / "TEM" / run_dir / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        second = (
            _CRUJRA_TOKEN
            if simulation in _CRUJRA_FORCED_SIMULATIONS
            else forcing.lower()
        )
        cad = "yr" if core.is_annual(variable) else "mon"
        fname = f"TEM-MDM_{second}_{simulation}_{variable}_{cad}_05.nc"
        return str(_OUTPUT / "overshoot" / "output" / "TEM" / simulation / fname)

    def _time(self, ds: xr.Dataset):
        base = core.cf_reference_month(ds["time"].attrs.get("units", ""))
        days = np.asarray(ds["time"].values, dtype="float64")
        years = np.floor(days / 365.0).astype("int64")
        doy = np.mod(days, 365.0)
        month = np.searchsorted(_MONTH_START, doy, side="right") - 1  # 0..11
        return base + (years * 12 + month).astype("timedelta64[M]")

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
        """Computed spherical cell area [m²]; ocean cells drop out via the data's
        NaN mask (no land-fraction raster shipped)."""
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
