"""VISIT-UT adapter.

Quirks (AGENTS.md §3): 0.5° grid, lat/lon, time `years since AD 0` (fractional)
so decode_times=False and floor. All files are monthly (`_mon_`), even stocks.
Computed spherical area (no land frac; README integral = Σ flux×area).

Naming (verified on the bucket): nested run dirs holding same-named files.
bgc/ctrl are bare (`VISIT-UT_BGC`, `VISIT-UT_CTRL`); cou/rad carry the GCM
(`VISIT-UT_<forcing>_COU`); the factorial is a trailing suffix. path() is a pure
transform — what exists is decided by read() opening the file.

DATA-QUALITY: `fFire` is mis-scaled (~600×) and unphysical — flagged for
Akihiko Ito. Per the PLAN.md decision ("expect outputs to be perfect; it's up to
the user to debug bad files") the API still exposes it, unmasked. Caller beware.
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "VISIT-UT"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_FACTORIALS = {"baseline": "", "noBVOC": "_noBVOC", "noFire": "_noFire"}


def _run(simulation, forcing, suf: str) -> str:
    """The VISIT-UT run token = dir name = file prefix."""
    if simulation in (Simulation.cou, Simulation.rad):
        return f"VISIT-UT_{forcing.value}_{simulation.name.upper()}{suf}"
    return f"VISIT-UT_{simulation.name.upper()}{suf}"      # BGC, CTRL


class VISIT_UT(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False                      # "years since AD 0" fractional -> floor
    FACTORIALS = _FACTORIALS

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        run = _run(simulation, forcing, self.FACTORIALS[factorial])
        return str(_OUTPUT / "VISIT-UT" / run / f"{run}_{variable}_mon_05.nc")

    def _time(self, ds: xr.Dataset):
        # "years since AD 0" (fractional for monthly) -> datetime64
        return core.years_to_datetime(ds["time"].values)

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²]."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
