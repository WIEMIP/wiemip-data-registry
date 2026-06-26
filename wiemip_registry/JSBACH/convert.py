"""JSBACH adapter.

Quirks (AGENTS.md §3): 1° grid, lat/lon, datetime time (epoch 1847). `fFire`≈0
(fire effectively off in this run).

Naming (verified on the bucket): nested run dirs holding same-named files.
bgc/ctrl carry a `stable_` tag (`JSBACH_stable_<sim>`), cou carries the GCM
(`JSBACH_<forcing>_cou`); the factorial is a trailing suffix. path() is a pure
transform — what exists is decided by read() opening the file.
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "JSBACH"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_FACTORIALS = {"baseline": "", "ndep": "_ndep", "noNitrogen": "_noNitrogen"}


def _run(simulation, forcing, suf: str) -> str:
    """The JSBACH run token = dir name = file prefix."""
    if simulation in (Simulation.cou, Simulation.rad):
        return f"JSBACH_{forcing.value}_{simulation.name}{suf}"
    return f"JSBACH_stable_{simulation.name}{suf}"          # bgc, ctrl


class JSBACH(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = _FACTORIALS

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        run = _run(simulation, forcing, self.FACTORIALS[factorial])
        cad = "yr" if core.kind_of(variable) == "stock" else "mon"
        return str(_OUTPUT / "JSBACH" / run / f"{run}_{variable}_{cad}_1.nc")

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
                      GCMPattern.ukesm, "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
