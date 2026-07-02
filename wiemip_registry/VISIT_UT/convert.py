"""VISIT-UT adapter."""

from __future__ import annotations

import warnings

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "VISIT-UT"
_OUTPUT = DATA_ROOT

_FACTORIALS = {
    Factorial.baseline.name: "",
    Factorial.noBVOC.name: "_noBVOC",
    Factorial.noFire.name: "_noFire",
}

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
    if simulation in ("cou", "rad"):
        return f"VISIT-UT_{forcing}_{simulation.upper()}"
    return f"VISIT-UT_{simulation.upper()}"  # BGC, CTRL


class VISIT_UT(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # "years since AD 0" fractional -> floor
    FACTORIALS = _FACTORIALS

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        suf = self.FACTORIALS[factorial]  # "" | "_noBVOC" | "_noFire"
        bare = _bare_run(simulation, forcing)
        run = f"{bare}{suf}"  # dir carries the factorial
        fname = f"{bare}_{variable}_mon{suf}_05.nc"  # file: factorial AFTER cadence
        return str(_OUTPUT / "1pctCO2" / "output" / "VISIT-UT" / run / fname)

    def overshoot_path(self, simulation, forcing, variable) -> str:
        prefix = f"VISIT-UT_{forcing.lower()}_{simulation.lower()}"
        fname = f"{prefix}_{variable}_mon_05.nc"
        return str(_OUTPUT / "overshoot" / "output" / "VISIT-UT" / prefix / fname)

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
                "1pctCO2",
                "bgc",
                "ukesm",
                "baseline",
                "cVeg",
            ),
            decode_times=self.DECODE,
        )
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)
