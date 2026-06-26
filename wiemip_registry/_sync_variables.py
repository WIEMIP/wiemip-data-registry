"""Sync `wiemip_registry`'s variable list from the WIE-MIP data request
(GitHub: colligant/wiemip-data-request).

The data request defines one JSON per variable under
`<data-request>/variables/<category>/<name>.json`, each carrying a `"Variable name"`
short/CMIP name. This script collects those names across all categories and rewrites
the AUTO-GENERATED `VARIABLES` block in `const.py`, then regenerates `__init__.pyi`
so `wr.variables` and editor autocomplete stay in sync. Run it whenever the data
request changes:

    python wiemip_registry/_sync_variables.py
    python wiemip_registry/_sync_variables.py /path/to/wiemip-data-request
    WIEMIP_DATA_REQUEST=/path/to/wiemip-data-request python wiemip_registry/_sync_variables.py

Stdlib only (json + pathlib). The synced list is COMMITTED to const.py, so using the
package needs no data-request checkout — only re-syncing does. If the data request is
ever added as a git submodule at the repo root, it's picked up automatically (no code
change), since that path is one of the search candidates.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # .../wiemip-data-processing/wiemip_registry
_REPO = _HERE.parent                              # .../wiemip-data-processing
_CONST = _HERE / "const.py"

_START = "# >>> AUTO-GENERATED VARIABLES"
_END = "# <<< AUTO-GENERATED VARIABLES"


def _candidate_roots(explicit: str | None) -> list[Path]:
    """Where to look for the data-request repo. An explicit arg/env is authoritative
    (no silent fallback, so typos surface); otherwise try the in-tree submodule then
    the sibling clone."""
    explicit = explicit or os.environ.get("WIEMIP_DATA_REQUEST")
    if explicit:
        return [Path(explicit).expanduser()]
    return [
        _REPO / "wiemip-data-request",          # in-tree submodule
        _REPO.parent / "wiemip-data-request",   # sibling clone
    ]


def _find_variables_dir(explicit: str | None) -> Path:
    """Resolve the data request's `variables/` dir (accepts the repo root or that dir)."""
    roots = _candidate_roots(explicit)
    for root in roots:
        cand = root if root.name == "variables" else root / "variables"
        if cand.is_dir():
            return cand
    tried = "\n  ".join(str(r) for r in roots)
    raise SystemExit(
        "Could not find the wiemip-data-request `variables/` directory. Tried:\n  "
        f"{tried}\n"
        "Clone colligant/wiemip-data-request next to this repo, pass its path as an "
        "argument, or set $WIEMIP_DATA_REQUEST."
    )


def collect_variables(variables_dir: Path) -> list[str]:
    """Sorted, de-duplicated `Variable name`s across every category JSON."""
    names: set[str] = set()
    for jf in sorted(variables_dir.rglob("*.json")):
        with jf.open(encoding="utf-8") as fh:
            data = json.load(fh)
        name = (data.get("Variable name") or "").strip()
        if name:
            names.add(name)
    if not names:
        raise SystemExit(f"No `Variable name` entries found under {variables_dir}.")
    return sorted(names)


def _format_block(names: list[str]) -> list[str]:
    """The replacement lines between the markers: a one-per-line VARIABLES list."""
    return ["VARIABLES = [", *[f'    "{n}",' for n in names], "]"]


def rewrite_const(names: list[str]) -> None:
    """Replace the text between the AUTO-GENERATED markers in const.py."""
    lines = _CONST.read_text().splitlines()
    starts = [k for k, l in enumerate(lines) if l.startswith(_START)]
    ends = [k for k, l in enumerate(lines) if l.startswith(_END)]
    if not starts or not ends or ends[0] < starts[0]:
        raise SystemExit(f"AUTO-GENERATED VARIABLES markers not found (or misordered) in {_CONST}.")
    i, j = starts[0], ends[0]
    new_lines = lines[: i + 1] + _format_block(names) + lines[j:]   # keep both marker lines
    _CONST.write_text("\n".join(new_lines) + "\n")


def _regenerate_stubs() -> None:
    """Re-run _gen_stubs.main() so __init__.pyi / wr.variables track the new list.
    Loaded by file path so this works as a plain script (no package context needed)."""
    spec = importlib.util.spec_from_file_location("_wr_gen_stubs", _HERE / "_gen_stubs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def main() -> None:
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    variables_dir = _find_variables_dir(explicit)
    names = collect_variables(variables_dir)
    rewrite_const(names)
    print(f"synced {len(names)} variables from {variables_dir} -> {_CONST.name}")
    _regenerate_stubs()


if __name__ == "__main__":
    main()
