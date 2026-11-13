from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, ONE_PERCENT_CO2_KEY, Factorial

MODEL = "CARDAMOM-JPL"
_PREFIX = "CARDAMOMJPL"
_OUTPUT = DATA_ROOT

# the ukesm_stable_cou-bgc files are cou - bgc, accounting for CARDAMOM's emulator behavior

_ONE_PCT_YEARS = slice("1850", "2000")

_POOL_SPLITS = {
    "rhPools": {"cwd": "rhPoolsCWD", "litter": "rhPoolsLitter", "som": "rhPoolsSom"},
}


class CARDAMOM_JPL(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = {Factorial.baseline.name: ""}
    ANNUAL = {"cOther"}

    def land_carbon_variables(self) -> list[str]:
        return ["cVeg", "cLitter", "cCwd", "cSoilAbove1m"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        run = f"{forcing.lower() if gcm_forced else 'stable'}_{simulation}"
        cad = "yr" if variable in self.ANNUAL or core.is_annual(variable) else "mon"
        fname = f"{_PREFIX}_{run}_{variable}_{cad}_1deg.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / fname)

    def paths(self, experiment, simulation, forcing, factorial, variable) -> list[str]:
        file_variables = _POOL_SPLITS.get(variable, {variable: variable}).values()
        return [
            self.path(experiment, simulation, forcing, factorial, file_variable)
            for file_variable in file_variables
        ]

    def _read_one(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        if "Unit" in da.attrs:
            da = da.assign_attrs(units=da.attrs["Unit"])
        da = core.standardize(da, self.LAT, self.LON, ds["time"].values)
        if experiment == ONE_PERCENT_CO2_KEY:
            da = da.sel(time=_ONE_PCT_YEARS)
        return da

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        if variable in _POOL_SPLITS:
            split = _POOL_SPLITS[variable]
            pools = [
                self._read_one(experiment, simulation, forcing, factorial, file_var)
                for file_var in split.values()
            ]
            labels = xr.DataArray(list(split), dims="pool", name="pool")
            return xr.concat(pools, dim=labels).rename(variable)
        return self._read_one(experiment, simulation, forcing, factorial, variable)

    def _compute_weights(self) -> xr.DataArray:
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "stable", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
