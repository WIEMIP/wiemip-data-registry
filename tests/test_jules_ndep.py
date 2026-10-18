import pytest

import wiemip_registry as wr


@pytest.mark.parametrize(
    "simulation, forcing",
    [
        ("bgc_ndep", "stable"),
        ("ctrl_ndep", "stable"),
        ("cou_ndep", "ukesm"),
        ("rad_ndep", "gfdl"),
    ],
)
def test_jules_ndep_does_not_fall_back_to_bgc(simulation, forcing):
    # JULES uploaded no _ndep runs, so these must spell a path of their own (and miss
    # on read) rather than resolve to the bgc files.
    bgc = wr.retrieve_one_pct_variable("JULES", "stable", "bgc", "baseline", "cVeg")
    ndep = wr.retrieve_one_pct_variable(
        "JULES", forcing, simulation, "baseline", "cVeg"
    )
    assert ndep.path != bgc.path
    assert "_ndep" in ndep.path
