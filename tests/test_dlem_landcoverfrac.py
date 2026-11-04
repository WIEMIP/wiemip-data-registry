import numpy as np
import xarray as xr

import wiemip_registry as wr
from wiemip_registry.DLEM.convert import DLEM

LOOSE_FILE = "overshoot/output/DLEM/DLEM_Land_Cover_overshoot.nc"


def test_every_overshoot_run_spells_the_loose_file():
    for forcing, simulation in (
        ("ukesm", "hist"),
        ("ukesm", "ctrl"),
        ("ipsl", "hl_cf"),
    ):
        f = wr.retrieve_overshoot_variable("DLEM", forcing, simulation, "landCoverFrac")
        assert f.path.endswith(LOOSE_FILE)


def test_landcoverfrac_reads_without_time(tmp_path, monkeypatch):
    # Layout of the 2026-11-04 upload: fraction(time=1, land_cover=9, lat, lon), units 1.
    nc = tmp_path / "DLEM_Land_Cover_overshoot.nc"
    values = np.zeros((1, 9, 2, 3))
    values[0, 3] = 1.0
    values[0, :, 0, 0] = -9999.0
    xr.Dataset(
        {
            "fraction": (
                ("time", "land_cover", "lat", "lon"),
                values,
                {"_FillValue": -9999.0, "units": "1"},
            )
        },
        coords={
            "time": ("time", [173.0], {"units": "years since 1850-01-01 00:00:00"}),
            "land_cover": (
                "land_cover",
                np.arange(1, 10),
                {
                    "flag_meanings": "cropland pasture rangeland forest shrubland grassland others urban bare_land"
                },
            ),
            "lat": [88.25, 87.75],
            "lon": [-179.75, -179.25, -178.75],
        },
    ).to_netcdf(nc)
    adapter = DLEM()
    monkeypatch.setattr(adapter, "path", lambda *args: str(nc))

    da = adapter.read("overshoot", "hist", "ukesm", None, "landCoverFrac")

    assert da.name == "landCoverFrac"
    assert da.dims == ("lat", "lon", "land_cover")
    assert np.isnan(da.isel(lat=0, lon=0)).all()
    assert da.sum("land_cover").values[1, 1] == 1.0
    assert da.land_cover.attrs["flag_meanings"].split()[3] == "forest"
