from wiemip_registry.core import WIEFile
import wiemip_registry.const as const
from wiemip_registry.adapters import adapters
from wiemip_registry.variables import VARIABLES
from wiemip_registry.variable_overrides import EXTRA_VARIABLES


def retrieve_one_pct_variable(
    model: str, forcing: str, simulation: str, factorial: str, variable: str
) -> WIEFile:

    simulation = simulation.lower()
    forcing = forcing.lower()

    if simulation not in (
        const.Simulation.bgc.name,
        const.Simulation.cou.name,
        const.Simulation.ctrl.name,
        const.Simulation.rad.name,
    ):
        raise ValueError(
            "One percent simulations only include ctrl, bgc, cou, and rad."
        )

    return WIEFile(
        model=model,
        experiment="1pctCO2",
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

    if simulation not in (
        const.Simulation.hist.name,
        const.Simulation.ctrl.name,
        const.Simulation.vl.name,
        const.Simulation.vl_cf.name,
        const.Simulation.l.name,
        const.Simulation.hl.name,
        const.Simulation.hl_cf.name,
        const.Simulation.m.name,
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


models = adapters.keys()
one_percent_simulations = ["ctrl", "bgc", "cou", "rad"]
overshoot_simulations = ["hist", "ctrl", "vl", "vl_cf", "l", "hl", "hl_cf", "m"]
gcm_patterns = [m.name for m in const.GCMPattern]
variables = list(dict.fromkeys([*VARIABLES, *EXTRA_VARIABLES]))
