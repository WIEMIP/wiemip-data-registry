"""CLASSIC adapter.

Naming (verified on the bucket): nested run dirs
`CLASSIC_<FORCING>_1pctCO2-<SIM><factorial>/` holding files
`<dir>_<var>_<cad>_1deg.nc`; ctrl is special-cased to `CLASSIC_stable_piControl…`
with a `CLASSIC_stable…` file prefix. Only UKESM was submitted, so the forcing
token is honored (ipsl/gfdl simply won't resolve at read()). path() is a pure
transform — what exists is decided by read() opening the file.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "CLASSIC"
_OUTPUT = DATA_ROOT

_SIM = {
    "bgc": "BGC",
    "cou": "COU",
    "rad": "RAD",
    "rad_ndep": "RAD-Ndep",
    "cou_ndep": "COU-Ndep",
    "bgc_ndep": "BGC-Ndep",
    "ctrl_ndep": "CTRL-Ndep",
}

_FACTORIALS = {
    Factorial.baseline.name: ("", ""),
    Factorial.noFire.name: ("", "_noFire"),
    Factorial.noNitrogen.name: ("", "_noNitrogen"),
    Factorial.noFire_noNitrogen.name: ("", "_noFire_noNitrogen"),
}
_SFTLF = (
    _OUTPUT
    / "1pctCO2"
    / "output"
    / "CLASSIC"
    / "CLASSIC_UKESM_1pctCO2-BGC"
    / "CLASSIC_UKESM_1pctCO2-BGC_land_fraction_ann_1deg.nc"
)


class CLASSIC(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = _FACTORIALS

    # Per-PFT carbon that CLASSIC writes monthly even though the bulk-grid pools
    # are annual (model-specific cadence override of const.ANNUAL).
    MONTHLY = {"cVegpft"}
    wiemip_to_classic_variable_mapping = {
        "fCH4Fire": "fCh4Fire",
        "fN2OFire": "fN2oFire",
        "soilR": "soilr",
        "wetCH4": "wetch4_spec",
        # NOTE: Assumed that CH4 == wet CH4 here!!!
        "ch4": "wetch4_spec",
    }

    def _get_variable(self, wiemip_variable: str) -> str:
        if wiemip_variable in self.wiemip_to_classic_variable_mapping:
            return self.wiemip_to_classic_variable_mapping[wiemip_variable]
        return wiemip_variable

    def overshoot_path(self, simulation, forcing, variable) -> str:
        return "null"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        ndep, post = self.FACTORIALS[factorial]
        cad = (
            "mon"
            if variable in self.MONTHLY
            else ("ann" if core.is_annual(variable) else "mon")
        )
        if simulation == "ctrl":  # ctrl has no ndep variant
            run = f"CLASSIC_stable_piControl{post}"
            prefix = "CLASSIC_stable"
        else:
            stem = f"CLASSIC_{forcing.upper()}_1pctCO2-{_SIM[simulation]}{ndep}"
            run = f"{stem}{post}"  # dir carries ndep + post
            prefix = stem  # file prefix carries ndep only
        variable = self._get_variable(wiemip_variable=variable)
        z = str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "CLASSIC"
            / run
            / f"{prefix}_{variable}_{cad}{post}_1deg.nc"
        )
        return z

    def _time(self, ds: xr.Dataset):
        return ds["time"].values  # already datetime64 (decode_times=True)

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
        """Spherical cell area × static land fraction (sftlf)."""
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
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        sftlf = xr.open_dataset(_SFTLF)["sftlf"]
        return core.rename_latlon((cell * sftlf).astype("float32"), self.LAT, self.LON)
