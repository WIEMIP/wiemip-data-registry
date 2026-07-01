"""LPX-Bern adapter.

Quirks (AGENTS.md §3): 1° grid, latitude/longitude, numeric `years`/`year`
time so decode_times=False and floor to integer year. Area = provided
`gridcell_area.nc` (`area`, land-only). High-fire model (~15-23 Pg C/yr fire —
real, via their own recipe), also ships `fFireCveg`.

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
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "LPX-Bern"
_OUTPUT = DATA_ROOT

# canonical bucket -> (prefix before sim, suffix after sim) in LPX's own spelling.
_FACTORIALS = {
    "baseline": ("", ""),
    "noFire": ("nofire", ""),
    "noPermafrost": ("nopermafrost", ""),
    "noPermafrost_noFire": ("nopermafrost_nofire", ""),
    "ndep": ("", "ndep"),
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
        sim = simulation.name  # bgc/cou/rad/ctrl
        pre_tok, suf_tok = self.FACTORIALS[factorial]
        pre = f"{pre_tok}_" if pre_tok else ""
        suf = f"_{suf_tok}" if suf_tok else ""
        gcm = (
            f"_{forcing.value.upper()}"
            if simulation in (Simulation.cou, Simulation.rad)
            else ""
        )
        cad = "yr" if core.is_annual(variable) else "mon"
        variable = self._get_variable(variable)
        fname = f"LPX-Bern_{pre}{sim}{suf}{gcm}_{variable}_{cad}_1.nc"
        return str(
            _OUTPUT / Experiment.one_percent_co2.value / "output" / "LPX-Bern" / fname
        )

    def overshoot_path(self, simulation, forcing, variable) -> str:
        """
        Note: LPX-Bern uploaded files prefixed with "overshoot" which are bitwise
        identical to the ones prefixed with "ukesm". These won't be coverered by this naming
        convention but they're duplicates so it's OK.
        """
        sim = simulation.name  #
        gcm = forcing.value.lower()
        cad = "yr" if core.is_annual(variable) else "mon"
        variable = self._get_variable(variable)
        fname = f"LPX-Bern_{gcm}_{sim}_{variable}_{cad}_1.nc"
        return str(_OUTPUT / Experiment.overshoot.value / "output" / "LPX-Bern" / fname)

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
