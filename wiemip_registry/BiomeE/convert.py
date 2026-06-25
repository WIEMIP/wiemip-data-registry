"""BiomeE adapter.

Quirks (AGENTS.md §3): 0.5° grid, dims (lon, lat, time), datetime time, area =
provided `veg_area.nc` (vegetated m²), cVeg/etc use a -1e5 fill that must be
masked, first valid year 1851. UKESM-forced. Which simulations/variables resolve
is decided by file existence (see WIEAdapter.available), not a hardcoded list.
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "BiomeE"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

# Baseline (no-factorial) run-path prefix per simulation; cou = UKESM-forced.
_PREFIX = {
    Simulation.bgc: "BiomeE/BiomeE_ukesm_bgc_",
    Simulation.cou: "BiomeE/BiomeE_ukesm_cou_",
    Simulation.ctrl: "BiomeE/BiomeE_ukesm_ctrl_",
}


class BiomeE(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True                       # datetime time axis

    def _fname(self, variable: str) -> str:
        cad = "yr" if core.kind_of(variable) == "stock" else "mon"
        return f"{variable}_{cad}_05.nc"

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        # TODO: only the one_percent_co2 / ukesm / baseline corner is constructible.
        # gfdl/ipsl forcings and factorial runs need their own path patterns.
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
        return ds["time"].dt.year.values

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._years(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Provided vegetated-area raster [m²] (BiomeE README recipe)."""
        a = xr.open_dataset(_OUTPUT / "BiomeE" / "veg_area.nc")["veg_area"]
        a = a.drop_vars("time", errors="ignore")
        return core.rename_latlon(a, self.LAT, self.LON).astype("float32")
