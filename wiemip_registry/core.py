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
from abc import ABC
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import wiemip_registry.const as const


class WIEAdapter(ABC):
    """
    Contract that each model must fill out. This converts whatever naming
    convention was uploaded to the WIE-MIP S3 bucket into something callable in
    Python.

    Subclasses implement the three abstract hooks (`path`, `read`,
    `_compute_weights`) and may override the candidate-space class attributes. The
    namespace is enumerated by `available()`, which takes the cartesian product of
    those candidate lists and KEEPS ONLY the combinations whose file actually
    exists on the bucket — no hardcoded per-model "which files exist" schema.
    """

    model: str

    # Candidate space that EXISTENCE then filters (see `available()`). Generous
    # defaults — override only if a model's candidate space genuinely differs.
    # `variable` is never an Enum (CMIP names).
    experiments = [const.Experiment.one_percent_co2]
    simulations = [const.Simulation.bgc, const.Simulation.cou, const.Simulation.ctrl]
    available_gcm_patterns = [const.GCMPattern.ukesm]
    factorials = [const.Factorial.baseline]
    variables = ["cVeg", "cSoil", "cLitter", "gpp", "npp", "rh", "nbp", "fFire"]

    _weights_cache: xr.DataArray | None = None

    # --- abstract, model-specific hooks ------------------------------------ #
    @abc.abstractmethod
    def path(self, experiment: const.Experiment, simulation: const.Simulation,
              forcing: const.GCMPattern, factorial: const.Factorial, variable: str) -> str:
        """Path to the .nc file on a mounted S3 bucket. Assumes you're using s3fs."""
        raise NotImplementedError()

    @abc.abstractmethod
    def read(self, experiment: const.Experiment, simulation: const.Simulation,
             forcing: const.GCMPattern, factorial: const.Factorial, variable: str) -> xr.DataArray:
        """
        Open one variable and STANDARDIZE its layout: canonical dims
        ('time', 'lat', 'lon'[, level]), integer-year `time` coord, sentinel fills
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
        """Model weights [m2], materialized once and cached on the instance."""
        if self._weights_cache is None:
            self._weights_cache = self._compute_weights()
        return self._weights_cache

    def weight_dataarray(self, da: xr.DataArray) -> xr.core.weighted.DataArrayWeighted:
        """Wrap `da` in this model's documented weights via xarray `.weighted()`,
        so `.sum()`/`.mean()` over (lat, lon) are one call."""
        return da.weighted(self.weights())

    def available(self) -> list[tuple]:
        """Resolvable (experiment, simulation, forcing, factorial, variable)
        tuples: the cartesian product of the candidate lists, KEPT ONLY where the
        file actually exists on the bucket. No hardcoded per-model schema — upload
        more files and they show up automatically. Enums for every level except
        `variable`."""
        out = []
        for e in self.experiments:
            for s in self.simulations:
                for g in self.available_gcm_patterns:
                    for f in self.factorials:
                        for v in self.variables:
                            try:
                                p = self.path(e, s, g, f, v)
                            except (KeyError, NotImplementedError):
                                continue          # model can't construct that combo
                            if Path(p).exists():
                                out.append((e, s, g, f, v))
        return out

    def to_annual_pgc(self, total: xr.DataArray, variable: str) -> pd.Series:
        """Collapse a per-timestep weighted (lat, lon) sum to an annual Pg C
        series. MODEL-SPECIFIC: override when a model's upload cadence/units make
        the default wrong (e.g. it didn't upload a monthly rate that SPY applies
        to). Default: monthly rate × SPY for fluxes, annual mean for stocks."""
        s = total.to_series()
        s = s.groupby(s.index).mean()            # monthly -> annual (mean rate / mean stock)
        s = s / const.PG if kind_of(variable) == "stock" else s * const.SPY / const.PG
        s.name = variable
        return s


def kind_of(variable: str) -> str:
    """'stock' or 'flux' — selects the global-integral unit conversion."""
    return "stock" if variable in const.STOCKS else "flux"


def spherical_area(obj: xr.Dataset | xr.DataArray, latn: str, lonn: str) -> xr.DataArray:
    """
    Grid-cell area [m2] from lat/lon centres, assuming a regular spherical grid.

    Used by the models that do *not* ship an area raster (CLASSIC, DLEM, JSBACH,
    JULES cell, VISIT-UT). Models with a provided raster (BiomeE `veg_area.nc`,
    LPX-Bern `gridcell_area.nc`) ignore this. Verbatim from extract.py.
    """
    lat, lon = obj[latn].values, obj[lonn].values
    R = 6.371e6
    dlat, dlon = np.abs(np.gradient(lat)), np.abs(np.gradient(lon))
    band = R**2 * (np.sin(np.deg2rad(lat + dlat / 2)) - np.sin(np.deg2rad(lat - dlat / 2)))
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


def standardize(da: xr.DataArray, latn: str, lonn: str, years: np.ndarray) -> xr.DataArray:
    """
    Map a model's raw DataArray onto the canonical standardized form: lat/lon
    renamed to ('lat', 'lon'), an integer-year `time` coord attached, and
    ('time', 'lat', 'lon') moved to the front while PRESERVING any extra dims
    (e.g. PFT / soil levels). `da` is expected to be fill-masked already.
    """
    da = rename_latlon(da, latn, lonn)
    da = da.assign_coords(time=("time", np.asarray(years).astype(int)))
    front = [d for d in ("time", "lat", "lon") if d in da.dims]
    rest = [d for d in da.dims if d not in front]
    return da.transpose(*front, *rest)


@dataclass
class WIEFile:
    """
    Thin, lazy wrapper over one variable's file(s) for one run. Holds identity +
    the model's adapter instance. No s3 access until a data method is called.
    """

    model: str                     # canonical model name, e.g. "LPX-Bern"
    experiment: const.Experiment
    simulation: const.Simulation
    forcing: const.GCMPattern
    factorial: const.Factorial
    variable: str                  # CMIP name, e.g. "cVeg"
    _adapter: WIEAdapter

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
        return str(self._adapter.path(
            self.experiment, self.simulation, self.forcing, self.factorial, self.variable))

    def read(self) -> xr.DataArray:
        """Standardized, *lazy* DataArray for this variable (canonical dims,
        integer-year time coord, NaN fills, native units).

        TODO(virtualizarr): when a reference sidecar exists in `references/`, open
        through the committed virtual-zarr store instead of re-opening raw netCDF.
        """
        return self._adapter.read(
            self.experiment, self.simulation, self.forcing, self.factorial, self.variable)

    def weighted_dataarray(self, da: xr.DataArray | None = None) -> xr.core.weighted.DataArrayWeighted:
        """Wrap the data in this model's documented area weights, so a sum over
        (lat, lon) integrates the per-m2 quantity. Delegated to the adapter."""
        if da is None:
            da = self.read()
        return self._adapter.weight_dataarray(da)

    def latitudinal_sum(self, start: float | None = None, end: float | None = None) -> pd.Series:
        """Area-weighted total as an annual Pg C series. With no band, sums the
        whole globe; pass (start, end) degrees to restrict to a latitude band. The
        annual/unit conversion is delegated to the model's adapter (`to_annual_pgc`).

        TODO(cache): look up the precomputed series in the `wiemip-csv` mirror
        bucket first, and write computed results back.
        """
        da = self.read()
        if start is not None and end is not None:
            band = da.sel(lat=slice(start, end))
            if band.sizes.get("lat", 0) == 0:        # handle descending-lat grids
                band = da.sel(lat=slice(end, start))
            da = band
        total = self.weighted_dataarray(da).sum(("lat", "lon"))
        return self._adapter.to_annual_pgc(total, self.variable)

    def __repr__(self) -> str:
        return (f"WIEFile({self.experiment.name}.{self.simulation.name}.{self.model}."
                f"{self.forcing.name}.{self.factorial.name}.{self.variable})")
