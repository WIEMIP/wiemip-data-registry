"""LPJmL6 adapter.

Quirks (AGENTS.md §3): 1° grid, dims latitude/longitude, datetime time, units
written `kg C m$^{-2}$`. Global integral needs land fraction (per V. Arora):
area × sftlf × quantity. sftlf is static across runs — load once from BGC.

Naming (verified on the bucket): nested run dirs
`LPJmL6_<FORCING>_1pctCO2-<SIM><factorial>/` holding files
`<dir>_<var>_<cad>_1deg.nc`; ctrl is special-cased to `LPJmL6_stable_piControl…`
with a `LPJmL6_stable…` file prefix. Only UKESM was submitted, so the forcing
token is honored (ipsl/gfdl simply won't resolve at read()). path() is a pure
transform — what exists is decided by read() opening the file.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJmL6"
_OUTPUT = DATA_ROOT


_FACTORIALS = {
    Factorial.baseline.name: ("", ""),
}


class LPJmL6(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = _FACTORIALS

    yearly = {"alt", "fNHarvest"}

    def _get_variable(self, wiemip_variable: str) -> str:
        return wiemip_variable

    def overshoot_path(self, simulation, forcing, variable) -> str:
        return "null"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        if simulation in ("ctrl", "bgc"):
            run = f"stable_{simulation}"
        else:
            run = f"{forcing}_{simulation}"

        cadence = "yr" if core.is_annual(variable) else "mon"

        if variable in self.yearly:
            cadence = "yr"

        prefix = f"LPJmL6_{run}"

        z = str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "LPJmL6"
            / run
            / f"{prefix}_{variable}_{cadence}_05.nc"
        )
        return z

    def _time(self, ds: xr.Dataset):
        return ds["time"].values  # already datetime64 (decode_times=True)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(variable)])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Spherical cell area × static land fraction (sftlf)."""
        ref = xr.open_dataset(
            self.path(
                "1pctCO2",
                "bgc",
                "ukesm",
                "baseline",
                "cVeg",
            ),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        sftlf = xr.open_dataset(_SFTLF)["sftlf"]
        return core.rename_latlon((cell * sftlf).astype("float32"), self.LAT, self.LON)
