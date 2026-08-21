"""
CLM adapter.

The overshoot upload reuses the 1pctCO2 grammar for the run dir and file prefix
(`hh_<forcing>_<sim>/clm6_hh_<forcing>_<sim>_<var>`), with two differences: `hist` is
CRUJRA-driven so it carries no pattern token, and each variable is split into time
chunks (`.2024-2100.nc`, `.2101-2200.nc`, `.2201-2300.nc`; `hist` uses `.1850-1950` +
`.1951-2023`), so `paths()` lists the chunks and `read()` concatenates them. Only the
`hh` set was submitted, and no control run.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, Factorial

MODEL = "CLM"
_OUTPUT = DATA_ROOT

# Time chunks each overshoot variable is split across.
_SCENARIO_CHUNKS = ("2024-2100", "2101-2200", "2201-2300")
_OVERSHOOT_CHUNKS = {"hist": ("1850-1950", "1951-2023")}

# hist is CRUJRA-driven, so its run token carries no GCM pattern.
_UNFORCED_OVERSHOOT_SIMS = ("hist", "hist_ctrl")

# Pool-split variables (1pctCO2 arm): one requested name fans out to one file per
# pool; read() stacks them along a "pool" dim (same dim name as BiomeE's single-file
# cSoilPools). Labels per CLM_README: cSoilpools _1/_2/_3 = fast/slow/passive;
# rhPools l1-l3 = litter, s1-s3 = soil, plus cwd. The file's data variable is named
# like its filename token (e.g. "rhPools_cwd"), not the requested name.
_POOL_SPLITS = {
    "cSoilPools": {
        "fast": "cSoilpools_1",
        "slow": "cSoilpools_2",
        "passive": "cSoilpools_3",
    },
    "rhPools": {p: f"rhPools_{p}" for p in ("cwd", "l1", "l2", "l3", "s1", "s2", "s3")},
}


class CLM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # mixed "yr" / noleap "hours since 1850" axis, decoded by hand
    # The factorial picks the run set: hh (baseline) or flat, CLM's two uploads.
    # flat's ctrl originally sat loose at the model-dir top (unreachable); moved
    # into flat_ukesm_ctrl/ on the bucket 2026-08-21, so all runs resolve here.
    FACTORIALS = {Factorial.baseline.name: "hh", "flat": "flat"}

    def land_carbon_variables(self) -> list[str]:
        """
        Confirmed by Will Wieder on 11/08/2026 to be cVeg and cSoil.
        """
        return ["cVeg", "cSoil"]

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        prefix = self.FACTORIALS[factorial]
        # cou/rad carry the GCM pattern; the constant-climate runs (bgc/ctrl) are
        # still labelled "ukesm" on disk, so that's the token for anything else.
        # Validated with Will Wieder on 8/17/2026
        gcm_forced = simulation.split("_")[0] in ("cou", "rad")
        token = forcing.lower() if gcm_forced else "ukesm"
        run_dir = f"{prefix}_{token}_{simulation}"
        fname = f"clm6_{prefix}_{token}_{simulation}_{variable}.nc"
        return str(_OUTPUT / "1pctCO2" / "output" / MODEL / run_dir / fname)

    def _overshoot_files(self, simulation, forcing, factorial, variable) -> list[str]:
        """The chunk files for one overshoot variable, oldest first."""
        prefix = self.FACTORIALS.get(factorial or Factorial.baseline.name)
        if prefix is None:
            raise core.MissingFactorialError(
                f"{MODEL} has no '{factorial}' factorial (has: {sorted(self.FACTORIALS)})"
            )
        if simulation in _UNFORCED_OVERSHOOT_SIMS:
            run = f"{prefix}_{simulation}"
        else:
            run = f"{prefix}_{forcing}_{simulation}"
        chunks = _OVERSHOOT_CHUNKS.get(simulation, _SCENARIO_CHUNKS)
        return [
            str(
                _OUTPUT
                / "overshoot"
                / "output"
                / MODEL
                / run
                / f"clm6_{run}_{variable}.{chunk}.nc"
            )
            for chunk in chunks
        ]

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        return self._overshoot_files(simulation, forcing, factorial, variable)[0]

    def paths(self, experiment, simulation, forcing, factorial, variable) -> list[str]:
        if experiment == "overshoot":
            return self._overshoot_files(simulation, forcing, factorial, variable)
        if variable in _POOL_SPLITS:
            return [
                self.one_pct_path(simulation, forcing, factorial, file_var)
                for file_var in _POOL_SPLITS[variable].values()
            ]
        return super().paths(experiment, simulation, forcing, factorial, variable)

    def _time(self, ds: xr.Dataset):
        t = ds["time"]
        if t.attrs.get("units") == "yr":  # annual pools: a bare calendar-year axis
            return core.years_to_datetime(t.values)
        # monthly, contiguous from the epoch in the file's own units — January 1850 for
        # 1pctCO2, the chunk's first year for the overshoot files. Index it
        # month-by-month rather than unpick the noleap sub-month timestamps.
        epoch = np.datetime64(t.attrs["units"].split("since")[1].strip()[:7], "M")
        return epoch + np.arange(t.size).astype("timedelta64[M]")

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        if variable in _POOL_SPLITS and experiment != "overshoot":
            pools = []
            for file_var in _POOL_SPLITS[variable].values():
                ds = xr.open_dataset(
                    self.one_pct_path(simulation, forcing, factorial, file_var),
                    decode_times=self.DECODE,
                )
                da = core.mask_fill(ds[file_var])
                pools.append(core.standardize(da, self.LAT, self.LON, self._time(ds)))
            labels = xr.DataArray(
                list(_POOL_SPLITS[variable]), dims="pool", name="pool"
            )
            return xr.concat(pools, dim=labels).rename(variable)
        chunks = []
        for path in self.paths(experiment, simulation, forcing, factorial, variable):
            ds = xr.open_dataset(path, decode_times=self.DECODE)
            da = core.mask_fill(ds[variable])
            chunks.append(core.standardize(da, self.LAT, self.LON, self._time(ds)))
        if len(chunks) == 1:
            return chunks[0]
        return xr.concat(chunks, dim="time")

    def _compute_weights(self) -> xr.DataArray:
        """Land area per cell [m²] from the shipped `area` (km²) and `landfrac`."""
        ref = xr.open_dataset(
            self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg"),
            decode_times=self.DECODE,
        )
        weights = ref["area"] * 1e6 * ref["landfrac"]
        ref.close()
        return core.rename_latlon(weights, self.LAT, self.LON)
