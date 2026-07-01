from wiemip_registry.core import WIEFile
import wiemip_registry.const as const
from wiemip_registry.adapters import adapters
from wiemip_registry.variables import VARIABLES
from wiemip_registry.variable_overrides import EXTRA_VARIABLES


def retrieve_one_pct_variable(
    model, forcing, simulation, factorial, variable
) -> WIEFile:
    return WIEFile(
        model=model,
        experiment=const.Experiment.one_percent_co2,
        forcing=forcing,
        simulation=simulation,
        factorial=factorial,
        variable=variable,
        _adapter=adapters[model],
    )


def retrieve_overshoot_variable(model, forcing, simulation, variable):
    return WIEFile(
        model=model,
        experiment=const.Experiment.overshoot,
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
