"""VISIT-UT adapter.

Quirks (AGENTS.md §3): 0.5° grid, lat/lon, time `years since AD 0` (fractional)
so decode_times=False and floor. All files are monthly (`_mon_`), even stocks.
Computed spherical area (no land frac; README integral = Σ flux×area).

Naming (verified on the bucket): nested run dirs holding same-named files.
bgc/ctrl are bare (`VISIT-UT_BGC`, `VISIT-UT_CTRL`); cou/rad carry the GCM
(`VISIT-UT_<forcing>_COU`); the factorial is a trailing suffix. path() is a pure
transform — what exists is decided by read() opening the file.

DATA-QUALITY: `fFire` carries `units="kg C m-2 s-1"` but its values are ~1000×
too large — they are really `g C m-2 s-1` (the global total integrates to ~1078
Pg C/yr as-labeled, vs a physical ~1.08 Pg C/yr once divided by 1000; the spatial
pattern itself is correct). A g→kg label slip, flagged for Akihiko Ito. nbp was
validated against Ito's reference CSV and is genuinely kg C m-2 s-1, so this is
fFire-specific. Per the PLAN.md decision ("expect outputs to be perfect; it's up
to the user to debug bad files") the API still exposes it UNMODIFIED — read()
emits the file's declared units and warns on known-bad variables (see
_UNITS_NOTE); the caller applies the correction. Caller beware.
"""

from __future__ import annotations

import warnings

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "VISIT-UT"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

_FACTORIALS = {"baseline": "", "noBVOC": "_noBVOC", "noFire": "_noFire"}

# Known unit problems in the uploaded files: variable -> human note. Data is
# returned UNMODIFIED (PLAN.md), but read() emits each file's own `units` attr and
# warns on these so a caller can't silently integrate a mis-scaled field.
# Discovered by integrating to a global total and comparing to physical scale
# (nbp, gpp, … checked out; only fFire is off).
_UNITS_NOTE = {
    "fFire": "declared units 'kg C m-2 s-1' but values are ~1000x too large; "
    "they appear to be 'g C m-2 s-1' (global ~1078 Pg C/yr as-labeled "
    "vs physical ~1.08 Pg C/yr). g->kg label slip, flagged for A. Ito.",
}


def _bare_run(simulation, forcing) -> str:
    """The factorial-free run token (file prefix). The factorial is NOT here —
    it suffixes the dir and trails the cadence in the filename (see path())."""
    if simulation in (Simulation.cou, Simulation.rad):
        return f"VISIT-UT_{forcing.value}_{simulation.name.upper()}"
    return f"VISIT-UT_{simulation.name.upper()}"  # BGC, CTRL


class VISIT_UT(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # "years since AD 0" fractional -> floor
    FACTORIALS = _FACTORIALS

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        suf = self.FACTORIALS[factorial]  # "" | "_noBVOC" | "_noFire"
        bare = _bare_run(simulation, forcing)
        run = f"{bare}{suf}"  # dir carries the factorial
        fname = f"{bare}_{variable}_mon{suf}_05.nc"  # file: factorial AFTER cadence
        return str(_OUTPUT / "VISIT-UT" / run / fname)

    def _time(self, ds: xr.Dataset):
        # "years since AD 0" (fractional for monthly) -> datetime64
        return core.years_to_datetime(ds["time"].values)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        # Emit the file's OWN units attr (not an assumed value) onto the returned
        # array, and warn on any variable with a known unit problem so it can't be
        # integrated blindly. standardize() preserves attrs.
        file_units = ds[variable].attrs.get("units", "")
        da.attrs["units"] = file_units
        if variable in _UNITS_NOTE:
            warnings.warn(
                f"VISIT-UT {variable}: {_UNITS_NOTE[variable]} "
                f"(file declares units={file_units!r})",
                stacklevel=2,
            )
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²]."""
        ref = xr.open_dataset(
            self.path(
                Experiment.one_percent_co2,
                Simulation.bgc,
                GCMPattern.ukesm,
                "baseline",
                "cVeg",
            ),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
