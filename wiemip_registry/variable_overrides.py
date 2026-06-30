"""Runtime variable-name overrides, merged into `wr.variables` at import.

Hand-maintained, and intentionally SEPARATE from the auto-generated `variables.py`
(which `.github/workflows/_sync_variables.py` overwrites wholesale from the live
WIE-MIP data request — anything added there is lost on the next sync).

Use this for variable names that exist on the bucket but are absent from the
current request: typically names SUPERSEDED by a later request revision whose
files were already uploaded. Listing them keeps them iterable and
coverage-checkable (`wr.variables`) without fighting the generator.

The variable axis is still free-form — this only affects iteration/coverage.
"""

EXTRA_VARIABLES = [
    "nSoil",  # total soil N — superseded by nOrgSoil + nInorgSoil; files still on bucket (JSBACH, LPX-Bern)
    "nSoilpft",  # per-PFT total soil N — superseded by nOrgSoilpft; files still on bucket (JSBACH, LPX-Bern)
]
