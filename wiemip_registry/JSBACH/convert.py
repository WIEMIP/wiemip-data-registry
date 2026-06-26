"""JSBACH adapter.

Quirks (AGENTS.md §3): 1° grid, lat/lon, datetime time (epoch 1847). `fFire`≈0
(fire effectively off in this run). Run dirs hold two filename prefixes
(`stable_bgc_` vs `stable_1pctCO2_`) — the seeded prefix picks the exp-tagged one.
Which runs/variables resolve is decided by file existence (WIEAdapter.available).
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "JSBACH"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_PREFIX = {
    Simulation.bgc:  "JSBACH/JSBACH_stable_bgc/JSBACH_stable_bgc_",
    Simulation.cou:  "JSBACH/JSBACH_ukesm_cou/JSBACH_ukesm_cou_",
    Simulation.ctrl: "JSBACH/JSBACH_stable_ctrl/JSBACH_stable_ctrl_",
}


class JSBACH(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True

    def _fname(self, variable: str) -> str:
        cad = "yr" if core.kind_of(variable) == "stock" else "mon"
        return f"{variable}_{cad}_1.nc"

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

    def _time(self, ds: xr.Dataset):
        return ds["time"].values        # already datetime64 (decode_times=True)

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²] (ocean -> NaN on the data)."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, Factorial.baseline, "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
