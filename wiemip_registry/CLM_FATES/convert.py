"""CLM-FATES adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "CLM-FATES"
_OUTPUT = DATA_ROOT

_FACTORIALS = {
    Factorial.baseline.name: "",
    Factorial.noFire.name: "nofire",
}
_PREFIX = "FATES"
_GCM_FORCED = ("cou", "rad")

# The counterfactual overshoot sims are hyphenated on disk (vl_cf/hl_cf uploaded
# 2026-08, after ml_cf).
_OVERSHOOT_SIMULATION_TOKENS = {"ml_cf": "ml-cf", "vl_cf": "vl-cf", "hl_cf": "hl-cf"}

# WIEMIP's wetCH4 is the net emission from ALL wetlands and fch4soil is soil uptake
# only. FATES' own wetlandCH4 covers just the inundated fraction and it uploaded no
# fch4soil, so both come from the net soil flux ch4, split by sign per cell and
# timestep: wetCH4 = pos(ch4), fch4soil = neg(ch4). The wetlandCH4 upload goes
# unread. From Juliette Bernard's script, agreed with Jessica Needham and Will
# Wieder 2026-09-21.
_CH4_SPLIT = ("wetCH4", "fch4soil")


class CLM_FATES(core.WIEAdapter):
    """
    CLM-FATES does not run any factorials.
    CLM-FATES also runs
    """

    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = _FACTORIALS

    # overshoot band validation: global sums ~3e6 Pg yr-1 for these, ceiling is 1e6
    PROVISIONAL_DATA = (
        ("overshoot", "fRootLitter"),
        ("overshoot", "fWoodLitter"),
    )

    # CLM-FATES uploads wetland fraction monthly even though const.ANNUAL lists
    # wetfrac as annual
    MONTHLY = {"wetfrac"}
    wiemip_to_clm_fates_variable_mapping = {
        "alt": "ALT",
        "burntArea": "burntFractionAll",
        "cVegPft": "cVegpft",
        "nInorgSoil": "nMineral",
        "tair": "tas",
        "tveg": "tran",
        "firerosTotal": "fireosTotal",
        "wetfrac": "wetlandFrac",
    }

    def land_carbon_variables(self) -> list[str]:
        """
        Confirmed with Jessie Needham.
        """
        return ["cLitter", "cVeg", "cSoil", "cOther"]

    def _get_variable(self, wiemip_variable: str) -> str:
        if wiemip_variable in self.wiemip_to_clm_fates_variable_mapping:
            return self.wiemip_to_clm_fates_variable_mapping[wiemip_variable]
        return wiemip_variable

    def _vegtype(self, variable):
        vegtype = "multi" if "pft" in variable.lower() else "lnd"
        if variable in (
            "fAllocLeaf",
            "fAllocRoot",
            "fAllocWood",
            "cfuelTotal",
            "mfuelTotal",
            "cVegpft",
        ):
            vegtype = "multi"
        elif variable in ("tas", "burntFractionAll", "landCoverFrac", "wetlandFrac"):
            vegtype = "u"
        return vegtype

    def _fname(
        self, token: str, simulation: str, variable: str, factorial_token: str = ""
    ) -> str:
        """`FATES_<token>_<sim>_land.<VAR>.tavg-<level>-hxy-<vegtype>.<cad>.glb[_<fact>]_1.nc`
        — the same grammar in both experiments."""
        cad = (
            "mon"
            if variable in self.MONTHLY
            else ("yr" if core.is_annual(variable) else "mon")
        )
        if variable in ("cSoilAbove1m", "cSoilBelow1m"):
            level = "d100cm"
        elif variable in ("cSoilLayers", "soilIce", "soilRh"):
            level = "sl"
        elif variable == "tas":
            level = "h2m"
        else:
            level = "u"

        variable = self._get_variable(wiemip_variable=variable)
        vegtype = self._vegtype(variable)
        fact = f"_{factorial_token}" if factorial_token else ""
        return (
            f"{_PREFIX}_{token}_{simulation}_land.{variable}"
            f".tavg-{level}-hxy-{vegtype}.{cad}.glb{fact}_1.nc"
        )

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        token = forcing.lower() if simulation.split("_")[0] in _GCM_FORCED else "stable"
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / MODEL
            / self._fname(token, simulation, variable, self.FACTORIALS[factorial])
        )

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        # ukesm only, but spell the requested pattern so ipsl/gfdl raise.
        simulation = _OVERSHOOT_SIMULATION_TOKENS.get(simulation, simulation)
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / MODEL
            / self._fname(forcing.lower(), simulation, variable)
        )

    def paths(self, experiment, simulation, forcing, factorial, variable) -> list[str]:
        if variable in _CH4_SPLIT:
            return [self.path(experiment, simulation, forcing, factorial, "ch4")]
        return super().paths(experiment, simulation, forcing, factorial, variable)

    def _time(self, ds: xr.Dataset):
        return ds["time"].values  # already datetime64 (decode_times=True)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        if variable in _CH4_SPLIT:
            ch4 = self.read(experiment, simulation, forcing, factorial, "ch4")
            if variable == "wetCH4":
                split = ch4.where(ch4 > 0, 0)
            else:
                split = ch4.where(ch4 < 0, 0)
            # where() zero-fills NaN, so re-mask the ocean
            return (
                split.where(ch4.isel(time=0, drop=True).notnull())
                .rename(variable)
                .assign_attrs(units=ch4.attrs["units"])
            )
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[self._get_variable(variable)])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    @property
    def _area_weight_path(self):
        return self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg")

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²] (ocean cells masked via fills on the data)."""
        ref = xr.open_dataset(self._area_weight_path, decode_times=self.DECODE)
        a = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        return core.rename_latlon(a, self.LAT, self.LON)


if __name__ == "__main__":
    obj = CLM_FATES()
    import sys

    var = sys.argv[1]
    print(
        obj.path(
            experiment="1pctCO2",
            simulation="cou",
            forcing="ukesm",
            factorial="baseline",
            variable=var,
        )
    )
