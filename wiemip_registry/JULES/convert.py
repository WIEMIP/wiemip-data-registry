"""JULES adapter.

Quirks (AGENTS.md §3): n96 grid, latitude/longitude, datetime + a `year` coord.
Area = `landfrac_n96.nc` `land` × spherical cell; `land` carries ~1e37 ocean
fill so mask values >1 -> 0. Only `cVeg` & `cSoil` were submitted (the others
are simply never found by the existence check, not hardcoded out). ctrl is `ctl`.
Every JULES config carries `Nitrogen_DynVeg_Permafrost_noFire` — their README
designates that as the reference run, so we treat it as JULES's `baseline`.
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern, Factorial

MODEL = "JULES"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

# The reference-config suffix baked into every JULES filename / run dir.
_CONFIG = "Nitrogen_DynVeg_Permafrost_noFire"
_PREFIX = {
    Simulation.bgc:  f"JULES/JULESwiemipV2_bgc_{_CONFIG}/JULESwiemipV2_bgc_",
    Simulation.cou:  f"JULES/JULESwiemipV2_ukesm_cou_{_CONFIG}/JULESwiemipV2_ukesm_cou_",
    Simulation.ctrl: f"JULES/JULESwiemipV2_ctl_{_CONFIG}/JULESwiemipV2_ctl_",
}
_LANDFRAC = _OUTPUT / "JULES" / "landfrac_n96.nc"


class JULES(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True

    def _fname(self, variable: str) -> str:
        return f"{variable}_yr_{_CONFIG}_n96.nc"     # always annual

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        if (experiment is not Experiment.one_percent_co2
                or forcing is not GCMPattern.ukesm
                or factorial is not Factorial.baseline):
            raise NotImplementedError(
                f"{MODEL}: only (one_percent_co2, ukesm, baseline) paths are seeded; "
                f"got ({experiment.name}, {forcing.name}, {factorial.name}). "
                f"'baseline' maps to the {_CONFIG} reference config."
            )
        if simulation not in _PREFIX:
            raise KeyError(f"{MODEL}: no '{simulation.name}' run "
                           f"(have {[s.name for s in _PREFIX]})")
        return str(_OUTPUT / (_PREFIX[simulation] + self._fname(variable)))

    def _time(self, ds: xr.Dataset):
        return ds["time"].values        # datetime64 (decode_times=True); ignore the `year` coord

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Spherical cell area × land fraction (ocean fill ~1e37 -> 0)."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, Factorial.baseline, "cVeg"),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        land = xr.open_dataset(_LANDFRAC)["land"]
        land = land.where(land <= 1.0, 0.0)
        return core.rename_latlon((cell * land).astype("float32"), self.LAT, self.LON)
