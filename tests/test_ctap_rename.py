import pytest

import wiemip_registry as wr


@pytest.mark.parametrize(
    "model, simulation, on_disk",
    [
        ("LPJ_EOSIM", "hl_ctap", "LPJ_EOSIM_ukesm_hl_cf"),
        ("JULES", "vl_ctap", "ukesm_vl-cf"),
        ("CLM_FATES", "hl_ctap", "FATES_ukesm_hl-cf"),
        ("CLM", "ml_ctap", "hh_ukesm_ml_cf"),
    ],
)
def test_ctap_request_spells_the_cf_files(model, simulation, on_disk):
    # The CTAP runs were uploaded as `_cf` counterfactuals, so the new names must
    # still resolve to those files.
    f = wr.retrieve_overshoot_variable(model, "ukesm", simulation, "cVeg")
    assert f.simulation == simulation
    assert all(on_disk in p for p in f.paths)


def test_old_cf_name_warns_and_resolves_to_the_same_files():
    new = wr.retrieve_overshoot_variable("LPJ_EOSIM", "ukesm", "hl_ctap", "cVeg")
    with pytest.warns(FutureWarning, match="renamed 'hl_ctap'"):
        old = wr.retrieve_overshoot_variable("LPJ_EOSIM", "ukesm", "hl_cf", "cVeg")
    assert old.simulation == "hl_ctap"
    assert old.paths == new.paths


def test_cf_names_left_the_vocabulary():
    assert {"hl_ctap", "ml_ctap", "vl_ctap", "vl_cf_polmip"} <= set(
        wr.overshoot_simulations
    )
    assert not {"hl_cf", "ml_cf", "vl_cf"} & set(wr.overshoot_simulations)


def test_cfuel_variable_is_not_renamed():
    # CLM's `cfuelTotal` follows the sim token (`..._hl_cfuelTotal`), so the rename
    # must map whole simulation names, never a `_cf` substring.
    f = wr.retrieve_overshoot_variable("CLM", "ukesm", "hl", "cfuelTotal")
    assert all("ctap" not in p for p in f.paths)
