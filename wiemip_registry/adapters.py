from wiemip_registry.BiomeE.convert import BiomeE
from wiemip_registry.CLASSIC.convert import CLASSIC
from wiemip_registry.CLM_FATES.convert import CLM_FATES
from wiemip_registry.DLEM.convert import DLEM
from wiemip_registry.JSBACH.convert import JSBACH
from wiemip_registry.JULES.convert import JULES
from wiemip_registry.LPJ_EOSIM.convert import LPJ_EOSIM
from wiemip_registry.LPX_Bern.convert import LPX_Bern
from wiemip_registry.TEM.convert import TEM
from wiemip_registry.VISIT_UT.convert import VISIT_UT

adapters = {
    "BiomeE": BiomeE(),
    "CLASSIC": CLASSIC(),
    "CLM_FATES": CLM_FATES(),
    "DLEM": DLEM(),
    "JSBACH": JSBACH(),
    "JULES": JULES(),
    "LPJ_EOSIM": LPJ_EOSIM(),
    "LPX_Bern": LPX_Bern(),
    "VISIT_UT": VISIT_UT(),
    "TEM": TEM(),
}
