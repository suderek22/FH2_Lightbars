"""Build the offline PoliceLightbars car pack and release archive."""
import argparse
from pathlib import Path
import sys
import json
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT.parent / "CarPackStudio"))
sys.path.insert(0, str(PROJECT.parent / "FH2StrEditor"))
from cps.bundle import Bundle
from cps.zipnative import build_zip
from ConvertTextures import convert_textures
from PackAssets import add_labels, build_lamp_materials, fix_vertex_layout, replace_materials

from RoofLights import build_roof_lights, preset_records
from PositionLightbar import position_lightbar

VERSION = "0.2.2"
CHARGER = "DOD_ChargerSRT8_12"
CHARGER_SHIFT = (0.25, -0.14)


def build_car(stock_path, work, textures, marker, library, donor, preset_template, pack, offset=(0.0, 0.0)):
    name = stock_path.stem
    car = name.lower().encode("ascii")
    scene = f"{name}.carbin"
    reference = work / ("fh2-ALF_4C_14.carbin" if name == "ALF_4C_14" else f"stock-{scene}")
    with ZipFile(stock_path) as stock:
        scene = next(member for member in stock.namelist() if member.lower() == scene.lower())
        if stock.read(scene) != reference.read_bytes():
            raise ValueError(f"Stock {name} scene differs from the input to the scene builder.")
        entries = {member: stock.read(member) for member in stock.namelist()}
    entries[scene] = (work / f"{name}.carbin").read_bytes()

    # Short resource names keep the Charger paths within FH2's material reference format.
    if offset != (0.0, 0.0):
        textures = {key: (f"{key}.swatchbin", data) for key, (_, data) in textures.items()}
        body_name = next(member for member in entries if member.lower().endswith("/platform/body_a.modelbin"))
        skeleton, = Bundle(entries[body_name]).all("Skel")
    for key, (filename, texture) in textures.items():
        if key != "lens_mask":
            entries[f"Textures/lightbars/{filename}"] = texture

    for variant in ("amber", "blue"):
        filename = f"lightbar_{variant}_modern_a.modelbin"
        original = (work / filename).read_bytes()
        bindings, materials = build_lamp_materials(library, marker, original, variant, textures, car)
        model = fix_vertex_layout(replace_materials(original, bindings))
        if offset != (0.0, 0.0):
            model = position_lightbar(model, skeleton.data, *offset)
        entries[f"scene/exterior/lightbars/{filename}"] = model
        entries.update(materials)
    build_roof_lights(entries, donor, car, *offset, preset_template)

    native_zip, _, _, _ = build_zip(entries)
    output = pack / "media" / "cars" / stock_path.name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(native_zip)
    with ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.infolist()) != len(entries):
            raise ValueError(f"Replacement {name} archive failed ZIP validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_archive", type=Path, help="Stock FH2 Alfa Romeo 4C archive")
    parser.add_argument("fh6_root", type=Path)
    parser.add_argument("--charger-archive", type=Path)
    args = parser.parse_args()
    work = PROJECT / "work"
    media = args.stock_archive.parent.parent
    charger = args.charger_archive or args.stock_archive.with_name(f"{CHARGER}.zip")

    with ZipFile(args.fh6_root / "media/Cars/_library/Textures.zip") as source, ZipFile(
        media / "cars/_library/Textures.zip"
    ) as stock_textures:
        textures = convert_textures(source, stock_textures)
    release = PROJECT / "dist" / VERSION
    pack = release / "fh2-cars" / "PoliceLightbars"
    with ZipFile(media / "cars/NIS_FairladyZvSTwinTurbo_94.zip") as marker_car, ZipFile(
        media / "cars/_library/Materials.zip"
    ) as library, ZipFile(args.fh6_root / "media/Cars/ALF_4C_14.zip") as donor, ZipFile(args.stock_archive) as stock:
        marker = marker_car.read("scene/Exterior/BumperF/bumperFSideMarkers_b.modelbin")
        preset_template = preset_records(stock.read("LightPresets.bin"), 1)[9]
        build_car(args.stock_archive, work, textures, marker, library, donor, preset_template, pack)
        build_car(charger, work, textures, marker, library, donor, preset_template, pack, CHARGER_SHIFT)
        cars = json.loads((PROJECT / "ExtraPlacements.json").read_text())
        for name, spec in cars.items():
            build_car(media / "cars" / f"{name}.zip", work, textures, marker, library,
                      donor, preset_template, pack, tuple(spec["offset"]))
            print(f"Built {name}", flush=True)

    strings = pack / "media" / "Stripped" / "StringTables"
    for path in sorted((media / "Stripped" / "StringTables").glob("*.zip")):
        with ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.lower() == "list_partmanufacturer.str")
            output = strings / path.stem / "List_PartManufacturer.str"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(add_labels(archive.read(name)))

    (pack / "pack.ini").write_text(f"[pack]\nname = PoliceLightbars\nversion = {VERSION}\n", encoding="ascii")
    # The DLL registers the SQL for both the pack and fallback databases.
    with ZipFile(release / f"PoliceLightbars-v{VERSION}-test.zip", "w", ZIP_DEFLATED) as package:
        for path in sorted(pack.rglob("*")):
            if path.is_file() and path.name != "Upgrade.sql":
                package.write(path, path.relative_to(release))
        package.write(release / "fh2-mods" / "PoliceLightbars.dll", "fh2-mods/PoliceLightbars.dll")
        package.write(PROJECT / "README.md", "PoliceLightbars-README.md")


if __name__ == "__main__":
    main()
