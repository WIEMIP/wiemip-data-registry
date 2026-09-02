"""DLEM adapter.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial, OnePctSimulation

MODEL = "DLEM"
_OUTPUT = DATA_ROOT
_AREA = _OUTPUT / "1pctCO2" / "output" / "DLEM" / "LAND_AREA_DLEM.nc"

_OVERSHOOT_NO_FORCING_TOKEN = ("ctrl", "hist", "hist_ctrl")


class DLEM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # numeric "years/months since 1850"
    # no factorials uploaded as far as I know
    FACTORIALS = {Factorial.baseline.name: ""}

    wiemip_to_dlem_variable_mapping = {
        "fFireLitter": "fFireCLitter",
        "nOrgSoilpft": "nSoilpft",
    }

    def land_carbon_variables(self) -> list[str]:
        """
        Confirmed with DLEM team on 2026/08/24. cLitter, cVeg, and cSoil make up the land carbon stock.
        """
        return ["cLitter", "cVeg", "cSoil"]

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

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        cad = "yr" if core.is_annual(variable) else "mon"
        if simulation in _OVERSHOOT_NO_FORCING_TOKEN:
            run, fpref = f"os_{simulation}", f"DLEM_{simulation}"
        else:
            run, fpref = f"os_future_{simulation}", f"DLEM_{forcing}_{simulation}"
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / "DLEM"
            / run
            / f"{fpref}_{variable}_{cad}_05.nc"
        )

    def _time(self, ds: xr.Dataset):
        # "years/months since <epoch>" -> datetime64, preserving monthly cadence.
        # The epoch is READ OFF THE FILE, not assumed: 1pctCO2 and the overshoot
        # hist/ctrl runs count from 1850, the overshoot scenarios from 2024.
        tu = ds["time"].attrs.get("units", "")
        tv = np.asarray(ds["time"].values).astype("int64")
        base = core.cf_reference_month(tu)
        if "months since" in tu:
            return base + tv.astype("timedelta64[M]")
        return base + (tv * 12).astype("timedelta64[M]")  # years since <epoch>

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
        """Provided land-area raster `LAND_AREA_DLEM.nc` [km2 -> m2]."""
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
        a = xr.open_dataset(_AREA)["LAND_AREA"] * 1e6  # km2 -> m2
        a = a.sel({self.LAT: ref[self.LAT], self.LON: ref[self.LON]})
        ref.close()
        return core.rename_latlon(a.astype("float32"), self.LAT, self.LON)
