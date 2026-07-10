"""LPJ-EOSIM adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJ-EOSIM"  # model dir on disk (hyphenated)
_PREFIX = "LPJ_EOSIM"  # run sub-dir and file prefix (underscored)
_OUTPUT = DATA_ROOT


class LPJ_EOSIM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True  # gregorian "days since 1850-01-01" -> datetime64 directly
    FACTORIALS = {Factorial.baseline.name: "", Factorial.noFire.name: "_noFire"}

    def _factorial_suffix(self, factorial: str) -> str:
        return self.FACTORIALS.get(factorial, f"_{factorial}")

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        second = forcing.lower() if gcm_forced else "stable"
        cad = "yr" if core.is_annual(variable) else "mon"
        suffix = self._factorial_suffix(factorial)
        run_dir = f"{_PREFIX}_{second}_{simulation}{suffix}"
        fname = f"{_PREFIX}_{second}_{simulation}_{variable}_{cad}{suffix}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / run_dir / fname)

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
