"""CLASSIC adapter.

Quirks (AGENTS.md §3): 1° grid, dims latitude/longitude, datetime time, units
written `kg C m$^{-2}$`. Global integral needs land fraction (per V. Arora):
area × sftlf × quantity. sftlf is static across runs — load once from BGC.
Which runs/variables resolve is decided by file existence (WIEAdapter.available).
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "CLASSIC"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_PREFIX = {
    Simulation.bgc:  "CLASSIC/CLASSIC_UKESM_1pctCO2-BGC/CLASSIC_UKESM_1pctCO2-BGC_",
    Simulation.cou:  "CLASSIC/CLASSIC_UKESM_1pctCO2-COU/CLASSIC_UKESM_1pctCO2-COU_",
    Simulation.ctrl: "CLASSIC/CLASSIC_stable_piControl/CLASSIC_stable_",
}
_SFTLF = (_OUTPUT / "CLASSIC" / "CLASSIC_UKESM_1pctCO2-BGC"
          / "CLASSIC_UKESM_1pctCO2-BGC_land_fraction_ann_1deg.nc")


class CLASSIC(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True

    def _fname(self, variable: str) -> str:
        cad = "ann" if core.kind_of(variable) == "stock" else "mon"
        return f"{variable}_{cad}_1deg.nc"

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
        """Spherical cell area × static land fraction (sftlf)."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, Factorial.baseline, "cVeg"),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        sftlf = xr.open_dataset(_SFTLF)["sftlf"]
        return core.rename_latlon((cell * sftlf).astype("float32"), self.LAT, self.LON)
