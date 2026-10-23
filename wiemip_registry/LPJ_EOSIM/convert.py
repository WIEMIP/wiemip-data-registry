"""LPJ-EOSIM adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJ-EOSIM"  # model dir on disk (hyphenated)
_PREFIX = "LPJ_EOSIM"  # run sub-dir and file prefix (underscored)
_OUTPUT = DATA_ROOT

_CRUJRA_SIMULATIONS = ("hist", "hist_ctrl", "ctrl")

_SOIL_T_DEPTHS = (0.0, 0.1, 0.25, 0.5, 0.7, 1.0, 1.5, 2.0)
_SOIL_LAYER_DEPTHS = (0.05, 0.15, 0.25, 0.4, 0.6, 0.85, 1.25, 1.75)


class LPJ_EOSIM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True  # gregorian "days since 1850-01-01" -> datetime64 directly
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "_noFire",
        Factorial.noNitrogen.name: "_noNitrogen",
        Factorial.noPermafrost.name: "_noPermafrost",
        "noDynVeg": "_noDynVeg",
    }

    LAYERED_VARIABLES = {"soilT", "soilIce", "soilMoist"}

    MONTHLY = {"wetfrac", "nInorgSoil"}
    ANNUAL = {"docFlux", "fN2OFire"}

    PROVISIONAL_DATA = (("1pctCO2", "firerosTotal"),)

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
        if simulation in _CRUJRA_SIMULATIONS:
            run_dir = file_run = simulation
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
        if variable == "soilT":
            # the 2026-09-16 1pctCO2 upload leads with a 0-50 cm mean; overshoot doesn't
            # two model versions that emit soil data differently, but same
            # underlying model
            if da.sizes["pool"] == len(_SOIL_T_DEPTHS) + 1:
                da = da.isel(pool=slice(1, None))
            da = da.assign_coords(pool=("pool", list(_SOIL_T_DEPTHS), {"units": "m"}))
        elif variable in self.LAYERED_VARIABLES:
            da = da.assign_coords(
                layer=("layer", list(_SOIL_LAYER_DEPTHS), {"units": "m"})
            )
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
