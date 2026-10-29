import numpy as np
import pandas as pd
import pytest
import xarray as xr

from wiemip_registry.EDv3.convert import EDv3
from wiemip_registry.LPJmL6.convert import LPJmL6
from wiemip_registry.VISIT_UT.convert import VISIT_UT

YEARS = np.arange(1849, 2002)

CASES = {
    "EDv3": (
        EDv3,
        "latitude",
        "longitude",
        xr.DataArray(
            365.0 * (YEARS - 1849) + 181,
            dims="time",
            attrs={"units": "days since 1849-01-01", "calendar": "noleap"},
        ),
    ),
    "VISIT_UT": (VISIT_UT, "lat", "lon", YEARS.astype(float)),
    "LPJmL6": (LPJmL6, "lat", "lon", pd.to_datetime([f"{y}-07-01" for y in YEARS])),
}


def _adapter_reading(tmp_path, monkeypatch, model):
    adapter_class, latn, lonn, time = CASES[model]
    nc = tmp_path / "cVeg.nc"
    xr.Dataset(
        {"cVeg": (("time", latn, lonn), np.ones((len(YEARS), 1, 1)))},
        coords={"time": time, latn: [10.25], lonn: [20.25]},
    ).to_netcdf(nc)
    adapter = adapter_class()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))
    return adapter


@pytest.mark.parametrize("model", CASES)
def test_one_pct_is_clipped_to_1850_2000(tmp_path, monkeypatch, model):
    adapter = _adapter_reading(tmp_path, monkeypatch, model)

    da = adapter.read("1pctCO2", "bgc", "ukesm", "baseline", "cVeg")

    assert list(da["time"].dt.year.values) == list(range(1850, 2001))


@pytest.mark.parametrize("model", ["EDv3", "VISIT_UT"])
def test_overshoot_is_not_clipped(tmp_path, monkeypatch, model):
    adapter = _adapter_reading(tmp_path, monkeypatch, model)

    da = adapter.read("overshoot", "hist", "ukesm", None, "cVeg")

    assert da.sizes["time"] == len(YEARS)
