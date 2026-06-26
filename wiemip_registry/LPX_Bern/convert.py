"""LPX-Bern adapter.

Quirks (AGENTS.md §3): 1° grid, latitude/longitude, numeric `years`/`year`
time so decode_times=False and floor to integer year. Area = provided
`gridcell_area.nc` (`area`, land-only). High-fire model (~15-23 Pg C/yr fire —
real, via their own recipe), also ships `fFireCveg`.

Naming (verified on the bucket): flat layout, run encoded in the filename:
`LPX-Bern_[<factprefix>_]<sim>[_ndep][_<FORCING>]_<var>_<cad>_1.nc`. The
nofire / nopermafrost sensitivity runs sit as a PREFIX before the sim token;
`ndep` is a SUFFIX after it; the GCM forcing (cou/rad only) trails, uppercase.
path() is a pure transform — what exists is decided by read().
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "LPX-Bern"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

# Factorials whose token is a PREFIX before the simulation (the value is unused;
# the prefix string is the name itself). `ndep` is handled as a suffix below.
_PREFIX_FACTORIALS = {"nofire", "nopermafrost", "nopermafrost_nofire"}
_FACTORIALS = {
    "baseline": "",
    "nofire": "",
    "nopermafrost": "",
    "nopermafrost_nofire": "",
    "ndep": "_ndep",
}
_AREA = _OUTPUT / "LPX-Bern" / "gridcell_area.nc"


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

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        sim = simulation.name  # bgc/cou/rad/ctrl
        pre = f"{factorial}_" if factorial in _PREFIX_FACTORIALS else ""
        ndep = "_ndep" if factorial == "ndep" else ""
        gcm = (
            f"_{forcing.value.upper()}"
            if simulation in (Simulation.cou, Simulation.rad)
            else ""
        )
        cad = "yr" if core.is_annual(variable) else "mon"
        variable = self._get_variable(variable)
        fname = f"LPX-Bern_{pre}{sim}{ndep}{gcm}_{variable}_{cad}_1.nc"
        return str(_OUTPUT / "LPX-Bern" / fname)

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
