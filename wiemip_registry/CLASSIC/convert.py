"""CLASSIC adapter.

Quirks (AGENTS.md §3): 1° grid, dims latitude/longitude, datetime time, units
written `kg C m$^{-2}$`. Global integral needs land fraction (per V. Arora):
area × sftlf × quantity. sftlf is static across runs — load once from BGC.

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
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "CLASSIC"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

# How CLASSIC spells each simulation in the `1pctCO2-<SIM>` run token (ctrl is
# special-cased in path()).
_SIM = {Simulation.bgc: "BGC", Simulation.cou: "COU", Simulation.rad: "RAD"}

# Per-model factorial vocabulary -> the exact suffix CLASSIC appends to the run
# token (verified against the bucket dir names). baseline = no suffix.
_FACTORIALS = {
    "baseline": "", "ndep": "-Ndep", "noFire": "_noFire", "noNitrogen": "_noNitrogen",
    "ndep_noFire": "-Ndep_noFire", "noFire_noNitrogen": "_noFire_noNitrogen",
}
_SFTLF = (_OUTPUT / "CLASSIC" / "CLASSIC_UKESM_1pctCO2-BGC"
          / "CLASSIC_UKESM_1pctCO2-BGC_land_fraction_ann_1deg.nc")


class CLASSIC(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = _FACTORIALS

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
        suf = self.FACTORIALS[factorial]
        cad = "ann" if core.kind_of(variable) == "stock" else "mon"
        if simulation is Simulation.ctrl:
            run = f"CLASSIC_stable_piControl{suf}"
            base = f"CLASSIC_stable{suf}"
        else:
            run = f"CLASSIC_{forcing.value.upper()}_1pctCO2-{_SIM[simulation]}{suf}"
            base = run
        return str(_OUTPUT / "CLASSIC" / run / f"{base}_{variable}_{cad}_1deg.nc")

    def _time(self, ds: xr.Dataset):
        return ds["time"].values        # already datetime64 (decode_times=True)

    def read(self, experiment, simulation, forcing, factorial, variable) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    def _compute_weights(self) -> xr.DataArray:
        """Spherical cell area × static land fraction (sftlf)."""
        ref = xr.open_dataset(
            self.path(Experiment.one_percent_co2, Simulation.bgc,
                      GCMPattern.ukesm, "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        sftlf = xr.open_dataset(_SFTLF)["sftlf"]
        return core.rename_latlon((cell * sftlf).astype("float32"), self.LAT, self.LON)
