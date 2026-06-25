"""DLEM adapter.

Quirks (AGENTS.md §3): 0.5° grid, lat truncated to 354 rows, time is
`years since 1850` (yr) / `months since 1850` (mon) so decode_times=False.
No `fFire`. `nbp` is 0 in 1850, nonzero later. Baseline BGC dir is tagged
`_ndep` but the *filename* carries no suffix (so it's still the baseline run).
Which runs/variables resolve is decided by file existence (no `fFire` is simply
never found on the bucket — not a hardcoded exclusion).
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "DLEM"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_PREFIX = {
    Simulation.bgc:  "DLEM/1pctCO2_BGC_ndep/DLEM_bgc_",
    Simulation.cou:  "DLEM/1pctCO2_COU_UKESM_ndep/DLEM_ukesm_cou_",
    Simulation.ctrl: "DLEM/1pctCO2_CTRL/DLEM_ctrl_",
}


class DLEM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False                      # numeric "years/months since 1850"

    def _fname(self, variable: str) -> str:
        cad = "yr" if core.kind_of(variable) == "stock" else "mon"
        return f"{variable}_{cad}_05.nc"

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
        tu = ds["time"].attrs.get("units", "")
        tv = ds["time"].values
        return (1850 + tv // 12).astype(int) if "months since" in tu else (1850 + tv).astype(int)

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._years(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²] (ocean cells masked via fills on the data)."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, Factorial.baseline, "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
