import pytest

import wiemip_registry as wr
from wiemip_registry import core

ROOT = "overshoot/output/BiomeE/"


@pytest.mark.parametrize("forcing", ["ukesm", "gfdl", "ipsl"])
def test_hist_pins_the_uploaded_ukesm_token(forcing):
    f = wr.retrieve_overshoot_variable("BiomeE", forcing, "hist", "cVeg")
    assert f.path.endswith(ROOT + "BiomeE_ukesm_hist_cVeg_yr_05_noCH4.nc")


def test_hist_monthly_cadence():
    f = wr.retrieve_overshoot_variable("BiomeE", "ukesm", "hist", "gpp")
    assert f.path.endswith(ROOT + "BiomeE_ukesm_hist_gpp_mon_05_noCH4.nc")


def test_overshoot_ch4_is_provisional():
    f = wr.retrieve_overshoot_variable("BiomeE", "ukesm", "hist", "ch4")
    assert not f.exists()
    with pytest.raises(core.ProvisionalDataError):
        f.read()
