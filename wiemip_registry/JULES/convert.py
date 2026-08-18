"""JULES adapter.

Naming (verified on the bucket): nested run dirs
`JULESwiemipV2_<sim>_<config>/` holding files
`JULESwiemipV2_<sim>_<var>_yr_<config>_n96.nc` (always annual). `<sim>` is bgc /
ctl / `<forcing>_cou`. The `<config>` string IS the factorial — every run carries
a Nitrogen/DynVeg/Permafrost/Fire combination; the README reference run
`Nitrogen_DynVeg_Permafrost_noFire` is our `baseline`. path() is a pure transform
— what exists is decided by read().

The overshoot upload keeps the config idea but spells it differently: the config
leads the prefix instead of trailing the sim token (`JULESwiemipV2<config>_<run>/`),
only the fire axis was repeated, and those configs are `noFire`/`FireP####` rather
than the full 1pct strings. cVeg and cSoil only.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "JULES"
_OUTPUT = DATA_ROOT
_LANDFRAC = _OUTPUT / "1pctCO2" / "output" / "JULES" / "landfrac_n96.nc"

# Factorial name -> the JULES config string baked into the run dir AND filename.
_FACTORIALS = {
    Factorial.baseline.name: "Nitrogen_DynVeg_Permafrost_noFire",
    Factorial.noFire_noNitrogen.name: "noNitrogen_DynVeg_Permafrost_noFire",
    "noDynVeg": "Nitrogen_noDynVeg_Permafrost_noFire",
    "noPermafrostC": "Nitrogen_DynVeg_noPermafrostC_noFire",
    "noPermafrostCN": "Nitrogen_DynVeg_noPermafrostCN_noFire",
    "noPermafrostCNNinorg": "Nitrogen_DynVeg_noPermafrostCNNinorg_noFire",
    "addPermafrostC": "Nitrogen_DynVeg_addPermafrostC_noFire",
    "addPermafrostCN": "Nitrogen_DynVeg_addPermafrostCN_noFire",
    "addPermafrostCNNinorg": "Nitrogen_DynVeg_addPermafrostCNNinorg_noFire",
    "noNitrogen_addPermafrostC": "noNitrogen_DynVeg_addPermafrostC_noFire",
    "noNitrogen_noPermafrostC": "noNitrogen_DynVeg_noPermafrostC_noFire",
    "Fire0005": "Nitrogen_DynVeg_Permafrost_Fire0005",
    "Fire0249": "Nitrogen_DynVeg_Permafrost_Fire0249",
    "Fire0304": "Nitrogen_DynVeg_Permafrost_Fire0304",
    "Fire0336": "Nitrogen_DynVeg_Permafrost_Fire0336",
}


# Overshoot fire configs, keyed by the 1pct factorial name they correspond to.
_OVERSHOOT_CONFIGS = {
    Factorial.baseline.name: "noFire",
    "Fire0005": "FireP0005",
    "Fire0249": "FireP0249",
    "Fire0304": "FireP0304",
    "Fire0336": "FireP0336",
}

# hist and the control are CRUJRA-driven, so their run token carries no GCM pattern.
_UNFORCED_OVERSHOOT_SIMS = {"hist": "hist", "ctrl": "ctl"}


def _sim_tok(simulation, forcing) -> str:
    if simulation == "cou":
        return f"{forcing}_cou"
    if simulation == "rad":
        return f"{forcing}_rad"
    if simulation == "ctrl":
        return "ctl"
    return "bgc"


class JULES(core.WIEAdapter):
    """JULES submitted a bunch of factorials which have to be accessed by name in the
    retrieve_one_pct_variable() function. See the factorials dict in wiemip_registry/JULES/convert.py for a
    listing.
    """

    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = _FACTORIALS
    OVERSHOOT_FACTORIALS = _OVERSHOOT_CONFIGS

    def land_carbon_variables(self) -> list[str]:
        """
        # No cLitter was submitted (0 files across every combo), so the land carbon
        # total is veg + soil and litter is presumed folded into the reported cSoil.
        # Confirmed with the JULES group.
        """
        return ["cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        config = self.FACTORIALS[factorial]
        tok = _sim_tok(simulation, forcing)
        run = f"JULESwiemipV2_{tok}_{config}"
        fname = f"JULESwiemipV2_{tok}_{variable}_yr_{config}_n96.nc"  # always annual
        return str(_OUTPUT / "1pctCO2" / "output" / "JULES" / run / fname)

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        config = self.OVERSHOOT_FACTORIALS.get(factorial or Factorial.baseline.name)
        if config is None:
            raise core.MissingFactorialError(
                f"{MODEL} ran no '{factorial}' overshoot config "
                f"(has: {sorted(self.OVERSHOOT_FACTORIALS)})"
            )
        # The counterfactual scenarios are hyphenated on disk (hl-cf, not hl_cf).
        tok = _UNFORCED_OVERSHOOT_SIMS.get(
            simulation, f"{forcing}_{simulation.replace('_cf', '-cf')}"
        )
        run = f"JULESwiemipV2{config}_{tok}"
        fname = f"{run}_{variable}_yr_n96.nc"  # always annual
        return str(_OUTPUT / "overshoot" / "output" / MODEL / run / fname)

    def _time(self, ds: xr.Dataset):
        return ds[
            "time"
        ].values  # datetime64 (decode_times=True); ignore the `year` coord

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
        """Spherical cell area × land fraction (ocean fill ~1e37 -> 0)."""
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
        land = xr.open_dataset(_LANDFRAC)["land"]
        land = land.where(land <= 1.0, 0.0)
        return core.rename_latlon((cell * land).astype("float32"), self.LAT, self.LON)
