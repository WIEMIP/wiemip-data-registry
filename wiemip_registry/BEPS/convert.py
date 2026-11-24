"""BEPS adapter."""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial, GCMPattern

MODEL = "BEPS"
_OUTPUT = DATA_ROOT / "1pctCO2" / "output" / MODEL
_OVERSHOOT_OUTPUT = DATA_ROOT / "overshoot" / "output" / MODEL

_SOIL_CONFIGURATIONS = {20: "layered", 1: "bucket"}

_CRUJRA_SIMULATIONS = ("hist", "hist_ctrl")


class BEPS(core.WIEAdapter):
    model = MODEL
    LAT, LON = "latitude", "longitude"
    DECODE = True
    FACTORIALS = {
        Factorial.baseline.name: "noDynVeg_noPermafrost",
        "permafrost": "noDynVeg",
    }

    LAYERED_VARIABLES = {
        "soilT",
        "soilMoist",
        "mrsoLayer",
        "cSoilLayers",
        "rhLayers",
        "soilRh",
        "nOrgSoilLayer",
        "nInorgSoilLayer",
        "cPoolVr",
        "fch4layer",
    }

    SPECIES_TO_CARBON = {"isopr", "isoprpft", "terp", "terppft"}

    MONTHLY = {"wetfrac"}
    ANNUAL = {"cOther", "canopyheightTotal", "highcoverTotal"}

    OVERSHOOT_FIXED = {"landCoverFrac"}

    def land_carbon_variables(self) -> list[str]:
        return ["cVeg", "cSoil"]

    def _cadence(self, variable) -> str:
        if variable in self.MONTHLY:
            return "mon"
        if variable in self.ANNUAL or core.is_annual(variable):
            return "yr"
        return "mon"

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        cadence = self._cadence(variable)
        token = self.FACTORIALS[factorial]
        return str(
            _OUTPUT / f"BEPS_{forcing}_{simulation}_{variable}_{cadence}_{token}_1.nc"
        )

    def disk_simulation(self, simulation: str) -> str:
        return simulation

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        if simulation in _CRUJRA_SIMULATIONS and forcing == GCMPattern.ukesm.name:
            run = f"BEPS_{simulation}"
        else:
            run = f"BEPS_{forcing}_{simulation}"
        cadence = "fx" if variable in self.OVERSHOOT_FIXED else self._cadence(variable)
        fname = f"{run}_{variable}_{cadence}_1.nc"
        return str(_OVERSHOOT_OUTPUT / run / fname)

    def _time(self, ds: xr.Dataset):
        return ds["time"].values

    def _layer_depths(self, number_of_layers: int) -> list[float]:
        soil = xr.open_dataset(_OUTPUT / "soil_metadata_1deg.nc")
        configuration = _SOIL_CONFIGURATIONS[number_of_layers]
        top = soil[f"{configuration}_layer_top_depth"].values
        bottom = soil[f"{configuration}_layer_bottom_depth"].values
        soil.close()
        return ((top + bottom) / 2).tolist()

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        da = core.mask_fill(ds[variable])
        if experiment == "overshoot" and variable in self.OVERSHOOT_FIXED:
            da = core.rename_latlon(da.squeeze("time", drop=True), self.LAT, self.LON)
            return da.transpose("lat", "lon", ...)
        if variable in self.LAYERED_VARIABLES:
            layer_dim = "layer" if "layer" in da.dims else "nsoil"
            depths = self._layer_depths(da.sizes[layer_dim])
            da = da.assign_coords({layer_dim: (layer_dim, depths, {"units": "m"})})
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    @property
    def area_weight_path(self):
        return _OUTPUT / "global_domain_1deg.nc"

    def _compute_weights(self) -> xr.DataArray:
        domain = xr.open_dataset(self.area_weight_path)
        cell_area = domain["cell_area"].load()
        domain.close()
        return cell_area
