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

# Pool-split variables (both arms): one requested name fans out to one file per
# pool (x time chunks on the overshoot arm); read() stacks them along a "pool" dim
# (same dim name as BiomeE's single-file cSoilPools). Labels per CLM_README:
# cSoilpools _1/_2/_3 = fast/slow/passive; rhPools l1-l3 = litter, s1-s3 = soil,
# plus cwd. The file's data variable is named like its filename token (e.g.
# "rhPools_cwd"), not the requested name.
_POOL_SPLITS = {
    "cSoilPools": {
        "fast": "cSoilpools_1",
        "slow": "cSoilpools_2",
        "passive": "cSoilpools_3",
    },
    "rhPools": {p: f"rhPools_{p}" for p in ("cwd", "l1", "l2", "l3", "s1", "s2", "s3")},
}

# The noNitrogen set spells its run dir with a `noN` token AFTER the pattern
# (`flat_ukesm_noN_bgc/`) and stamps a year span on every filename inside it
# (`…_cVeg.1850-2000.nc`). 1pctCO2 only — the overshoot arm is `hh` throughout.
_FACTORIAL_RUN_TOKENS = {Factorial.noNitrogen.name: "noN"}
_FACTORIAL_YEAR_SPANS = {Factorial.noNitrogen.name: ".1850-2000"}

# WIEMIP's wetCH4 is the net emission from ALL wetlands and fch4soil is soil uptake
# only, but CLM splits its CH4 by inundation: wetCH4 is the net flux from the
# inundated fraction and fch4soil the net flux from the rest
# pos(wetCH4) + pos(fch4soil), fch4soil = neg(wetCH4) +
# neg(fch4soil).
# From Juliette Bernard's script, agreed with Will Wieder and Jessica Needham
# 2026-09-21.
_CH4_SPLIT = ("wetCH4", "fch4soil")


class CLM(core.WIEAdapter):
    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # mixed "yr" / noleap "hours since 1850" axis, decoded by hand
    FACTORIALS = {
        Factorial.baseline.name: "hh",
        "flat": "flat",
        Factorial.noNitrogen.name: "flat",
    }

    # overshoot band validation: global sums ~1e11 for these, ceiling is 1e6
    PROVISIONAL_DATA = (
        ("overshoot", "LWalbedo"),
        ("overshoot", "albedo"),
        ("overshoot", "fpar"),
        ("overshoot", "swalbedo"),
    )

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
        run_token = _FACTORIAL_RUN_TOKENS.get(factorial, "")
        run_dir = "_".join(filter(None, (prefix, token, run_token, simulation)))
        year_span = _FACTORIAL_YEAR_SPANS.get(factorial, "")
        fname = f"clm6_{run_dir}_{variable}{year_span}.nc"
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

    def _files(self, experiment, simulation, forcing, factorial, variable) -> list[str]:
        """The file(s) one on-disk variable lives in: time chunks on the overshoot arm."""
        if experiment == "overshoot":
            return self._overshoot_files(simulation, forcing, factorial, variable)
        return [self.path(experiment, simulation, forcing, factorial, variable)]

    def paths(self, experiment, simulation, forcing, factorial, variable) -> list[str]:
        if variable in _POOL_SPLITS:
            file_vars = _POOL_SPLITS[variable].values()
        elif variable in _CH4_SPLIT:
            file_vars = _CH4_SPLIT  # each re-split variable reads both files
        else:
            file_vars = (variable,)
        return [
            path
            for file_var in file_vars
            for path in self._files(
                experiment, simulation, forcing, factorial, file_var
            )
        ]

    def _time(self, ds: xr.Dataset):
        t = ds["time"]
        if t.attrs.get("units") == "yr":  # annual pools: a bare calendar-year axis
            return core.years_to_datetime(t.values)
        # monthly, contiguous from the epoch in the file's own units — January 1850 for
        # 1pctCO2, the chunk's first year for the overshoot files. Index it
        # month-by-month rather than unpick the noleap sub-month timestamps.
        epoch = np.datetime64(t.attrs["units"].split("since")[1].strip()[:7], "M")
        return epoch + np.arange(t.size).astype("timedelta64[M]")

    def _read_one(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        """One on-disk variable: its (possibly time-chunked) files, concatenated."""
        chunks = []
        for path in self._files(experiment, simulation, forcing, factorial, variable):
            ds = xr.open_dataset(path, decode_times=self.DECODE)
            da = core.mask_fill(ds[variable])
            chunks.append(core.standardize(da, self.LAT, self.LON, self._time(ds)))
        if len(chunks) == 1:
            return chunks[0]
        return xr.concat(chunks, dim="time")

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        if variable in _POOL_SPLITS:
            split = _POOL_SPLITS[variable]
            pools = [
                self._read_one(experiment, simulation, forcing, factorial, file_var)
                for file_var in split.values()
            ]
            labels = xr.DataArray(list(split), dims="pool", name="pool")
            return xr.concat(pools, dim=labels).rename(variable)
        if variable in _CH4_SPLIT:
            wet, soil = (
                self._read_one(experiment, simulation, forcing, factorial, file_var)
                for file_var in _CH4_SPLIT
            )
            if variable == "wetCH4":
                own = wet
                split = wet.where(wet > 0, 0) + soil.where(soil > 0, 0)
            else:
                own = soil
                split = wet.where(wet < 0, 0) + soil.where(soil < 0, 0)
            # where() zero-fills NaN, so re-mask the ocean from the variable's own file
            return (
                split.where(own.isel(time=0, drop=True).notnull())
                .rename(variable)
                .assign_attrs(units=own.attrs["units"])
            )
        return self._read_one(experiment, simulation, forcing, factorial, variable)

    @property
    def _area_weight_path(self):
        return self.path("1pctCO2", "bgc", "ukesm", "baseline", "cVeg")

    def _compute_weights(self) -> xr.DataArray:
        """Land area per cell [m²] from the shipped `area` (km²) and `landfrac`."""
        ref = xr.open_dataset(
            self._area_weight_path,
            decode_times=self.DECODE,
        )
        weights = ref["area"] * 1e6 * ref["landfrac"]
        ref.close()
        return core.rename_latlon(weights, self.LAT, self.LON)
