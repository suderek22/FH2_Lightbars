"""Build deduplicated resources for the PoliceLightbars loose-file release."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_cars", type=Path)
    parser.add_argument("reference_cars", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    args.output.mkdir(parents=True, exist_ok=True)
    cars = sorted(set(json.loads((project / "ExtraPlacements.json").read_text()))
                  | {"ALF_4C_14", "DOD_ChargerSRT8_12"})
    resources = {}
    model_resources = {}
    declarations = []
    overrides = []
    for car in cars:
        with ZipFile(args.stock_cars / f"{car}.zip") as stock, ZipFile(
            args.reference_cars / f"{car}.zip"
        ) as modified:
            changes = {}
            stock_names = set(stock.namelist())
            for entry in modified.namelist():
                payload = modified.read(entry)
                if entry not in stock_names or payload != stock.read(entry):
                    changes[entry] = payload
            for required in (f"{car}.carbin", "Lights.bin", "LightPresets.bin"):
                if required.casefold() not in {name.casefold() for name in changes}:
                    raise ValueError(f"{car} is missing changed {required}")
            for entry, payload in sorted(changes.items()):
                digest = hashlib.sha256(payload).digest()
                if digest not in resources:
                    resource = 101 + len(resources)
                    resources[digest] = resource
                    filename = f"{resource}.bin"
                    (args.output / filename).write_bytes(payload)
                    declarations.append(f'{resource} RCDATA "{filename}"')
                resource = resources[digest]
                entry = entry.replace(chr(92), "/")
                if entry.endswith(".modelbin"):
                    model_resources.setdefault(entry, set()).add(resource)
                path = json.dumps(f"cars/{car}/{entry}")
                overrides.append(f"    {{{resource}, {path}}},")
    (args.output / "LooseAssets.rc").write_text("\n".join(declarations) + "\n")
    (args.output / "LooseAssets.inc").write_text("\n".join(overrides) + "\n")
    print(f"{len(cars)} cars, {len(overrides)} override paths, {len(resources)} unique payloads")
    for entry, ids in sorted(model_resources.items()):
        print(f"{entry}: {len(ids)} unique payload(s)")


if __name__ == "__main__":
    main()
