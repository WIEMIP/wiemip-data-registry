"""JSBACH adapter.

Naming (verified on the bucket): nested run dirs holding same-named files.
bgc/ctrl carry a `stable_` tag (`JSBACH_stable_<sim>`), cou carries the GCM
(`JSBACH_<forcing>_cou`); the factorial is a trailing suffix, except the dynamic
vegetation runs (2026-09-23), which put a `dynveg` token before the sim in the
filename and a suffix on the dir only. path() is a pure transform — what exists is
decided by read() opening the file.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "JSBACH"
_OUTPUT = DATA_ROOT

# Overshoot hist/ctrl are CRUJRA-driven; the scenarios carry the GCM pattern.
_CRUJRA_FORCED_SIMULATIONS = ("hist", "ctrl")
_CRUJRA_TOKEN = "crujra3"

_OVERSHOOT_RUN_TOKENS = {"baseline": "", "dynVeg": "dynveg"}


def _stem(simulation, forcing, run_token: str = "") -> str:
    if simulation.split("_")[0] in ("cou", "rad"):
        return f"JSBACH_{forcing}_{run_token}{simulation}"
    return f"JSBACH_stable_{run_token}{simulation}"  # bgc, ctrl (+ _ndep)


class JSBACH(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = {
        Factorial.baseline.name: ("", "", ""),
        Factorial.noNitrogen.name: ("_noNitrogen", "", "_noNitrogen"),
        Factorial.noFire.name: ("_noFire", "", "_noFire"),
        "dynVeg_noNitrogen": ("_dynveg_noNitrogen", "dynveg_", ""),
        "dynVeg_noFire_noNitrogen": ("_dynveg_noNitrogen_noFire", "dynveg_nofire_", ""),
    }
    OVERSHOOT_FACTORIALS = _OVERSHOOT_RUN_TOKENS

    def land_carbon_variables(self) -> list[str]:
        """
        Aug 7: Confirmed with Beiyao Xu that our aggregations and
        definitions of land carbon stock are correct.
        They include cLitter, cVeg, and cSoil.
        """
        return ["cLitter", "cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        dir_suf, run_token, post = self.FACTORIALS[factorial]
        cad = "yr" if core.is_annual(variable) else "mon"
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "JSBACH"
            / f"{_stem(simulation, forcing)}{dir_suf}"
            / f"{_stem(simulation, forcing, run_token)}_{variable}_{cad}{post}_1.nc"
        )

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        # Run dir is the bare simulation token, `_dynveg`-suffixed for that factorial.
        run_token = self.OVERSHOOT_FACTORIALS.get(factorial or Factorial.baseline.name)
        if run_token is None:
            raise core.MissingFactorialError(
                f"{MODEL} ran no '{factorial}' overshoot config "
                f"(has: {sorted(self.OVERSHOOT_FACTORIALS)})"
            )
        forcing_token = (
            _CRUJRA_TOKEN if simulation in _CRUJRA_FORCED_SIMULATIONS else forcing
        )
        run_dir = f"{simulation}_{run_token}" if run_token else simulation
        file_token = f"{run_token}_{simulation}" if run_token else simulation
        cadence = "yr" if core.is_annual(variable) else "mon"
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / "JSBACH"
            / run_dir
            / f"JSBACH_{forcing_token}_{file_token}_{variable}_{cadence}_1.nc"
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
        da = core.mask_fill(ds[variable])
        return core.standardize(da, self.LAT, self.LON, self._time(ds))

    @property
    def _area_weight_path(self):
        return _OUTPUT / "1pctCO2" / "output" / "JSBACH" / "sftlf_1.nc"

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²] (ocean -> NaN on the data)."""
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
        sftlf = core.rename_latlon(
            xr.open_dataset(self._area_weight_path)["sftlf"], self.LAT, self.LON
        )
        return core.rename_latlon(
            (cell * sftlf.values).astype("float32"), self.LAT, self.LON
        )
