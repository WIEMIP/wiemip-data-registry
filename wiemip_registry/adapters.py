from wiemip_registry.BiomeE.convert import BiomeE
from wiemip_registry.CLASSIC.convert import CLASSIC
from wiemip_registry.CLM_FATES.convert import CLM_FATES
from wiemip_registry.DLEM.convert import DLEM
from wiemip_registry.JSBACH.convert import JSBACH
from wiemip_registry.JULES.convert import JULES
from wiemip_registry.LPX_Bern.convert import LPX_Bern
from wiemip_registry.VISIT_UT.convert import VISIT_UT

# Model handle (the name you pass to retrieve_*/qa.sh) -> a single shared adapter
# INSTANCE (weights are cached on it). Keyed by the Python-safe package alias
# (LPX_Bern, not LPX-Bern); the adapter's own `.model` carries the on-disk name.
adapters = {
    "BiomeE": BiomeE(),
    "CLASSIC": CLASSIC(),
    "CLM_FATES": CLM_FATES(),
    "DLEM": DLEM(),
    "JSBACH": JSBACH(),
    "JULES": JULES(),
    "LPX_Bern": LPX_Bern(),
    "VISIT_UT": VISIT_UT(),
}
