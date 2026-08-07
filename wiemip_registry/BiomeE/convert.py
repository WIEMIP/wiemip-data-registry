"""BiomeE adapter.

Naming (verified on the bucket): flat layout
`BiomeE_<forcing>_<sim>_<var>_<cad>_05.nc` (lowercase forcing + sim tokens).
path() is a pure transform — what exists is decided by read() opening the file.

The constant-climate runs (bgc/ctrl) are labelled `ukesm` on disk even though the
protocol requires requesting them as `stable`, so their token is pinned — see
`_GCM_FORCED`.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "BiomeE"
_OUTPUT = DATA_ROOT

# Only cou/rad carry the requested GCM pattern; bgc and the fact_ runs are on disk
# as `ukesm` even though the protocol requires requesting them as `stable`.
_GCM_FORCED = ("cou", "rad")
_CONSTANT_CLIMATE_TOKEN = "ukesm"

# Baseline ctrl was re-uploaded as BiomeE_stable_ctrl_*, superseding BiomeE_ukesm_ctrl_*.
_STABLE_TOKEN = "stable"
_STABLE_TOKEN_SIMS = ("ctrl",)


class BiomeE(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True  # datetime time axis
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "noFire",
        Factorial.noNitrogen.name: "noNitrogen",
    }  # only the bare run was submitted

    def land_carbon_variables(self) -> list[str]:
        return ["cLitter", "cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        cad = "yr" if core.is_annual(variable) else "mon"
        is_fact = factorial != Factorial.baseline.name and factorial in self.FACTORIALS

        if simulation.split("_")[0] not in _GCM_FORCED:
            forcing = (
                _STABLE_TOKEN
                if not is_fact and simulation in _STABLE_TOKEN_SIMS
                else _CONSTANT_CLIMATE_TOKEN
            )

        if is_fact:
            fname = f"BiomeE_{forcing}_fact_{simulation}_{self.FACTORIALS[factorial]}_{variable}_{cad}_05.nc"
        else:
            fname = f"BiomeE_{forcing}_{simulation}_{variable}_{cad}_05.nc"

        return str(_OUTPUT / "1pctCO2" / "output" / "BiomeE" / fname)

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
        a = xr.open_dataset(_OUTPUT / "1pctCO2" / "output" / "BiomeE" / "veg_area.nc")[
            "veg_area"
        ]
        a = a.drop_vars("time", errors="ignore")
        return core.rename_latlon(a, self.LAT, self.LON).astype("float32")
