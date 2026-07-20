from importlib.metadata import PackageNotFoundError, version as _pkg_version

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


def retrieve_one_pct_variable(
    model: str, forcing: str, simulation: str, factorial: str, variable: str
) -> WIEFile:

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
    model: str, forcing: str, simulation: str, variable: str
):

    simulation = simulation.lower()
    forcing = forcing.lower()

    _sanity_check(model, forcing, simulation, variable)

    if simulation not in (
        const.OvershootSimulation.hist.name,
        const.OvershootSimulation.ctrl.name,
        const.OvershootSimulation.vl.name,
        const.OvershootSimulation.vl_cf.name,
        const.OvershootSimulation.l.name,
        const.OvershootSimulation.hl.name,
        const.OvershootSimulation.hl_cf.name,
        const.OvershootSimulation.m.name,
    ):
        raise ValueError(
            "Overshoot simulations only include hist, ctrl, vl, vl_cf, l, hl, "
            "hl_cf, and m."
        )

    return WIEFile(
        model=model,
        experiment="overshoot",
        forcing=forcing,
        simulation=simulation,
        variable=variable,
        _adapter=adapters[model],
    )
