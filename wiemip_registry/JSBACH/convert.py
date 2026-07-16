"""JSBACH adapter.

Naming (verified on the bucket): nested run dirs holding same-named files.
bgc/ctrl carry a `stable_` tag (`JSBACH_stable_<sim>`), cou carries the GCM
(`JSBACH_<forcing>_cou`); the factorial is a trailing suffix. path() is a pure
transform — what exists is decided by read() opening the file.
"""

from __future__ import annotations

import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "JSBACH"
_OUTPUT = DATA_ROOT

_SFTLF = _OUTPUT / "1pctCO2" / "output" / "JSBACH" / "sftlf_1.nc"


def _stem(simulation, forcing, run_suf: str) -> str:
    """The JSBACH run token (file prefix); the dir additionally carries `post`.
    ndep is a simulation (bgc_ndep/cou_ndep), so the sim token already carries the
    `_ndep`; the GCM tag keys on the BASE sim (cou/rad are the GCM-forced ones)."""
    if simulation.split("_")[0] in ("cou", "rad"):
        return f"JSBACH_{forcing}_{simulation}{run_suf}"
    return f"JSBACH_stable_{simulation}{run_suf}"  # bgc, ctrl (+ _ndep)


class JSBACH(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = True
    FACTORIALS = {
        Factorial.baseline.name: ("", ""),
        Factorial.noNitrogen.name: ("", "_noNitrogen"),
        Factorial.noFire.name: ("", "_noFire"),
    }

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        run_suf, post = self.FACTORIALS[factorial]
        stem = _stem(simulation, forcing, run_suf)
        cad = "yr" if core.is_annual(variable) else "mon"
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / "JSBACH"
            / f"{stem}{post}"
            / f"{stem}_{variable}_{cad}{post}_1.nc"
        )

    def overshoot_path(self, simulation, forcing, variable) -> str:
        # overshoot has no factorial axis -> the bare baseline run token, no suffix.
        stem = _stem(simulation, forcing, "")
        cad = "yr" if core.is_annual(variable) else "mon"
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / "JSBACH"
            / stem
            / f"{stem}_{variable}_{cad}_1.nc"
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
        sftlf = core.rename_latlon(xr.open_dataset(_SFTLF)["sftlf"], self.LAT, self.LON)
        return core.rename_latlon(
            (cell * sftlf.values).astype("float32"), self.LAT, self.LON
        )
