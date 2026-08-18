"""

This package acts as a wrapper on top of WIEMIP submissions to ease analysis.
It can be run on the WIEMIP Jupyterhub or installed locally. Each model (e.g., CLM)
gets its own implementation of the [WIEAdapter](core.html#WIEAdapter) class, which contains
logic on how to compute weighted aggregations and how to construct paths for WIEMIP variables.
Each variable is returned as a [WIEFile](core.html#WIEFile), which contains methods like exists(), latitudinal_sum(),
read(), and so forth. All functions are documented on this site.

Quick start
-----------

    import wiemip_registry as wr

    cveg = wr.retrieve_one_pct_variable(
        model="CLASSIC", forcing="ukesm", simulation="cou",
        factorial="baseline", variable="cVeg",
    )

    cveg.path                       # which file this resolves to
    cveg.exists()                   # is it actually on the bucket
    data = cveg.read()              # xarray.DataArray, native units
    series = cveg.latitudinal_sum() # global total, Pg C


Please see the API documentation for more detailed descriptions of functions and how to use them.
Of particular interest may be `land_carbon_stock`, `retrieve_one_pct_variable`, `retrieve_overshoot_variable`,
and the description of the `WIEFile` class.

The `WIEFile` class is returned from every `retrieve` call and includes key methods that operate on the underlying data,
including weighting the data in the way the modeling group intended.

Below are some helpful links to key functions and objects:

- [WIEFile](https://wiemip.github.io/docs/api/wiemip_registry/core.html#WIEFile)

- [How csv caching works](https://wiemip.github.io/docs/api/wiemip_registry/core.html#cache_csv)

- See each model's one percent CO2 factorials by clicking on the model on the left hand side of the page and navigating to `FACTORIALS`.
[Here are CLASSIC's factorials](https://wiemip.github.io/docs/api/wiemip_registry/CLASSIC.html#CLASSIC.FACTORIALS).

- The [`core` submodule contains](https://wiemip.github.io/docs/api/wiemip_registry/core.html) documentation for many of the important functions.

"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

import wiemip_registry

try:
    __version__ = _pkg_version(
        "wiemip-data-processing"
    )  # git-derived, set at build by hatch-vcs
except PackageNotFoundError:  # running from a raw source tree, not installed
    __version__ = "0+unknown"

from wiemip_registry.core import WIEFile
import wiemip_registry.const as const
from wiemip_registry.adapters import adapters, models
from wiemip_registry.variables import VARIABLES as variables
from wiemip_registry.variable_overrides import extra_variables
import warnings

one_percent_simulations = [s.name for s in const.OnePctSimulation]
overshoot_simulations = [s.name for s in const.OvershootSimulation]
gcm_patterns = [m.name for m in const.GCMPattern]
variables = list(dict.fromkeys([*variables, *extra_variables]))
factorials = [f.name for f in const.Factorial]

# Series name returned by land_carbon_stock().
LAND_CARBON_STOCK_NAME = "land_carbon_PgC"


def _warn_factorial(
    model: str, forcing: str, simulation: str, factorial: str, variable: str
):
    accepted = [c.name.lower() for c in const.Factorial]
    if factorial.lower() not in accepted:
        warnings.warn(
            f"Factorial {factorial} for {model} {forcing} {simulation} not in the default list: {accepted}."
            f" Your factorial will be passed directly to the naming convention adapter for {model}"
        )


def _sanity_check(model: str, forcing: str, simulation: str, variable: str):
    if model not in models:
        raise core.MissingModelError(
            f"Model {model} is not in the set of registered models. Supported models: {'|'.join(models)}"
        )
    if forcing not in gcm_patterns:
        raise core.MissingForcingError(
            f"GCM pattern {forcing} is not in the list of GCM patterns."
            f" Supported GCM patterns: {'|'.join(gcm_patterns)}"
        )
    if simulation not in one_percent_simulations + overshoot_simulations:
        raise core.MissingSimulationError(
            f"Simulation {simulation} is not in the list of simulations. "
            f"Supported simulations: {'|'.join(one_percent_simulations + overshoot_simulations)}"
        )
    if variable not in variables:
        raise core.MissingVariableError(
            f"Variable {variable} is not in the list of WIEMIP variables."
            " Use import wiemip_registry.variables; print(variables.VARIABLES) to see a listing."
        )


def _land_carbon_overshoot(
    model: str,
    forcing: str,
    simulation: str,
    land_carbon_variables: list[str],
    factorial: str | None = None,
    lat_start: float | None = None,
    lat_end: float | None = None,
):
    _land_stock = None
    for variable in land_carbon_variables:
        if _land_stock is None:
            _land_stock = retrieve_overshoot_variable(
                model=model,
                forcing=forcing,
                simulation=simulation,
                variable=variable,
                factorial=factorial,
            ).latitudinal_sum(start=lat_start, end=lat_end)
        else:
            _land_stock += retrieve_overshoot_variable(
                model=model,
                forcing=forcing,
                simulation=simulation,
                variable=variable,
                factorial=factorial,
            ).latitudinal_sum(start=lat_start, end=lat_end)
    return _land_stock


def _land_carbon_one_pct(
    model: str,
    forcing: str,
    simulation: str,
    land_carbon_variables: list[str],
    factorial: str,
    lat_start: float | None = None,
    lat_end: float | None = None,
):
    _land_stock = None
    for variable in land_carbon_variables:
        if _land_stock is None:
            _land_stock = retrieve_one_pct_variable(
                model=model,
                forcing=forcing,
                simulation=simulation,
                variable=variable,
                factorial=factorial,
            ).latitudinal_sum(start=lat_start, end=lat_end)
        else:
            _land_stock += retrieve_one_pct_variable(
                model=model,
                forcing=forcing,
                simulation=simulation,
                variable=variable,
                factorial=factorial,
            ).latitudinal_sum(start=lat_start, end=lat_end)
    return _land_stock


def _check_land_carbon_variables(model: str) -> list:

    try:
        _land_carbon_variables = wiemip_registry.adapters[model].land_carbon_variables()
    except KeyError:
        raise core.MissingModelError(
            f"Model {model} is not in the list of registered models. "
            f"Supported models: {'|'.join(models)}"
        )
    return _land_carbon_variables


def land_carbon_variables(model: str) -> list[str]:
    return _check_land_carbon_variables(model)


def land_carbon_stock(
    experiment: str,
    model: str,
    forcing: str,
    simulation: str,
    factorial: str = "baseline",
    lat_start: float | None = None,
    lat_end: float | None = None,
):
    """Compute the land carbon stock for a model. Requires experiment (1pctCO2 or overshoot),
    the model (CLM, etc), the forcing (ukesm, stable, etc), the simulation (cou, bgc, ctrl),
    and finally the optional factorial argument, which is typically only used for 1pctCO2 simulations.
    """
    _land_carbon_variables = _check_land_carbon_variables(model)

    if experiment == "1pctCO2":
        land_carbon = _land_carbon_one_pct(
            model,
            forcing,
            simulation,
            _land_carbon_variables,
            factorial,
            lat_start,
            lat_end,
        )
    elif experiment == "overshoot":
        land_carbon = _land_carbon_overshoot(
            model,
            forcing,
            simulation,
            _land_carbon_variables,
            factorial,
            lat_start,
            lat_end,
        )
    else:
        raise core.InvalidExperimentError(
            "Experiment must be one of 1pctCO2 or overshoot"
        )

    # The accumulators use `+=`, which keeps the first component's name.
    return land_carbon.rename(LAND_CARBON_STOCK_NAME)


def retrieve_one_pct_variable(
    model: str, forcing: str, simulation: str, factorial: str, variable: str
) -> WIEFile:
    """Retrieve a one percent variable from the WIEMIP Wasabi bucket.
    Forcing is one of `stable`, `ukesm`, `ipsl`, or `gfdl`, simulation can be bgc/cou/ctrl/rad, factorial can be baseline (for the default
    simulation, noFire, noPermafrost, or the custom factorial name for, say, JULES.
    Variables one of the WIEMIP variables from the request.
    Invalid combinations - like LPJ-EOSIM, stable, cou, noFire, vegC - are rejected."""

    simulation = simulation.lower()
    forcing = forcing.lower()

    _sanity_check(model, forcing, simulation, variable)

    _warn_factorial(model, forcing, simulation, factorial, variable)

    if simulation not in (
        const.OnePctSimulation.bgc.name,
        const.OnePctSimulation.cou.name,
        const.OnePctSimulation.ctrl.name,
        const.OnePctSimulation.rad.name,
        const.OnePctSimulation.rad_ndep.name,
        const.OnePctSimulation.bgc_ndep.name,
        const.OnePctSimulation.cou_ndep.name,
        const.OnePctSimulation.ctrl_ndep.name,
    ):
        raise ValueError(
            "One percent simulations only include ctrl, bgc, cou, and rad, or their transient "
            "nitrogen deposition variants ctrl_ndep, bgc_ndep, cou_ndep, and rad_ndep."
        )

    return WIEFile(
        model=model,
        experiment=const.ONE_PERCENT_CO2_KEY,
        forcing=forcing,
        simulation=simulation,
        factorial=factorial,
        variable=variable,
        _adapter=adapters[model],
    )


def retrieve_overshoot_variable(
    model: str,
    forcing: str,
    simulation: str,
    variable: str,
    factorial: str | None = None,
) -> WIEFile:
    """
    Retrieve an overshoot variable from the WIEMIP Wasabi bucket. Forcing can be one of ukesm/ipsl/gfdl,
    simulation can be one of hist/ctrl/vl/ml/ml_cf and so on. See const.py for Enum classes containing the
    overshoot simulations.
    Factorial is always None except for models like JULES which have submitted custom factorials with
    unique names. In this case, the name of the factorial will be passed through to the path() method
    without checking against the WIEMIP vocabulary.
    """

    simulation = simulation.lower()
    forcing = forcing.lower()

    _sanity_check(model, forcing, simulation, variable)

    # Only JULES repeated the overshoot scenarios under several configurations; every
    # other group ran one, so the factorial stays None and their adapters ignore it.
    if factorial is not None:
        _warn_factorial(model, forcing, simulation, factorial, variable)

    # Validate against the exported vocabulary itself, so it cannot drift from what
    # this function accepts — the handwritten tuple here had dropped hist_ctrl, which
    # made looping over wr.overshoot_simulations raise.
    if simulation not in overshoot_simulations:
        raise ValueError(
            f"Overshoot simulations only include {', '.join(overshoot_simulations)}."
        )

    return WIEFile(
        model=model,
        experiment="overshoot",
        forcing=forcing,
        simulation=simulation,
        variable=variable,
        factorial=factorial,
        _adapter=adapters[model],
    )
