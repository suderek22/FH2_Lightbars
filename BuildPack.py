"""Build the offline 4C replacement pack from the converted scene and meshes."""
import argparse
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT.parent / "CarPackStudio"))
sys.path.insert(0, str(PROJECT.parent / "FH2StrEditor"))
from cps.zipnative import build_zip
from ConvertTextures import convert_textures
from PackAssets import add_labels, build_lamp_materials, fix_vertex_layout, replace_materials

from RoofLights import build_roof_lights

VERSION = "0.1.15"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_archive", type=Path)
    parser.add_argument("fh6_root", type=Path)
    args = parser.parse_args()
    work = PROJECT / "work"
    media = args.stock_archive.parent.parent
    with ZipFile(args.stock_archive) as stock:
        if stock.read("ALF_4C_14.carbin") != (work / "fh2-ALF_4C_14.carbin").read_bytes():
            raise ValueError("Stock 4C scene differs from the scene used to build the mod.")
        entries = {name: stock.read(name) for name in stock.namelist()}

    with ZipFile(args.fh6_root / "media/Cars/_library/Textures.zip") as source, ZipFile(
        media / "cars/_library/Textures.zip"
    ) as stock_textures:
        textures = convert_textures(source, stock_textures)
    for key, (name, texture) in textures.items():
        if key == "lens_mask":
            (work / name).write_bytes(texture)
        else:
            entries[f"Textures/lightbars/{name}"] = texture

    entries["ALF_4C_14.carbin"] = (work / "ALF_4C_14.carbin").read_bytes()
    with ZipFile(media / "cars" / "NIS_FairladyZvSTwinTurbo_94.zip") as donor:
        marker = donor.read("scene/Exterior/BumperF/bumperFSideMarkers_b.modelbin")
    with ZipFile(media / "cars" / "_library" / "Materials.zip") as library:
        for variant in ("amber", "blue"):
            filename = f"lightbar_{variant}_modern_a.modelbin"
            model = (work / filename).read_bytes()
            bindings, materials = build_lamp_materials(library, marker, model, variant, textures)
            entries[f"scene/exterior/lightbars/{filename}"] = fix_vertex_layout(replace_materials(model, bindings))
            entries.update(materials)

    with ZipFile(args.fh6_root / "media/Cars/ALF_4C_14.zip") as donor:
        build_roof_lights(entries, donor)

    native_zip, _, _, _ = build_zip(entries)
    release = PROJECT / "dist" / VERSION
    relative_pack = Path("fh2-cars") / "PoliceLightbars"
    pack = release / relative_pack
    car_archive = pack / "media" / "cars" / "ALF_4C_14.zip"
    car_archive.parent.mkdir(parents=True, exist_ok=True)
    car_archive.write_bytes(native_zip)
    with ZipFile(car_archive) as archive:
        if archive.testzip() is not None or len(archive.infolist()) != len(entries):
            raise ValueError("Replacement 4C archive failed ZIP validation.")

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
