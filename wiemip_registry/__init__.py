"""`wiemip_registry` — a typed, centralized accessor for every file in the
WIE-MIP buckets.

The headline access pattern is a dotted namespace resolving to a `WIEFile`:

    import wiemip_registry as wr

    # experiment . simulation . model . forcing . factorial . variable
    f  = wr.one_percent_co2.bgc.LPX_Bern.ukesm.baseline.cVeg
    ts = f.global_sum()     # Pg C time series
    da = f.read()           # standardized, lazy xr.DataArray

The namespace is **sparse**: only existing combinations resolve. A miss raises a
clear error listing what *is* available at that level (see `_Node.__getattr__`).

How it's built:
  * Discover each populated model subpackage's `convert.py`, find the single
    `WIEAdapter` subclass it defines, and instantiate it.
  * Ask each adapter to enumerate the (experiment, simulation, forcing, factorial,
    variable) tuples it resolves (Enums + a variable string).
  * Key the tree by the Python-safe identifiers (`Enum.name` for the four Enum
    levels, the subpackage name for `model`, the CMIP string for `variable`) and
    expose it through `_Node` proxies; the leaf builds a `WIEFile` holding the
    Enum members themselves.
"""
from __future__ import annotations

import importlib

from .core import WIEAdapter, WIEFile

# Populated models only (the other ~20 bucket dirs are empty placeholders).
# Each name is BOTH the subpackage dir and the Python-safe namespace alias.
_MODEL_PACKAGES = [
    "BiomeE", "CLASSIC", "DLEM", "JSBACH", "JULES", "LPX_Bern", "VISIT_UT",
]

# Experiment dir on disk  <->  Python-safe namespace alias (leading digit fix).
EXPERIMENT_ALIASES = {"1pctCO2": "one_percent_co2", "overshoot": "overshoot"}


def _find_adapter_class(module) -> type[WIEAdapter] | None:
    """The single concrete `WIEAdapter` subclass defined in a model's convert.py."""
    for obj in vars(module).values():
        if isinstance(obj, type) and issubclass(obj, WIEAdapter) and obj is not WIEAdapter:
            return obj
    return None


def _load_adapters() -> dict[str, WIEAdapter]:
    """Import each `<MODEL>/convert.py`, instantiate its adapter class, key by alias."""
    adapters: dict[str, WIEAdapter] = {}
    for name in _MODEL_PACKAGES:
        try:
            module = importlib.import_module(f"{__name__}.{name}.convert")
        except ModuleNotFoundError:
            continue                      # adapter not written yet — model won't resolve
        cls = _find_adapter_class(module)
        if cls is not None:
            adapters[name] = cls()
    return adapters


def _build_tree(adapters: dict[str, WIEAdapter]) -> dict:
    """Nested dict: exp -> sim -> model_alias -> forcing -> factorial -> var -> leaf,
    keyed by `Enum.name`/alias/str. A leaf is `(adapter, model_alias, coords)`
    where `coords` holds the Enum members, enough to lazily build a `WIEFile`."""
    tree: dict = {}
    for model_alias, adapter in adapters.items():
        for exp, sim, forcing, factorial, variable in adapter.available():
            coords = (exp, sim, forcing, factorial, variable)
            (tree
                .setdefault(exp.name, {})
                .setdefault(sim.name, {})
                .setdefault(model_alias, {})
                .setdefault(forcing.name, {})
                .setdefault(factorial.name, {})
                [variable]) = (adapter, model_alias, coords)
    return tree


_LEVELS = ("experiment", "simulation", "model", "forcing", "factorial", "variable")


class _Node:
    """Attribute proxy for one level of the sparse namespace."""

    def __init__(self, children: dict, depth: int, path: tuple[str, ...]):
        self._children = children
        self._depth = depth          # index into _LEVELS of THIS node's children
        self._path = path            # aliases consumed so far (for error messages)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            child = self._children[name]
        except KeyError:
            level = _LEVELS[self._depth]
            here = ".".join(self._path) or "<root>"
            avail = ", ".join(sorted(self._children)) or "(none)"
            raise AttributeError(
                f"no {level} '{name}' at {here}. Available {level}s: {avail}"
            ) from None

        # Leaf reached: child is the (adapter, alias, coords) tuple -> WIEFile.
        if isinstance(child, tuple):
            adapter, _model_alias, coords = child
            experiment, simulation, forcing, factorial, variable = coords
            return WIEFile(
                model=adapter.model,
                experiment=experiment,
                simulation=simulation,
                forcing=forcing,
                factorial=factorial,
                variable=variable,
                _adapter=adapter,
            )
        return _Node(child, self._depth + 1, self._path + (name,))

    def __dir__(self):
        # Enables tab-completion of the next level in REPLs / notebooks.
        return list(self._children)

    def __repr__(self) -> str:
        level = _LEVELS[self._depth]
        return f"<wiemip_registry node {'.'.join(self._path) or 'root'} -> {level}s {sorted(self._children)}>"


# --------------------------------------------------------------------------- #
# Build the namespace at import and expose experiments as module attributes.
# --------------------------------------------------------------------------- #
_ADAPTERS = _load_adapters()
_TREE = _build_tree(_ADAPTERS)
_ROOT = _Node(_TREE, depth=0, path=())


def __getattr__(name: str):  # PEP 562 — lazy module-level experiment lookup
    if name in _TREE:
        return _Node(_TREE[name], depth=1, path=(name,))
    raise AttributeError(
        f"no experiment '{name}'. Available experiments: {', '.join(sorted(_TREE)) or '(none)'}"
    )


def __dir__():
    return sorted(list(_TREE) + ["WIEFile"])


__all__ = ["WIEFile"] + list(EXPERIMENT_ALIASES.values())
