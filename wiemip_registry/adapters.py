from wiemip_registry.BiomeE.convert import BiomeE
from wiemip_registry.CARDAMOM_JPL.convert import CARDAMOM_JPL
from wiemip_registry.CLASSIC.convert import CLASSIC
from wiemip_registry.CLM.convert import CLM
from wiemip_registry.CLM_FATES.convert import CLM_FATES
from wiemip_registry.CoLM.convert import CoLM
from wiemip_registry.core import Model
from wiemip_registry.DLEM.convert import DLEM
from wiemip_registry.EDv3.convert import EDv3
from wiemip_registry.ELM.convert import ELM
from wiemip_registry.JSBACH.convert import JSBACH
from wiemip_registry.LPJ_EOSIM.convert import LPJ_EOSIM
from wiemip_registry.LPJ_GUESS.convert import LPJ_GUESS
from wiemip_registry.LPJmL6.convert import LPJmL6
from wiemip_registry.LPX_Bern.convert import LPX_Bern
from wiemip_registry.TEM.convert import TEM

adapters = {
    # "BEPS": BEPS() -> still re-running,
    "BiomeE": BiomeE(),
    "CARDAMOM_JPL": CARDAMOM_JPL(),
    "CLASSIC": CLASSIC(),
    "CLM": CLM(),
    "CLM_FATES": CLM_FATES(),
    "CoLM": CoLM(),
    "DLEM": DLEM(),
    # "DVM_DOS_TEM": DVM_DOS_TEM() -> still re-running
    "EDv3": EDv3(),
    "ELM": ELM(),
    "JSBACH": JSBACH(),
    # "JULES": JULES(),
    "LPJ_EOSIM": LPJ_EOSIM(),
    "LPJ_GUESS": LPJ_GUESS(),
    "LPJmL6": LPJmL6(),
    "LPX_Bern": LPX_Bern(),
    # "ORCHIDEE_MICT_CALIPSO": ORCHIDEE_MICT_CALIPSO() -> removed 2026-11-04
    # "VISIT_UT": VISIT_UT(),
    "TEM": TEM(),
}

models = tuple(Model(name, adapter) for name, adapter in adapters.items())
