"""List the model-output files on the bucket that no legal registry request reaches,
and write an issue body for the ones that are new since the last run.

Run by the `uncovered` GitHub Action, or by hand against an `aws s3 ls --recursive` dump:

    python .github/workflows/_uncovered.py <listing.txt> <previous uncovered.txt>

`path()` is pure string work, so this never touches S3: coverage is the set difference
between the bucket's model-output `.nc` keys and every path the registry can spell.
Writes `uncovered.txt` (the full list, next run's `previous`) and, when there are new
files and a previous list to compare against, `issue.md` + `issue_title.txt`.
"""

from __future__ import annotations

import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import wiemip_registry as wr
import wiemip_registry.const as const
from wiemip_registry.core import MissingFactorialError

warnings.simplefilter("ignore")  # JULES's Fire#### factorials warn on every request

OUTPUT_KEY = re.compile(
    rf"^({const.ONE_PERCENT_CO2_KEY}|overshoot)/output/[^/]+/.+\.nc$"
)
CONSTANT_CLIMATE = ("bgc", "bgc_ndep", "ctrl")  # core.ensure_valid allows only `stable`
MAX_LINES_PER_DIR = 50  # keeps the issue body under GitHub's 65k-character limit


def legal_requests(model, adapter):
    """Every WIEFile a user may legally request for `model`, both experiments."""
    for variable in wr.variables:
        for simulation in wr.one_percent_simulations:
            forcings = ["stable"] if simulation in CONSTANT_CLIMATE else wr.gcm_patterns
            for forcing in forcings:
                for factorial in adapter.FACTORIALS:
                    yield wr.retrieve_one_pct_variable(
                        model, forcing, simulation, factorial, variable
                    )
        for simulation in wr.overshoot_simulations:
            for forcing in wr.gcm_patterns:
                for factorial in adapter.OVERSHOOT_FACTORIALS or [None]:
                    yield wr.retrieve_overshoot_variable(
                        model, forcing, simulation, variable, factorial
                    )


if __name__ == "__main__":
    listing, previous_path = Path(sys.argv[1]), Path(sys.argv[2])

    spelled = set()
    for model, adapter in wr.adapters.items():
        for f in legal_requests(model, adapter):
            try:
                spelled.update(str(p) for p in f.paths)
            except (MissingFactorialError, NotImplementedError):
                continue  # factorial not declared for this arm, or overshoot not mapped

    # `aws s3 ls --recursive` lines are `<date> <time> <size> <key>`
    on_bucket = set()
    for line in listing.read_text().splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and OUTPUT_KEY.match(parts[3]):
            on_bucket.add(f"{const.DATA_ROOT}/{parts[3]}")

    uncovered = on_bucket - spelled
    Path("uncovered.txt").write_text("".join(f"{p}\n" for p in sorted(uncovered)))
    print(
        f"{len(on_bucket)} model-output files on the bucket, {len(uncovered)} unreached"
    )

    if not previous_path.exists():
        print("no previous list: seeding only")
        sys.exit(0)
    previous = set(previous_path.read_text().split())
    new, resolved = uncovered - previous, previous - uncovered
    print(f"{len(new)} new, {len(resolved)} resolved since the last run")
    if not new:
        sys.exit(0)

    by_dir = defaultdict(list)
    for p in sorted(new):
        experiment, _, model_dir, rest = p[len(f"{const.DATA_ROOT}/") :].split("/", 3)
        by_dir[f"{experiment}/output/{model_dir}"].append(rest)

    lines = [
        f"**{len(new)} new** unreached files, **{len(resolved)} resolved** since the last run, "
        f"**{len(uncovered)} unreached** in total ({len(on_bucket)} model-output files on the bucket).",
        "",
    ]
    for directory, files in by_dir.items():
        lines += [f"### `{directory}/` ({len(files)})", "```"]
        lines += files[:MAX_LINES_PER_DIR]
        if len(files) > MAX_LINES_PER_DIR:
            lines.append(
                f"... and {len(files) - MAX_LINES_PER_DIR} more (see uncovered.txt in the run artifact)"
            )
        lines += ["```", ""]
    Path("issue.md").write_text("\n".join(lines))
    Path("issue_title.txt").write_text(f"{len(new)} new unreached files")
