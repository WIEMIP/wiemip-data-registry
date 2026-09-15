"""DVM-DOS-TEM adapter."""

from __future__ import annotations

import warnings

import numpy as np
import xarray as xr

from wiemip_registry import core
from wiemip_registry.const import DATA_ROOT, ONE_PERCENT_CO2_KEY, Factorial

MODEL = "DVM-DOS-TEM"
_OUTPUT = DATA_ROOT

_ANNUAL = {"alt"}

_GCM_FORCED = ("cou", "rad")
_FORCING_TOKENS = {"ipsl": "ipst"}

_NO_NITROGEN = "noNItrogen"
_NO_NITROGEN_CTRL = "noNitrogen"

_OVERSHOOT_SIMULATION_TOKENS = {"hist": "historic"}
_NO_FORCING_TOKEN = True

_HISTORICAL_OVERSHOOT_SIMULATIONS = ("hist", "hist_ctrl", "ctrl")
_ONE_PCT_SPAN = (1850, 150)  # 1850-1999
_HISTORICAL_SPAN = (1850, 174)  # 1850-2023, hist + both overshoot controls
_SCENARIO_SPAN = (2024, 277)  # 2024-2300


class DVM_DOS_TEM(core.WIEAdapter):
    """DVM-DOS-TEM is a REGIONAL model. Its grid stops at 28.75 N and only 18% of
    those cells carry data — the simulated domain runs 45.75-82.75 N and covers
    21.5 Mkm2, boreal and arctic land only. Every "global" integral from this adapter
    is therefore a high-latitude total and is NOT comparable to a whole-globe total
    from any other model in the registry.
    """

    model = MODEL
    LAT, LON = "lat", "lon"
    DECODE = False  # the uploaded time axis is unusable; `_time` synthesizes one
    FACTORIALS = {
        Factorial.baseline.name: "",
        Factorial.noFire.name: "noFire",
        Factorial.noNitrogen.name: _NO_NITROGEN,
        "noWetland": "noWetland",
        "noFire_noWetland": "noFire_noWetland",
    }

    def land_carbon_variables(self) -> list[str]:
        """cVeg + cSoil. UNCONFIRMED with the group."""
        return ["cVeg", "cSoil"]

    def _cadence(self, variable: str) -> str:
        return "yr" if variable in _ANNUAL or core.is_annual(variable) else "mon"

    def _factorial_token(self, simulation: str, factorial: str) -> str:
        token = self.FACTORIALS[factorial]
        if (
            factorial == Factorial.noNitrogen.name
            and simulation.split("_")[0] == "ctrl"
        ):
            return _NO_NITROGEN_CTRL
        return token

    def _run(self, simulation: str, forcing: str, factorial: str) -> str:
        """`DVM-DOS-TEM_<forcing>_<sim>[_<factorial>]` — names the run dir AND prefixes
        every file inside it."""
        token = forcing.lower() if simulation.split("_")[0] in _GCM_FORCED else "stable"
        token = _FORCING_TOKENS.get(token, token)
        run = f"{MODEL}_{token}_{simulation}"
        suffix = self._factorial_token(simulation, factorial)
        return f"{run}_{suffix}" if suffix else run

    def one_pct_path(self, simulation, forcing, factorial, variable) -> str:
        run = self._run(simulation, forcing, factorial)
        cad = self._cadence(variable)
        return str(
            _OUTPUT
            / "1pctCO2"
            / "output"
            / MODEL
            / run
            / f"{run}_{variable}_{cad}_05.nc"
        )

    def overshoot_path(self, simulation, forcing, variable, factorial=None) -> str:
        # Bare sim token for the run dir, and no forcing token anywhere — `forcing` is
        # accepted and ignored so every pattern resolves to the one uploaded run.
        run = _OVERSHOOT_SIMULATION_TOKENS.get(simulation, simulation)
        cad = self._cadence(variable)
        return str(
            _OUTPUT
            / "overshoot"
            / "output"
            / MODEL
            / run
            / f"{MODEL}_{run}_{variable}_{cad}_05.nc"
        )

    def _canonical_grid(self, ds: xr.Dataset) -> xr.Dataset:
        lat_values, lon_values = ds["Y"].values, ds["X"].values
        ds = ds.drop_vars(["Y", "X", "lat", "lon"], errors="ignore")
        ds = ds.assign_coords(y=lat_values, x=lon_values)
        return ds.rename({"y": self.LAT, "x": self.LON})

    def _time(self, ds: xr.Dataset, experiment: str, simulation: str, variable: str):
        """Synthesize the time axis — the uploaded one is unusable.

        Every file DVM-DOS-TEM uploaded carries a `time` coord whose first element is
        0.0 and whose every remaining element is NaN, so there is nothing to decode:
        decoding it yields NaT for all but the first step. The step COUNTS are right
        though (150/1800 for 1pctCO2, 174/2088 for overshoot hist+controls, 277/3324
        for the scenarios), so the axis is rebuilt from the count and the protocol
        start year.

        The declared CF epoch is not used and must not be: the scenarios say
        `days since 1901-01-01`, which is wrong in the other direction from the
        1850-hardcoding bug this function exists to avoid (`core.cf_reference_month`).
        Flagged to the group — once they re-upload a real axis, delete this and decode
        it like everyone else.
        """
        if experiment == ONE_PERCENT_CO2_KEY:
            start_year, expected_years = _ONE_PCT_SPAN
        elif simulation in _HISTORICAL_OVERSHOOT_SIMULATIONS:
            start_year, expected_years = _HISTORICAL_SPAN
        else:
            start_year, expected_years = _SCENARIO_SPAN

        n = ds.sizes["time"]
        annual = self._cadence(variable) == "yr"
        step_months = 12 if annual else 1
        if n != expected_years * (12 // step_months):
            warnings.warn(
                f"{MODEL} {experiment}/{simulation} {variable}: {n} timesteps, but the "
                f"protocol span is {expected_years} years "
                f"({'annual' if annual else 'monthly'}). The synthesized axis starts at "
                f"{start_year} and will NOT line up with the real run.",
                stacklevel=3,
            )
        start = np.datetime64(f"{start_year}-01", "M")
        return start + (np.arange(n) * step_months).astype("timedelta64[M]")

    def read(
        self, experiment, simulation, forcing, factorial, variable
    ) -> xr.DataArray:
        ds = xr.open_dataset(
            self.path(experiment, simulation, forcing, factorial, variable),
            decode_times=self.DECODE,
        )
        ds = self._canonical_grid(ds)
        warnings.warn(
            f"{MODEL} {experiment}/{simulation}: the uploaded `time` coord is all-NaN "
            f"past the first step, so the returned axis is SYNTHESIZED from the "
            f"timestep count and the protocol start year. Flagged to the group.",
            stacklevel=2,
        )
        da = core.mask_fill(ds[variable])
        da.attrs["units"] = ds[variable].attrs.get("units", "")
        return core.standardize(
            da, self.LAT, self.LON, self._time(ds, experiment, simulation, variable)
        )

    @property
    def _area_weight_path(self):
        return self.path("1pctCO2", "bgc", "stable", "baseline", "cVeg")

    def _compute_weights(self) -> xr.DataArray:
        """Computed spherical cell area [m²] on the model's REGIONAL grid (0.5 degree,
        28.75-89.75 N); ocean cells drop out via the data's NaN mask (no land-fraction
        raster shipped)."""
        ref = xr.open_dataset(self._area_weight_path, decode_times=self.DECODE)
        a = core.spherical_area(self._canonical_grid(ref), self.LAT, self.LON)
        ref.close()
        return a
