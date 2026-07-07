"""LPJ-EOSIM adapter.

Discovered on the bucket (`/mnt/wiemip/1pctCO2/output/LPJ-EOSIM/`):

* Nested run sub-dirs `LPJ_EOSIM_<second>_<sim>[_noFire]/` — only `bgc`, `ctrl`, and
  the UKESM-coupled `cou` were uploaded (no `rad`, no `_ndep`). Each run ships a bare
  baseline and a `noFire` factorial variant; no other sensitivity runs so far. As of
  this writing only `cVeg` is present in every run.
* Files: `LPJ_EOSIM_<second>_<sim>_<var>_<cad>[_noFire]_05.nc`. The `<second>` token is
  the GCM name for the coupled run (`ukesm`) and the literal `stable` for the
  not-GCM-forced runs (`bgc`, `ctrl`). The model dir on disk is hyphenated
  (`LPJ-EOSIM`); the run sub-dir and file prefix are underscored (`LPJ_EOSIM`).
* The `noFire` factorial is a post-cadence `_noFire` suffix carried by BOTH the run
  sub-dir name and the filename (after the cadence token, before the `05` grid token).
* 0.5° grid (`05` token), coords `latitude`/`longitude` (both ascending). Internal
  netCDF variable names are the CMIP short-names already, so no renaming.
* Time is CF `days since 1850-01-01` on a **gregorian** calendar (end-of-year stamps,
  1850..2000), so xarray decodes it straight to datetime64 — decode_times=True. Annual
  stocks (cVeg) use the `yr` token, everything else `mon`.
* No area / land-fraction raster is shipped, and ocean cells are NaN in the data, so
  the area weight is the computed spherical cell area — the data's NaN mask is the land
  mask (identical recipe to DLEM/TEM/VISIT-UT).

path() is a pure token→string transform; what exists is decided by read().
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPJ-EOSIM"  # model dir on disk (hyphenated)
_PREFIX = "LPJ_EOSIM"  # run sub-dir and file prefix (underscored)
_OUTPUT = DATA_ROOT


class LPJ_EOSIM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True  # gregorian "days since 1850-01-01" -> datetime64 directly
    # Bare baseline + a fire-off sensitivity run. The factorial is a post-cadence
    # `_noFire` suffix carried by both the run sub-dir name and the filename.
    FACTORIALS = {Factorial.baseline.name: "", Factorial.noFire.name: "_noFire"}

    def _factorial_suffix(self, factorial: str) -> str:
        # Pure transform (see registry contract): a factorial this model didn't upload
        # still spells a path — a post-cadence `_<factorial>` suffix — and simply fails
        # at read(). baseline maps to the empty token (the bare run).
        return self.FACTORIALS.get(factorial, f"_{factorial}")

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        # bgc/ctrl are not GCM-forced ("stable"); cou/rad carry the GCM name.
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        second = forcing.lower() if gcm_forced else "stable"
        cad = "yr" if core.is_annual(variable) else "mon"
        suffix = self._factorial_suffix(factorial)
        run_dir = f"{_PREFIX}_{second}_{simulation}{suffix}"
        fname = f"{_PREFIX}_{second}_{simulation}_{variable}_{cad}{suffix}_05.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / run_dir / fname)

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
        """Computed spherical cell area [m²]; ocean cells drop out via the data's
        NaN mask (no land-fraction raster shipped)."""
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
