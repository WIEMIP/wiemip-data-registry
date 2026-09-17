"""LPJ-EOSIM adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJ-EOSIM"  # model dir on disk (hyphenated)
_PREFIX = "LPJ_EOSIM"  # run sub-dir and file prefix (underscored)
_OUTPUT = DATA_ROOT

# Overshoot runs driven by CRUJRA rather than a GCM pattern. The run DIR drops the
# forcing token, but the filenames inside do NOT -- they fill the forcing slot with a
# repeat of the sim token, and hist_ctrl shortens both halves to `ctrl`:
#   LPJ_EOSIM_hist/      LPJ_EOSIM_hist_hist_<var>_<cad>_05.nc
#   LPJ_EOSIM_hist_ctrl/ LPJ_EOSIM_ctrl_ctrl_<var>_<cad>_05.nc
# Both verified on the 2026-09-16 listing (97 files each). `ctrl` alone is still not
# uploaded and is grouped with hist_ctrl on the assumption it spells the same way.
_CRUJRA_FILE_TOKENS = {
    "hist": "hist_hist",
    "hist_ctrl": "ctrl_ctrl",
    "ctrl": "ctrl_ctrl",
}


class LPJ_EOSIM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True  # gregorian "days since 1850-01-01" -> datetime64 directly
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "_noFire",
        Factorial.noNitrogen.name: "_noNitrogen",
    }

    # Cadence overrides of const.ANNUAL (verified on the bucket, 2026-08-28
    # upload): wetfrac and nInorgSoil arrive monthly, docFlux annual.
    MONTHLY = {"wetfrac", "nInorgSoil"}
    ANNUAL = {"docFlux"}

    def land_carbon_variables(self) -> list[str]:
        return ["cLitter", "cVeg", "cSoil"]

    def _factorial_suffix(self, factorial: str) -> str:
        return self.FACTORIALS.get(factorial, f"_{factorial}")

    def _cadence(self, variable: str) -> str:
        return (
            "mon"
            if variable in self.MONTHLY
            else "yr" if variable in self.ANNUAL or core.is_annual(variable) else "mon"
        )

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        second = forcing.lower() if gcm_forced else "stable"
        cad = self._cadence(variable)
        suffix = self._factorial_suffix(factorial)
        run_dir = f"{_PREFIX}_{second}_{simulation}{suffix}"
        fname = f"{_PREFIX}_{second}_{simulation}_{variable}_{cad}{suffix}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / run_dir / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        if simulation in _CRUJRA_FILE_TOKENS:
            run_dir, file_run = simulation, _CRUJRA_FILE_TOKENS[simulation]
        else:
            run_dir = file_run = f"{forcing.lower()}_{simulation}"
        fname = f"{_PREFIX}_{file_run}_{variable}_{self._cadence(variable)}_05.nc"
        return str(
            _OUTPUT / "overshoot" / "output" / MODEL / f"{_PREFIX}_{run_dir}" / fname
        )

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
    def _area_weight_path(self):
        return self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg")

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²]; ocean cells drop out via the data's
        NaN mask (no land-fraction raster shipped)."""
        ref = xr.open_dataset(self._area_weight_path, decode_times=self.DECODE)
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
