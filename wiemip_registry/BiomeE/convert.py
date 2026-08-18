"""BiomeE adapter.

Naming (verified on the bucket): flat layout
`BiomeE_<forcing>_<sim>_<var>_<cad>_05.nc` (lowercase forcing + sim tokens).
path() is a pure transform — what exists is decided by read() opening the file.

BiomeE's constant-climate runs (bgc/ctrl, incl. their fact_ variants) are `stable`
on disk — confirmed with the BiomeE team. Baseline ctrl was already re-uploaded as
`BiomeE_stable_ctrl_*`, superseding `BiomeE_ukesm_ctrl_*`. bgc is still `ukesm`-only
on disk as of 2026-08-17 pending their re-upload, so `stable` bgc paths raise at
read() until that lands — that's the correct signal, not a bug in this adapter.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "BiomeE"
_OUTPUT = DATA_ROOT


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
        """
        Unconfirmed. Assuming cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        cad = "yr" if core.is_annual(variable) else "mon"
        is_fact = factorial != Factorial.baseline.name and factorial in self.FACTORIALS

        # cou/rad carry the GCM pattern; bgc/ctrl (and their fact_ variants) are
        # constant-climate and labelled "stable" on disk. Confirmed with BiomeE team
        # on 2026-08-17.
        if simulation.split("_")[0] not in ("cou", "rad"):
            forcing = "stable"

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
