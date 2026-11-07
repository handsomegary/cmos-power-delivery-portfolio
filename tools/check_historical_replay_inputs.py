"""Check retained local inputs for a historical Spectre case."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?")
    parser.add_argument("case_directory", nargs="?", type=Path)
    parser.add_argument("model_entry", nargs="?", type=Path)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    inventory = json.loads((repo / "docs/historical-replay-inputs.json").read_text(encoding="utf-8"))
    cases = inventory["cases"]
    if args.list:
        print("\n".join(sorted(cases)))
        return
    if args.case not in cases or args.case_directory is None or args.model_entry is None:
        parser.error("Supply a listed case, the retained case directory and the installed model entry.")
    files = cases[args.case]["files"]
    try:
        for name, expected in files.items():
            if digest(args.case_directory / name) != expected:
                raise SystemExit(f"Input SHA-256 mismatch for {name}")
        if digest(args.model_entry) != inventory["licensed_model_entry_sha256"]:
            raise SystemExit("Model-entry SHA-256 mismatch")
    except OSError as error:
        raise SystemExit(str(error)) from error
    print(f"Verified {len(files)} input files and the model entry for {args.case}.")


if __name__ == "__main__":
    main()
