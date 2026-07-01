"""BiomeE adapter.

Quirks (AGENTS.md §3): 0.5° grid, dims (lon, lat, time), datetime time, area =
provided `veg_area.nc` (vegetated m²), cVeg/etc use a -1e5 fill that must be
masked, first valid year 1851. UKESM-forced; bgc/cou submitted (no ctrl).

Naming (verified on the bucket): flat layout
`BiomeE_<forcing>_<sim>_<var>_<cad>_05.nc` (lowercase forcing + sim tokens).
path() is a pure transform — what exists is decided by read() opening the file.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment

MODEL = "BiomeE"
_OUTPUT = DATA_ROOT


class BiomeE(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True  # datetime time axis
    FACTORIALS = {"baseline": ""}  # only the bare run was submitted

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        cad = "yr" if core.is_annual(variable) else "mon"
        fname = f"BiomeE_{forcing.value}_{simulation.name}_{variable}_{cad}_05.nc"
        return str(
            _OUTPUT / Experiment.one_percent_co2.value / "output" / "BiomeE" / fname
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

    def _compute_weights(self) -> xr.DataArray:
        """Provided vegetated-area raster [m²] (BiomeE README recipe)."""
        a = xr.open_dataset(
            _OUTPUT / "1pctCO2" / "output" / "BiomeE" / "veg_area.nc"
        )["veg_area"]
        a = a.drop_vars("time", errors="ignore")
        return core.rename_latlon(a, self.LAT, self.LON).astype("float32")
