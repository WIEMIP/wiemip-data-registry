import numpy as np
import xarray as xr

from wiemip_registry.ORCHIDEE_MICT_CALIPSO.convert import ORCHIDEE_MICT_CALIPSO

POOLS = np.array([1.0, 2.0, 4.0])
VEGET_FRACTION = np.array([0.25, 0.75])


def _adapter_reading(tmp_path, monkeypatch):
    time = ("time_counter", [0.0], {"units": "seconds since 1850-01-01 00:00:00"})
    files = {
        "cSoilpft": tmp_path / "cSoilpft.nc",
        "maxvegetfrac": tmp_path / "maxvegetfrac.nc",
    }
    xr.Dataset(
        {
            "cSoilpft": (
                ("time_counter", "pool", "veget", "lat", "lon"),
                np.broadcast_to(POOLS[None, :, None, None, None], (1, 3, 2, 1, 1)),
                {"units": "kg m-2"},
            )
        },
        coords={
            "time_counter": time,
            "pool": ["a", "s", "p"],
            "lat": [0.5],
            "lon": [0.5],
        },
    ).to_netcdf(files["cSoilpft"])
    xr.Dataset(
        {
            "maxvegetfrac": (
                ("time_counter", "veget", "lat", "lon"),
                VEGET_FRACTION[None, :, None, None],
            )
        },
        coords={"time_counter": time, "lat": [0.5], "lon": [0.5]},
    ).to_netcdf(files["maxvegetfrac"])
    adapter = ORCHIDEE_MICT_CALIPSO()
    monkeypatch.setattr(adapter, "path", lambda *args: str(files[args[-1]]))
    return adapter


def test_soil_carbon_per_pft_sums_its_pools(tmp_path, monkeypatch):
    adapter = _adapter_reading(tmp_path, monkeypatch)

    da = adapter.read("1pctCO2", "bgc", "stable", "baseline", "cSoilpft")

    assert "pool" not in da.dims
    assert da.sizes["veget"] == 2
    assert da.isel(time=0, lat=0, lon=0).values.tolist() == [7.0, 7.0]
    assert da.attrs["units"] == "kg m-2"


def test_soil_carbon_weights_each_pft_by_its_cover(tmp_path, monkeypatch):
    adapter = _adapter_reading(tmp_path, monkeypatch)

    da = adapter.read("1pctCO2", "bgc", "stable", "baseline", "cSoil")

    assert set(da.dims) == {"time", "lat", "lon"}
    assert float(da.isel(time=0, lat=0, lon=0)) == 7.0
