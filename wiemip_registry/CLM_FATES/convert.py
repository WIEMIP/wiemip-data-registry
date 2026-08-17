"""CLM-FATES adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "CLM-FATES"
_OUTPUT = DATA_ROOT

_FACTORIALS = {
    Factorial.baseline.name: ("", ""),
}
# Only ukesm was submitted. The constant-climate runs (bgc/ctrl) are labelled `ukesm`
# on disk even though the protocol requires requesting them as `stable` — no pinning
# here, so a `stable` request spells a path that doesn't exist and raises at read(),
# flagging the run as unreachable until CLM-FATES re-uploads it under a neutral token
# (as CLASSIC did). This used to be a flat `FATES_ukesm` prefix that ignored `forcing`
# entirely, so an ipsl or gfdl request silently returned ukesm data (identical global
# sums, no error) instead of raising for a run that was never submitted.
_PREFIX = "FATES"

# ml_cf is the one overshoot sim whose on-disk token is hyphenated.
_OVERSHOOT_SIMULATION_TOKENS = {"ml_cf": "ml-cf"}


class CLM_FATES(core.WIEAdapter):
    """
    CLM-FATES does not run any factorials.
    CLM-FATES also runs
    """

    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = _FACTORIALS

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
        "wetCH4": "wetlandCH4",
        "wetfrac": "wetlandFrac",
    }

    def land_carbon_variables(self) -> list[str]:
        return ["cLitter", "cVeg", "cSoil"]

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

    def _fname(self, token: str, simulation: str, variable: str) -> str:
        """`FATES_<token>_<sim>_land.<VAR>.tavg-<level>-hxy-<vegtype>.<cad>.glb_1.nc`
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
        return (
            f"{_PREFIX}_{token}_{simulation}_land.{variable}"
            f".tavg-{level}-hxy-{vegtype}.{cad}.glb_1.nc"
        )

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / MODEL
            / self._fname(forcing.lower(), simulation, variable)
        )

    def overshoot_path(self, simulation, forcing, variable) -> str:
        # ukesm only, but spell the requested pattern so ipsl/gfdl raise.
        simulation = _OVERSHOOT_SIMULATION_TOKENS.get(simulation, simulation)
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / MODEL
            / self._fname(forcing.lower(), simulation, variable)
        )

    def _time(self, ds: xr.Dataset):
        return ds["time"].values  # already datetime64 (decode_times=True)

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        if variable in ("fN2O", "wetCH4"):
            # clm fates reports these in g, not kg: the declared units say
            # kg m-2 s-1 but the global integral is ~1000x too large (g -> kg).
            ds[self._get_variable(variable)] = ds[self._get_variable(variable)] / 1000
        da = core.mask_fill(ds[self._get_variable(variable)])
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
