"""
Core of `wiemip_registry`: the `WIEAdapter` contract every per-model adapter
fills out, the `WIEFile` wrapper the dotted namespace resolves to, and the small
set of generic helpers the adapters share.

Per-model knowledge (paths, dims, time encoding, area recipe, fills) lives in
each `<MODEL>/convert.py` as a `WIEAdapter` subclass. This module only holds the
*generic* mechanics (spherical area, standardize, fill masking, weighted
aggregation), all seeded from the proven `extract.py`.
"""

from __future__ import annotations

import abc
import os
import functools
from abc import ABC
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import wiemip_registry.const as const


class MissingModelError(Exception):
    pass


class MissingForcingError(Exception):
    pass


class MissingSimulationError(Exception):
    pass


class MissingVariableError(Exception):
    pass


class MissingFactorialError(Exception):
    pass


class Model(str):
    """A model name that also carries its adapter. Still a plain string
    (equality, hashing, joins, dict lookup all behave as the bare name), so it is
    a drop-in for the old string entries of `wr.models`; the extra attributes just
    save the `wr.adapters[name]` hop."""

    def __new__(cls, name: str, adapter: WIEAdapter) -> Model:
        obj = str.__new__(cls, name)
        obj._adapter = adapter
        return obj

    @property
    def adapter(self) -> WIEAdapter:
        return self._adapter

    @property
    def factorials(self) -> tuple[str, ...]:
        """Factorial names this model accepts (auto-ingested from its adapter)."""
        return self._adapter.factorials


class WIEAdapter(ABC):
    """
    Contract that each model must fill out. This converts whatever naming
    convention was uploaded to the WIE-MIP S3 bucket into something callable in
    Python.

    Subclasses implement the three abstract hooks (`path`, `read`,
    `_compute_weights`). There is no per-model "what exists" schema: the namespace
    lets a user select any (experiment, model, forcing, simulation, factorial,
    variable) by name, and a combination that wasn't uploaded simply fails when
    `read()` tries to open the file.
    """

    model: str

    _weights_cache: xr.DataArray | None = None

    # Per-model factorial vocabulary: canonical bucket -> however THIS model spells
    # the factorial
    # either overriden or set in the adapter subclass
    FACTORIALS: dict[str, str] = {"baseline": ""}

    @property
    def factorials(self) -> tuple[str, ...]:
        """The factorial names this model accepts (drives namespace validation
        and tab-completion of the factorial axis)."""
        return tuple(self.FACTORIALS)

    @abc.abstractmethod
    def one_pct_path(
        self,
        simulation: str,
        forcing: str,
        factorial: str,
        variable: str,
    ) -> str:
        """Build the .nc path on the mounted S3 bucket by transforming the axis
        tokens into THIS model's upload naming convention."""

        raise NotImplementedError()

    def overshoot_path(
        self,
        simulation: str,
        forcing: str,
        variable: str,
    ) -> str:
        """Overshoot-experiment path (no factorial axis). Overridden per model once
        that model's overshoot upload naming is known; until then asking for an
        overshoot path raises here rather than guessing a layout. Like `one_pct_path`
        it's a pure string transform — what exists is decided by `read()`."""
        raise NotImplementedError(f"overshoot paths not yet mapped for {self.model}")

    def path(self, experiment, simulation, forcing, factorial, variable):
        if experiment == "1pctCO2":
            if factorial not in self.FACTORIALS:
                raise MissingFactorialError(
                    f"{self.model} has no '{factorial}' factorial (has: {sorted(self.FACTORIALS)})"
                )
            pth = self.one_pct_path(simulation, forcing, factorial, variable)
        elif experiment == "overshoot":
            pth = self.overshoot_path(simulation, forcing, variable)
        else:
            raise ValueError("Must specify either overshoot or one_percent_co2!")
        return pth

    @abc.abstractmethod
    def read(
        self,
        experiment: str,
        simulation: str,
        forcing: str,
        factorial: str,
        variable: str,
    ) -> xr.DataArray:
        """
        Open one variable and STANDARDIZE its layout: canonical dims
        ('time', 'lat', 'lon'[, level]), pd.DateTime `time` coord, sentinel fills
        masked to NaN. Units stay NATIVE — unit conversion happens in `WIEFile`,
        not here. Returns an unweighted DataArray.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _compute_weights(self) -> xr.DataArray:
        """Grid-cell weight [m2] for this model, per its README (provided raster
        OR computed spherical area), standardized to ('lat', 'lon')."""
        raise NotImplementedError()

    def weights(self) -> xr.DataArray:
        """Model weights [m2], materialized once and cached on the instance.
        Fills are zeroed: a land-only / ocean-masked area raster carries NaN over
        the cells it excludes, and `xarray.weighted()` rejects NaN weights — a
        zero weight drops the cell from the integral, which is what we want."""
        if self._weights_cache is None:
            self._weights_cache = self._compute_weights().fillna(0.0)
        return self._weights_cache

    def weight_dataarray(self, da: xr.DataArray) -> xr.core.weighted.DataArrayWeighted:
        """Wrap `da` in this model's documented weights via xarray `.weighted()`,
        so `.sum()`/`.mean()` over (lat, lon) are one call."""
        return da.weighted(self.weights())

    def to_pgc(self, total: xr.DataArray, variable: str) -> pd.Series:
        """Convert a per-timestep weighted (lat, lon) sum to a Pg C series,
        PRESERVING the file's native cadence (monthly stays monthly — no annual
        collapse). MODEL-SPECIFIC: override when a model's upload units make the
        default wrong (e.g. its flux is not a per-second rate that SPY applies to).
        Default: stock `/PG`; flux rate `×SPY/PG` (a per-timestep annualized rate)."""
        s = total.to_series()
        s = s / const.PG if kind_of(variable) == "stock" else s * const.SPY / const.PG
        s.name = variable
        return s


def kind_of(variable: str) -> str:
    """'stock' or 'flux' — selects the global-integral unit conversion."""
    return "stock" if variable in const.STOCKS else "flux"


def is_annual(variable: str) -> bool:
    """Whether the variable is written at annual cadence (vs monthly) — selects
    the `yr`/`ann` vs `mon` filename token. Independent of stock/flux units (see
    const.ANNUAL): pools are annual, fluxes/states monthly."""
    return variable in const.ANNUAL


def spherical_area(
    obj: xr.Dataset | xr.DataArray, latn: str, lonn: str
) -> xr.DataArray:
    """
    Grid-cell area [m2] from lat/lon centres, assuming a regular spherical grid.

    Used by the models that do *not* ship an area raster (CLASSIC, DLEM, JSBACH,
    JULES cell, VISIT-UT). Models with a provided raster (BiomeE `veg_area.nc`,
    LPX-Bern `gridcell_area.nc`) ignore this. Verbatim from extract.py.
    """
    lat, lon = obj[latn].values, obj[lonn].values
    R = 6.371e6
    dlat, dlon = np.abs(np.gradient(lat)), np.abs(np.gradient(lon))
    band = R**2 * (
        np.sin(np.deg2rad(lat + dlat / 2)) - np.sin(np.deg2rad(lat - dlat / 2))
    )
    return xr.DataArray(
        band[:, None] * np.deg2rad(dlon)[None, :],
        dims=(latn, lonn),
        coords={latn: obj[latn], lonn: obj[lonn]},
    ).astype("float32")


def mask_fill(da: xr.DataArray) -> xr.DataArray:
    """Mask sentinel fills not always declared as `_FillValue` (see FILL_FLOOR)."""
    return da.where(da > const.FILL_FLOOR)


def rename_latlon(da: xr.DataArray, latn: str, lonn: str) -> xr.DataArray:
    """Rename a model's native lat/lon dims to the canonical ('lat', 'lon')."""
    ren = {}
    if latn != "lat":
        ren[latn] = "lat"
    if lonn != "lon":
        ren[lonn] = "lon"
    return da.rename(ren) if ren else da


def standardize(
    da: xr.DataArray, latn: str, lonn: str, time: np.ndarray
) -> xr.DataArray:
    """
    Map a model's raw DataArray onto the canonical standardized form: lat/lon
    renamed to ('lat', 'lon'), a pandas-`datetime64` `time` coord attached
    (PRESERVING the file's native cadence — monthly stays monthly), and
    ('time', 'lat', 'lon') moved to the front while keeping any extra dims
    (e.g. PFT / soil levels). `da` is fill-masked already; `time` is the decoded
    datetime axis from the adapter's `_time(ds)` hook.
    """
    da = rename_latlon(da, latn, lonn)
    da = da.assign_coords(time=("time", np.asarray(time, dtype="datetime64[ns]")))
    front = [d for d in ("time", "lat", "lon") if d in da.dims]
    rest = [d for d in da.dims if d not in front]
    return da.transpose(*front, *rest)


def years_to_datetime(values) -> np.ndarray:
    """Numeric (possibly fractional) *calendar* years -> `datetime64[M]`, keeping
    sub-annual resolution: year = floor(v), month = round(frac * 12) clamped 0..11.
    Annual data (frac == 0) maps to January of each year. Used by the models whose
    time axis is a bare numeric year (LPX-Bern, VISIT-UT)."""
    v = np.asarray(values, dtype="float64")
    years = np.floor(v).astype("int64")
    months = np.clip(np.rint((v - years) * 12).astype("int64"), 0, 11)
    total_months = (years - 1970) * 12 + months  # months since the 1970 epoch
    return np.datetime64("1970-01", "M") + total_months.astype("timedelta64[M]")


def _csv_path(src: Path, start: float | None, end: float | None) -> Path:
    """Cache path for a source .nc + latitude band: the source path mirrored under
    `const.CSV_ROOT` (the `csv/` prefix), '.nc' -> '.csv', suffixed with the band
    ('global' for whole-globe, else '<start>_<end>')."""
    band = "global" if start is None or end is None else f"{start}_{end}"
    rel = src.relative_to(const.DATA_ROOT)
    return const.CSV_ROOT / rel.parent / f"{rel.stem}_{band}.csv"


def cache_csv(method):
    """Lazy CSV cache for a `WIEFile` (lat, lon)->time aggregation returning a
    `pd.Series`. Mirrors the result to a CSV under `const.CSV_ROOT` and recomputes
    only when that CSV is missing or older than the source variable file; on a hit
    it reads the CSV straight back (two stats, zero netCDF reads).

    Freshness keys on the *variable* file (`self.path`) only.
    Use overwrite to recompute the sum. Useful when cache is invalid or methods change.
    """

    @functools.wraps(method)
    def wrapper(self, start=None, end=None, overwrite=False):
        src = Path(self.path)  # pure transform == the file read() opens
        out = _csv_path(src, start, end)
        if (
            not overwrite
            and out.exists()
            and out.stat().st_mtime >= src.stat().st_mtime
        ):
            return pd.read_csv(out, index_col=0, parse_dates=True).iloc[:, 0]
        series = method(self, start, end)
        out.parent.mkdir(parents=True, exist_ok=True)
        series.to_csv(out)
        return series

    return wrapper


@dataclass
class WIEFile:
    """
    Thin, lazy wrapper over one variable's file(s) for one run. Holds identity +
    the model's adapter instance. No s3 access until a data method is called.
    """

    model: str  # canonical model name, e.g. "LPX-Bern"
    experiment: str  # on-disk experiment dir, "1pctCO2" | "overshoot"
    simulation: str  # per-experiment run name, e.g. "bgc", "hl"
    forcing: str  # GCM pattern name, e.g. "ukesm"
    variable: str  # CMIP name, e.g. "cVeg"
    _adapter: WIEAdapter
    factorial: str | None = None  # per-model factorial name, e.g. "baseline", "ndep"

    @property
    def kind(self) -> str:
        return kind_of(self.variable)

    @property
    def units(self) -> str:
        """Native units string from the file header."""
        return self.read().attrs.get("units", "")

    @property
    def path(self) -> str:
        """Resolved bucket path, delegated to the model's adapter."""
        return str(
            self._adapter.path(
                self.experiment,
                self.simulation,
                self.forcing,
                self.factorial,
                self.variable,
            )
        )

    def read(self) -> xr.DataArray:
        """Standardized, *lazy* DataArray for this variable (canonical dims,
        pandas-datetime time coord at native cadence, NaN fills, native units).

        Raises whatever opening the file raises (FileNotFoundError for a combo
        that wasn't uploaded): read() is the single source of truth for what
        exists, so the caller can catch and report it. path() never pre-judges.

        TODO(virtualizarr): when a reference sidecar exists in `references/`, open
        through the committed virtual-zarr store instead of re-opening raw netCDF.
        """

        if not self.exists():
            pth = self._adapter.path(
                self.experiment,
                self.simulation,
                self.forcing,
                self.factorial,
                self.variable,
            )
            raise FileNotFoundError(
                f"Missing file for {pth}. Requested: {self.experiment}, {self.simulation}, {self.forcing}, {self.factorial}, {self.variable}"
            )

        return self._adapter.read(
            self.experiment,
            self.simulation,
            self.forcing,
            self.factorial,
            self.variable,
        )

    def weighted_dataarray(
        self, da: xr.DataArray | None = None
    ) -> xr.core.weighted.DataArrayWeighted:
        """Wrap the data in this model's documented area weights, so a sum over
        (lat, lon) integrates the per-m2 quantity. Delegated to the adapter."""
        if da is None:
            da = self.read()
        return self._adapter.weight_dataarray(da)

    def exists(self):
        try:
            pth = self._adapter.path(
                self.experiment,
                self.simulation,
                self.forcing,
                self.factorial,
                self.variable,
            )
        except MissingFactorialError:
            return False  # model doesn't provide this factorial -> treat as not-there
        return os.path.isfile(pth)

    @cache_csv
    def latitudinal_sum(
        self,
        start: float | None = None,
        end: float | None = None,
        overwrite: bool = False,
    ) -> pd.Series:
        """Area-weighted total as a Pg C series at the file's native cadence
        (monthly stays monthly). With no band, sums the whole globe; pass
        (start, end) degrees to restrict to a latitude band. The unit conversion is
        delegated to the model's adapter (`to_pgc`).

        Wrapped by `@cache_csv`: the result is mirrored to a CSV under
        `const.CSV_ROOT` and reused until the source .nc is newer or overwrite is True.
        """
        da = self.read()
        if start is not None and end is not None:
            band = da.sel(lat=slice(start, end))
            if band.sizes.get("lat", 0) == 0:  # handle descending-lat grids
                band = da.sel(lat=slice(end, start))
            da = band
        total = self.weighted_dataarray(da).sum(("lat", "lon"))
        return self._adapter.to_pgc(total, self.variable)

    def __repr__(self) -> str:
        if self.factorial is None:
            return (
                f"WIEFile({self.experiment}.{self.simulation}.{self.model}."
                f"{self.forcing}.{self.variable})"
            )
        else:
            return (
                f"WIEFile({self.experiment}.{self.simulation}.{self.model}."
                f"{self.forcing}.{self.factorial}.{self.variable})"
            )
