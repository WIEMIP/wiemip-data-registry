"""TEM (TEM-MDM) adapter.

Discovered on the bucket (`/mnt/wiemip/1pctCO2/output/TEM/`):

* Nested run sub-dirs `BGC/`, `COU/`, `CTRL/` — only these three runs were
  uploaded (no `rad`, no `_ndep`, no sensitivity/factorial runs). Baseline only.
* Files: `TEM-MDM_<second>_<sim>_<var>_<cad>_05.nc`, where the `<second>` token is
  the GCM name for the coupled run (`ukesm`) and the literal `stable` for the
  not-GCM-forced runs (`bgc`, `ctrl`). File prefix is `TEM-MDM`; the on-disk model
  dir is `TEM`.
* 0.5° grid (`05` token), coords `latitude`/`longitude` (lat ascending). Internal
  netCDF variable names are the CMIP short-names already, so no renaming.
* Time is CF `days since 1850-01-01` on a **noleap** calendar → decode_times=False
  and convert by hand (`_time`). Annual stocks (cVeg/cSoil) use the `yr` token,
  everything else `mon`.
* No area / land-fraction raster is shipped, and ocean cells are NaN in the data,
  so the area weight is the computed spherical cell area — the data's NaN mask is
  the land mask (identical recipe to DLEM/VISIT-UT).

path() is a pure token→string transform; what exists is decided by read().
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "TEM-MDM"
_OUTPUT = DATA_ROOT

# noleap calendar: 365-day years with fixed month lengths. Cumulative day-of-year
# at the start of each month (Jan..Dec), used to turn "days since 1850" into (year,
# month) without leap-day drift.
_MONTH_START = np.array([0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334])


class TEM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = False  # noleap "days since 1850-01-01" -> decode by hand
    # Only the bare baseline runs were uploaded — no sensitivity factorials.
    FACTORIALS = {Factorial.baseline.name: ""}

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        # bgc/ctrl are not GCM-forced ("stable"); cou/rad carry the GCM name.
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        second = forcing.lower() if gcm_forced else "stable"
        cad = "yr" if core.is_annual(variable) else "mon"
        run_dir = simulation.upper()  # BGC / COU / CTRL
        fname = f"TEM-MDM_{second}_{simulation}_{variable}_{cad}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / "TEM" / run_dir / fname)

    def _time(self, ds: xr.Dataset):
        """noleap `days since 1850-01-01` -> datetime64[M], preserving cadence."""
        days = np.asarray(ds["time"].values, dtype="float64")
        year = 1850 + np.floor(days / 365.0).astype("int64")
        doy = np.mod(days, 365.0)
        month = np.searchsorted(_MONTH_START, doy, side="right") - 1  # 0..11
        total_months = (year - 1970) * 12 + month
        return np.datetime64("1970-01", "M") + total_months.astype("timedelta64[M]")

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
        """Computed spherical cell area [m²]; ocean cells drop out via the data's
        NaN mask (no land-fraction raster shipped)."""
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
