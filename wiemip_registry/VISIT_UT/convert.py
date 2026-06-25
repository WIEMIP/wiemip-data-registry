"""VISIT-UT adapter.

Quirks (AGENTS.md §3): 0.5° grid, lat/lon, time `years since AD 0` (fractional)
so decode_times=False and floor. All files are monthly (`_mon_`), even stocks.
Computed spherical area (no land frac; README integral = Σ flux×area). Which
runs/variables resolve is decided by file existence (WIEAdapter.available).

DATA-QUALITY: `fFire` is mis-scaled (~600×) and unphysical — flagged for
Akihiko Ito. Per the PLAN.md decision ("expect outputs to be perfect; it's up to
the user to debug bad files") the API still exposes it, unmasked. Caller beware.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "VISIT-UT"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_PREFIX = {
    Simulation.bgc:  "VISIT-UT/VISIT-UT_BGC/VISIT-UT_BGC_",
    Simulation.cou:  "VISIT-UT/VISIT-UT_ukesm_COU/VISIT-UT_ukesm_COU_",
    Simulation.ctrl: "VISIT-UT/VISIT-UT_CTRL/VISIT-UT_CTRL_",
}


class VISIT_UT(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False                      # "years since AD 0" fractional -> floor

    def _fname(self, variable: str) -> str:
        return f"{variable}_mon_05.nc"      # all VISIT-UT output is monthly

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        if (experiment is not Experiment.one_percent_co2
                or forcing is not GCMPattern.ukesm
                or factorial is not Factorial.baseline):
            raise NotImplementedError(
                f"{MODEL}: only (one_percent_co2, ukesm, baseline) paths are seeded; "
                f"got ({experiment.name}, {forcing.name}, {factorial.name})."
            )
        if simulation not in _PREFIX:
            raise KeyError(f"{MODEL}: no '{simulation.name}' run "
                           f"(have {[s.name for s in _PREFIX]})")
        return str(_OUTPUT / (_PREFIX[simulation] + self._fname(variable)))

    def _years(self, ds: xr.Dataset):
        return np.floor(ds["time"].values).astype(int)

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._years(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²]."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, Factorial.baseline, "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
