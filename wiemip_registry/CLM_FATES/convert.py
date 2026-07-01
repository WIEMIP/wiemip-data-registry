"""CLM-FATES adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Experiment, Simulation, GCMPattern

MODEL = "CLM-FATES"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output"

# How CLASSIC spells each simulation in the `1pctCO2-<SIM>` run token (ctrl is
# special-cased in path()).
_SIM = {Simulation.bgc: "BGC", Simulation.cou: "COU", Simulation.rad: "RAD"}

# CLASSIC factorial -> (ndep_part, post_part). Two slots because CLASSIC spells
# them in different places (verified on the bucket):
#   * `-Ndep` is part of the RUN token: it's in the dir AND the file prefix, e.g.
#     CLASSIC_UKESM_1pctCO2-BGC-Ndep/CLASSIC_UKESM_1pctCO2-BGC-Ndep_cVeg_ann_1deg.nc
#   * `_noFire` / `_noNitrogen` suffix the DIR but trail the CADENCE in the file:
#     CLASSIC_UKESM_1pctCO2-BGC_noFire/CLASSIC_UKESM_1pctCO2-BGC_cVeg_ann_noFire_1deg.nc
_FACTORIALS = {
    "baseline": ("", ""),
}
_PREFIX = "FATES_ukesm"


class CLM_FATES(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = _FACTORIALS

    # CLM-FATES uploads wetland fraction monthly even though const.ANNUAL lists
    # wetfrac as annual (model-specific cadence override).
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

    def path(self, experiment, simulation, forcing, factorial, variable) -> str:
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
        z = str(
            _OUTPUT
            / MODEL
            / f"{_PREFIX}_{simulation.name}_land.{variable}.tavg-{level}-hxy-{vegtype}.{cad}.glb_1.nc"
        )
        print(variable, z)
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
                Experiment.one_percent_co2,
                Simulation.bgc,
                GCMPattern.ukesm,
                "baseline",
                "cVeg",
            ),
            decode_times=self.DECODE,
        )
        cell = core.spherical_area(ref, self.LAT, self.LON)
        ref.close()
        sftlf = xr.open_dataset(_SFTLF)["sftlf"]
        return core.rename_latlon((cell * sftlf).astype("float32"), self.LAT, self.LON)


if __name__ == "__main__":
    obj = CLM_FATES()
    import sys

    var = sys.argv[1]
    print(
        obj.path(
            experiment=Experiment.one_percent_co2,
            simulation=Simulation.cou,
            forcing=GCMPattern.ukesm,
            factorial="baseline",
            variable=var,
        )
    )
