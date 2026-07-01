"""`wiemip_registry` — a typed, centralized accessor for every file in the
WIE-MIP buckets.

The headline access pattern is a dotted namespace resolving to a `WIEFile`:

    import wiemip_registry as wr

    # experiment . model . forcing . simulation . factorial . variable
    f  = wr.one_percent_co2.LPX_Bern.ukesm.bgc.baseline.cVeg
    ts = f.latitudinal_sum()   # Pg C series (native cadence)
    da = f.read()              # standardized, lazy xr.DataArray

Resolution is **lazy and name-based** — no pre-enumerated tree, no existence scan
at import:
  * The four Enum axes (experiment / forcing / simulation / factorial) and the
    `model` axis are validated by *name* as you select them; an unknown name raises
    `AttributeError` listing the valid options (and drives tab-completion).
  * The `variable` axis is free-form: selecting it always returns a `WIEFile` and
    never touches s3. If that variable's file wasn't uploaded, the error surfaces
    only when you call `.read()` (xarray can't open it).
"""

from __future__ import annotations

import functools
import importlib
import sys

from .core import WIEAdapter, WIEFile
from .const import (
    Experiment,
    GCMPattern,
    Simulation,
    MODEL_PACKAGES,
    FACTORIAL_BUCKETS,
)
from .variables import VARIABLES
from .variable_overrides import EXTRA_VARIABLES


def _find_adapter_class(module) -> type[WIEAdapter] | None:
    """The single concrete `WIEAdapter` subclass defined in a model's convert.py."""
    for obj in vars(module).values():
        if (
            isinstance(obj, type)
            and issubclass(obj, WIEAdapter)
            and obj is not WIEAdapter
        ):
            return obj
    return None


def _load_adapters() -> dict[str, WIEAdapter]:
    """Import each `<MODEL>/convert.py`, instantiate its adapter class, key by alias."""
    adapters: dict[str, WIEAdapter] = {}
    for name in MODEL_PACKAGES:
        try:
            module = importlib.import_module(f"{__name__}.{name}.convert")
        except ModuleNotFoundError:
            continue  # adapter not written yet — model won't resolve
        cls = _find_adapter_class(module)
        if cls is not None:
            adapters[name] = cls()
    return adapters


_ADAPTERS = _load_adapters()

# Every adapter must slot its factorials into the universal buckets — a key outside
# const.FACTORIAL_BUCKETS is a spelling drift that would make the bucket unreachable
# cross-model, so fail loudly at import rather than at some later lookup.
for _name, _adapter in _ADAPTERS.items():
    _bad = set(_adapter.FACTORIALS) - set(FACTORIAL_BUCKETS)
    if _bad:
        raise ValueError(
            f"{_name} uses undefined factorial buckets {sorted(_bad)}; "
            f"add them to const.FACTORIAL_BUCKETS"
        )

# Iterable axis vocabularies — the valid attribute names at each level. Feed any of
# these back into the namespace with `getattr(node, name)`. (`variables` is the
# common-CMIP convenience list; the variable axis itself accepts any name.)
models: tuple[str, ...] = tuple(_ADAPTERS)
gcm_patterns: tuple[str, ...] = tuple(m.name for m in GCMPattern)
simulations: tuple[str, ...] = tuple(m.name for m in Simulation)
# Data-request list + hand-maintained overrides (superseded-but-uploaded names),
# de-duplicated, order preserved.
variables: tuple[str, ...] = tuple(dict.fromkeys([*VARIABLES, *EXTRA_VARIABLES]))

# Axis order of the dotted namespace, and the Enum backing each Enum axis.
# (`factorial` is NOT here — it's validated per-model against the adapter's
# FACTORIALS, since each model ships a different set of sensitivity runs.)
_LEVELS = ("experiment", "model", "forcing", "simulation", "factorial", "variable")
_ENUM_BY_LEVEL = {
    "experiment": Experiment,
    "forcing": GCMPattern,
    "simulation": Simulation,
}


class _Node:
    """Lazy attribute proxy. Carries the selections made so far and resolves the
    next axis (per `_LEVELS`) by name. Building a node never touches s3."""

    def __init__(
        self,
        depth: int,
        selections: dict,
        adapter: WIEAdapter | None,
        path: tuple[str, ...],
    ):
        self._depth = depth  # index into _LEVELS of the NEXT axis to pick
        self._sel = selections  # {level: Enum member} chosen so far
        self._adapter = adapter  # set once the model axis is chosen
        self._path = path  # attribute names chosen so far (for errors/repr)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        level = _LEVELS[self._depth]

        # Leaf: any variable name is accepted; a missing file errors at read() time.
        if level == "variable":
            return WIEFile(
                model=self._adapter.model,
                variable=name,
                _adapter=self._adapter,
                **self._sel,
            )

        if level == "model":
            adapter = _ADAPTERS.get(name)
            if adapter is None:
                raise AttributeError(
                    f"no model '{name}' at {'.'.join(self._path) or '<root>'}. "
                    f"Available models: {', '.join(sorted(_ADAPTERS))}"
                )
            return _Node(
                self._depth + 1, dict(self._sel), adapter, self._path + (name,)
            )

        # Factorial: per-model vocabulary, validated against the chosen adapter.
        if level == "factorial":
            if name not in self._adapter.FACTORIALS:
                raise AttributeError(
                    f"no factorial '{name}' for {self._adapter.model} at "
                    f"{'.'.join(self._path) or '<root>'}. Available factorials: "
                    f"{', '.join(sorted(self._adapter.FACTORIALS))}"
                )
            return _Node(
                self._depth + 1,
                {**self._sel, "factorial": name},
                self._adapter,
                self._path + (name,),
            )

        enum = _ENUM_BY_LEVEL[level]
        try:
            member = enum[name]
        except KeyError:
            raise AttributeError(
                f"no {level} '{name}' at {'.'.join(self._path) or '<root>'}. "
                f"Available {level}s: {', '.join(m.name for m in enum)}"
            ) from None
        return _Node(
            self._depth + 1,
            {**self._sel, level: member},
            self._adapter,
            self._path + (name,),
        )

    def __dir__(self):
        # Drives tab-completion of the next axis in REPLs / notebooks.
        level = _LEVELS[self._depth]
        if level == "model":
            return sorted(_ADAPTERS)
        if level == "factorial":
            return sorted(self._adapter.FACTORIALS)
        if level == "variable":
            return []  # free-form; no enum to enumerate
        return [m.name for m in _ENUM_BY_LEVEL[level]]

    def __repr__(self) -> str:
        return (
            f"<wiemip_registry node {'.'.join(self._path) or 'root'} "
            f"-> next: {_LEVELS[self._depth]}>"
        )


def __getattr__(name: str):  # PEP 562 — the top level is the `experiment` axis
    if name.startswith("_"):
        raise AttributeError(name)
    try:
        experiment = Experiment[name]
    except KeyError:
        raise AttributeError(
            f"no experiment '{name}'. "
            f"Available experiments: {', '.join(m.name for m in Experiment)}"
        ) from None
    return _Node(
        depth=1, selections={"experiment": experiment}, adapter=None, path=(name,)
    )


def retrieve(
    experiment: str,
    model: str,
    forcing: str,
    simulation: str,
    factorial: str,
    variable: str,
) -> WIEFile:
    """Resolve string axis names to a `WIEFile` — the functional twin of the dotted
    namespace `wr.<experiment>.<model>.<forcing>.<simulation>.<factorial>.<variable>`.

    Use this when the axes are held as strings (looping over `wr.models`, a config,
    CLI args) rather than typed out as attributes. The experiment/model/forcing/
    simulation axes are validated by name exactly as attribute access is (unknown
    name -> `AttributeError` listing the valid options). The factorial is checked
    against the model's universal buckets and raises `ValueError` if that model never
    ran it. The variable axis is free-form, so a combination that wasn't uploaded
    surfaces only when you call `.read()` / `.latitudinal_sum()`. Building the WIEFile
    never touches s3.

        f = wr.retrieve("one_percent_co2", "CLASSIC", "ukesm", "cou", "baseline", "cVeg")
        f.latitudinal_sum()   # identical to the dotted form
    """
    node = functools.reduce(
        getattr, (experiment, model, forcing, simulation), sys.modules[__name__]
    )
    if factorial not in node._adapter.FACTORIALS:
        raise ValueError(
            f"Factorial {factorial} for model {model} does not exist. "
            f"Available: {', '.join(node._adapter.FACTORIALS)}"
        )
    return getattr(getattr(node, factorial), variable)


_PUBLIC = ["WIEFile", "retrieve", "models", "variables", "gcm_patterns", "simulations"]


def __dir__():
    return sorted(_PUBLIC + [m.name for m in Experiment])


__all__ = _PUBLIC + [m.name for m in Experiment]
