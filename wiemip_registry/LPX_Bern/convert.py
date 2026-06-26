"""LPX-Bern adapter.

Quirks (AGENTS.md §3): 1° grid, latitude/longitude, numeric `years`/`year`
time so decode_times=False and floor to integer year. Area = provided
`gridcell_area.nc` (`area`, land-only). High-fire model (~15-23 Pg C/yr fire —
real, via their own recipe), also ships `fFireCveg`. Flat layout: run encoded
in the filename prefix. Which runs/variables resolve is decided by file existence.
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "LPX-Bern"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_PREFIX = {
    Simulation.bgc:  "LPX-Bern/LPX-Bern_bgc_",
    Simulation.cou:  "LPX-Bern/LPX-Bern_cou_UKESM_",
    Simulation.ctrl: "LPX-Bern/LPX-Bern_ctrl_",
}
_AREA = _OUTPUT / "LPX-Bern" / "gridcell_area.nc"


class LPX_Bern(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = False                      # numeric year axis -> floor

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
        # numeric calendar years (fractional for monthly) -> datetime64
        return core.years_to_datetime(ds["time"].values)

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Provided land-only grid-cell area raster [m²] (LPX-Bern README)."""
        a = xr.open_dataset(_AREA)["area"]
        return core.rename_latlon(a.astype("float32"), self.LAT, self.LON)
