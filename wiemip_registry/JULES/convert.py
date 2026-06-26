"""JULES adapter.

Quirks (AGENTS.md §3): n96 grid, latitude/longitude, datetime + a `year` coord.
Area = `landfrac_n96.nc` `land` × spherical cell; `land` carries ~1e37 ocean
fill so mask values >1 -> 0. Only `cVeg` & `cSoil` were submitted. ctrl is `ctl`.

Naming (verified on the bucket): nested run dirs
`JULESwiemipV2_<sim>_<config>/` holding files
`JULESwiemipV2_<sim>_<var>_yr_<config>_n96.nc` (always annual). `<sim>` is bgc /
ctl / `<forcing>_cou`. The `<config>` string IS the factorial — every run carries
a Nitrogen/DynVeg/Permafrost/Fire combination; the README reference run
`Nitrogen_DynVeg_Permafrost_noFire` is our `baseline`. path() is a pure transform
— what exists is decided by read().
"""
from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "JULES"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"
_LANDFRAC = _OUTPUT / "JULES" / "landfrac_n96.nc"

# Factorial name -> the JULES config string baked into the run dir AND filename.
_FACTORIALS = {
    "baseline":             "Nitrogen_DynVeg_Permafrost_noFire",
    "noNitrogen":           "noNitrogen_DynVeg_Permafrost_noFire",
    "noDynVeg":             "Nitrogen_noDynVeg_Permafrost_noFire",
    "noPermafrostC":        "Nitrogen_DynVeg_noPermafrostC_noFire",
    "noPermafrostCN":       "Nitrogen_DynVeg_noPermafrostCN_noFire",
    "noPermafrostCNNinorg": "Nitrogen_DynVeg_noPermafrostCNNinorg_noFire",
    "addPermafrostC":       "Nitrogen_DynVeg_addPermafrostC_noFire",
    "addPermafrostCN":      "Nitrogen_DynVeg_addPermafrostCN_noFire",
    "addPermafrostCNNinorg": "Nitrogen_DynVeg_addPermafrostCNNinorg_noFire",
    "Fire0005":             "Nitrogen_DynVeg_Permafrost_Fire0005",
    "Fire0249":             "Nitrogen_DynVeg_Permafrost_Fire0249",
    "Fire0304":             "Nitrogen_DynVeg_Permafrost_Fire0304",
    "Fire0336":             "Nitrogen_DynVeg_Permafrost_Fire0336",
}


def _sim_tok(simulation, forcing) -> str:
    if simulation is Simulation.cou:
        return f"{forcing.value}_cou"
    if simulation is Simulation.rad:
        return f"{forcing.value}_rad"
    if simulation is Simulation.ctrl:
        return "ctl"
    return "bgc"


class JULES(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = _FACTORIALS

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        config = self.FACTORIALS[factorial]
        tok = _sim_tok(simulation, forcing)
        run = f"JULESwiemipV2_{tok}_{config}"
        fname = f"JULESwiemipV2_{tok}_{variable}_yr_{config}_n96.nc"   # always annual
        return str(_OUTPUT / "JULES" / run / fname)

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
                      GCMPattern.ukesm, "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        land = xr.open_dataset(_LANDFRAC)["land"]
        land = land.where(land <= 1.0, 0.0)
        return core.rename_latlon((cell * land).astype("float32"), self.LAT, self.LON)
