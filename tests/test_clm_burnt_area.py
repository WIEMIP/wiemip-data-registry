import numpy as np
import pytest
import xarray as xr

from wiemip_registry.CLM.convert import CLM


def test_burnt_area_total_becomes_percent_of_the_vegetated_area(tmp_path, monkeypatch):
    path = tmp_path / "burntareaTotal.nc"
    rate_per_second, percent_vegetated = 1e-8, 100.0
    time = xr.DataArray(
        np.full(2, -2147483647.0),
        dims="time",
        attrs={"units": "hours since 1850-01-16 12:00:00.000000"},
    )
    xr.Dataset(
        {
            "burntareaTotal": (
                ("time", "lat", "lon"),
                np.full(
                    (2, 1, 1), rate_per_second / percent_vegetated, dtype="float32"
                ),
                {"units": "fraction"},
            )
        },
        coords={"time": time, "lat": [10.0], "lon": [20.0]},
    ).to_netcdf(path)
    monkeypatch.setattr(CLM, "_files", lambda self, *args: [str(path)])

    da = CLM().read("1pctCO2", "cou", "gfdl", "baseline", "burntareaTotal")

    january, february = (float(da.isel(time=i, lat=0, lon=0)) for i in (0, 1))
    assert january == pytest.approx(rate_per_second * 31 * 86400 * 100, rel=1e-5)
    assert february == pytest.approx(rate_per_second * 28 * 86400 * 100, rel=1e-5)
    assert da.attrs["units"] == "%"
    assert da.dtype == "float32"
    assert da.name == "burntareaTotal"
