import pytest

from wiemip_registry import core
from wiemip_registry.CLM.convert import CLM

N_FLUXES = ["fNdep", "fNup", "fNnitri", "fNloss", "fNleach", "nInorgSoil"]


@pytest.mark.parametrize("variable", N_FLUXES)
def test_no_nitrogen_runs_serve_no_nitrogen_fluxes(variable):
    with pytest.raises(core.MissingVariableError):
        CLM().one_pct_path("bgc", "ukesm", "noNitrogen", variable)


@pytest.mark.parametrize("factorial", ["baseline", "flat"])
def test_other_runs_still_serve_them(factorial):
    assert CLM().one_pct_path("bgc", "ukesm", factorial, "fNdep").endswith("_fNdep.nc")


def test_no_nitrogen_runs_still_serve_carbon():
    assert (
        CLM()
        .one_pct_path("bgc", "ukesm", "noNitrogen", "cVeg")
        .endswith("_cVeg.1850-2000.nc")
    )
