"""DLEM adapter.

Naming (verified on the bucket): nested run dirs `1pctCO2_<SIM>[_<FORCING>][_ndep]/`
holding files `DLEM_[<forcing>_]<sim>_<var>_<cad>_05.nc`. DLEM's reference run is
the `_ndep` dir (baseline has ndep in the dir name but the filename has no
suffix) for bgc/cou/rad; ctrl is the bare `1pctCO2_CTRL`. The
ndep-vs-not split is genuinely model-specific, so `baseline` reproduces that
curated mapping and other DLEM factorials are left for later. path() is a pure
transform — what exists is decided by read().
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial, OnePctSimulation

MODEL = "DLEM"
_OUTPUT = DATA_ROOT


class DLEM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # numeric "years/months since 1850"
    # baseline = the reference `_ndep` dirs; noNdep = the plain
    # `1pctCO2_<SIM>` dirs whose files carry a `_noNdep` token.
    # no factorials uploaded as far as I know
    FACTORIALS = {Factorial.baseline.name: ""}

    wiemip_to_dlem_variable_mapping = {
        "fFireLitter": "fFireCLitter",
        "nOrgSoilpft": "nSoilpft",
    }

    def _get_variable(self, wiemip_variable: str) -> str:
        if wiemip_variable in self.wiemip_to_dlem_variable_mapping:
            return self.wiemip_to_dlem_variable_mapping[wiemip_variable]
        return wiemip_variable

    def one_pct_path(
        self, simulation: str, forcing: str, factorial: str, variable: str
    ) -> str:
        sim = simulation  # bgc/cou/rad/ctrl/ctrl-ndep etc
        cad = "yr" if core.is_annual(variable) else "mon"
        gcm_dir = (
            f"_{forcing.upper()}" if simulation.split("_")[0] in ("cou", "rad") else ""
        )
        gcm_f = f"{forcing}_" if simulation.split("_")[0] in ("cou", "rad") else ""

        if simulation == "ctrl":
            run, fpref = "1pctCO2_CTRL", "DLEM_ctrl"  # ctrl has no ndep variant
        elif simulation in (
            OnePctSimulation.cou.name,
            OnePctSimulation.rad.name,
            OnePctSimulation.bgc.name,
        ):
            # no ndep == baseline one percent run
            run = f"1pctCO2_{sim.split('_')[0].upper()}{gcm_dir}"
            fpref = f"DLEM_{gcm_f}{sim.split('_')[0]}_noNdep"
        elif simulation in (
            OnePctSimulation.cou_ndep.name,
            OnePctSimulation.rad_ndep.name,
            OnePctSimulation.bgc_ndep.name,
        ):  # the transient nitrogen deposition run
            run = f"1pctCO2_{sim.split('_')[0].upper()}{gcm_dir}_ndep"
            fpref = f"DLEM_{gcm_f}{sim.split('_')[0]}"
        else:
            # not in the registry, construct run, fpref assuming noNdep
            # will error on downstream calls
            run = f"1pctCO2_{sim.split('_')[0].upper()}{gcm_dir}"
            fpref = f"DLEM_{gcm_f}{sim}_noNdep"

        z = str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "DLEM"
            / run
            / f"{fpref}_{variable}_{cad}_05.nc"
        )
        return z

    def _time(self, ds: xr.Dataset):
        # "years/months since 1850" -> datetime64, preserving monthly cadence.
        tu = ds["time"].attrs.get("units", "")
        tv = np.asarray(ds["time"].values).astype("int64")
        base = np.datetime64("1850-01", "M")
        if "months since" in tu:
            return base + tv.astype("timedelta64[M]")
        return base + (tv * 12).astype("timedelta64[M]")  # years since 1850

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
        """Computed spherical cell area [m²] (ocean cells masked via fills on the data)."""
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
