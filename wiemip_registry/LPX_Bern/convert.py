"""LPX-Bern adapter.

Naming (verified on the bucket): flat layout, run encoded in the filename:
`LPX-Bern_[<factprefix>_]<sim>[_ndep][_<FORCING>]_<var>_<cad>_1.nc`. The fire-off /
permafrost-off sensitivity runs sit as a PREFIX (`nofire`, `nopermafrost`,
`nopermafrost_nofire`) before the sim token; `ndep` is a SUFFIX after it; the GCM
forcing (cou/rad only) trails, uppercase. The FACTORIALS dict maps each canonical
bucket to that (prefix, suffix) token pair — the lowercase spellings are LPX's own,
not the bucket names. path() is a pure transform — what exists is decided by read().
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "LPX-Bern"
_OUTPUT = DATA_ROOT

# canonical bucket -> (prefix before sim, suffix after sim) in LPX's own spelling.
_FACTORIALS = {
    Factorial.baseline.name: ("", ""),
    Factorial.noFire.name: ("nofire", ""),
    Factorial.noPermafrost.name: ("nopermafrost", ""),
    Factorial.noFire_noPermafrost.name: ("nopermafrost_nofire", ""),
}
_AREA = _OUTPUT / "1pctCO2" / "output" / "LPX-Bern" / "gridcell_area.nc"


class LPX_Bern(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = False  # numeric year axis -> floor
    FACTORIALS = _FACTORIALS
    """
    Note: LPX-Bern uploaded nSoil, which has the same effective definition
    as nOrgSoil. nSoil was deprecated in the variable request after upload.
    By default, we'll skip nSoil.
    """

    wiemip_to_lpx_bern_variable_mapping = {
        "fFireLitter": "fFireCLitter",
        "nOrgSoilpft": "nSoilpft",
    }

    def _get_variable(self, wiemip_variable: str) -> str:
        if wiemip_variable in self.wiemip_to_lpx_bern_variable_mapping:
            return self.wiemip_to_lpx_bern_variable_mapping[wiemip_variable]
        return wiemip_variable

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        sim = simulation  # bgc/cou/rad/ctrl (+ _ndep simulation variants)
        pre_tok, suf_tok = self.FACTORIALS[factorial]
        pre = f"{pre_tok}_" if pre_tok else ""
        suf = f"_{suf_tok}" if suf_tok else ""
        # ndep is a simulation, so `sim` already carries `_ndep` (it lands before the
        # GCM tag in the filename); the GCM keys on the BASE sim (cou/rad are forced).
        gcm = (
            f"_{forcing.upper()}" if simulation.split("_")[0] in ("cou", "rad") else ""
        )
        cad = "yr" if core.is_annual(variable) else "mon"
        variable = self._get_variable(variable)
        fname = f"LPX-Bern_{pre}{sim}{suf}{gcm}_{variable}_{cad}_1.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / "LPX-Bern" / fname)

    def overshoot_path(self, simulation, forcing, variable) -> str:
        """
        Note: LPX-Bern uploaded files prefixed with "overshoot" which are bitwise
        identical to the ones prefixed with "ukesm". These won't be coverred by this naming
        convention but they're duplicates so it's OK.
        """
        sim = simulation  #
        gcm = forcing.lower()
        cad = "yr" if core.is_annual(variable) else "mon"
        variable = self._get_variable(variable)
        fname = f"LPX-Bern_{gcm}_{sim}_{variable}_{cad}_1.nc"
        return str(_OUTPUT / "overshoot" / "output" / "LPX-Bern" / fname)

    def _time(self, ds: xr.Dataset):
        # numeric calendar years (fractional for monthly) -> datetime64
        return core.years_to_datetime(ds["time"].values)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(variable)])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Provided land-only grid-cell area raster [m²] (LPX-Bern README)."""
        a = xr.open_dataset(_AREA)["area"]
        return core.rename_latlon(a.astype("float32"), self.LAT, self.LON)
