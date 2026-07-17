"""
CLM adapter.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "CLM"
_OUTPUT = DATA_ROOT


class CLM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # mixed "yr" / noleap "hours since 1850" axis, decoded by hand
    # The factorial picks the run set: hh (baseline) or flat, CLM's two uploads.
    # flat has only bgc/cou/rad in sub-dirs — its ctrl is loose at the model-dir
    # top, and we register only the sub-dir runs, so flat+ctrl has no path here.
    FACTORIALS = {Factorial.baseline.name: "hh", "flat": "flat"}

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        prefix = self.FACTORIALS[factorial]
        # cou/rad carry the GCM pattern; the constant-climate runs (bgc/ctrl) are
        # still labelled "ukesm" on disk, so that's the token for anything else.
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        token = forcing.lower() if gcm_forced else "ukesm"
        run_dir = f"{prefix}_{token}_{simulation}"
        fname = f"clm6_{prefix}_{token}_{simulation}_{variable}.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / run_dir / fname)

    def _time(self, ds: xr.Dataset):
        t = ds["time"]
        if t.attrs.get("units") == "yr":  # annual pools: a bare calendar-year axis
            return core.years_to_datetime(t.values)
        # monthly, contiguous from January 1850 — index it month-by-month rather
        # than unpick the noleap sub-month timestamps.
        months = np.arange(t.size).astype("timedelta64[M]")
        return np.datetime64("1850-01", "M") + months

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
        """Land area per cell [m²] from the shipped `area` (km²) and `landfrac`."""
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        weights = ref["area"] * 1e6 * ref["landfrac"]
        ref.close()
        return core.rename_latlon(weights, self.LAT, self.LON)
