"""Prepare FH2 string tables and materials used by the lightbar pack."""
import struct
import zlib

from strtable import StrTable

LABELS = {0xF812: "Amber Lightbar", 0xF813: "Blue Lightbar"}
BLOB = struct.Struct("<4sHHIIII")


def add_labels(data):
    table = StrTable.read(data)
    keys = sorted(table.strings)
    if LABELS.keys() & table.strings.keys():
        raise ValueError("Lightbar string keys already exist")
    all_keys = sorted([*keys, *LABELS])
    for section_index in (1, 3):
        section = table.sections[section_index]
        count = struct.unpack_from("<I", section, 4)[0]
        if count != len(keys):
            raise ValueError("Unexpected manufacturer string table layout")
        if section_index == 1:
            records = dict(zip(keys, struct.iter_unpack("<HHI", section[8:8 + count * 8])))
            names = bytearray(section[8 + count * 8:])
            for key in LABELS:
                records[key] = (key, 0, len(names))
                names.extend(f"IDS_Lightbar_{key:04X}".encode("ascii") + b"\0")
            payload = b"".join(struct.pack("<HHI", *records[key]) for key in all_keys) + names
        else:
            records = dict(zip(keys, struct.unpack_from(f"<{count}H", section, 8)))
            payload = struct.pack(f"<{len(all_keys)}H", *(records.get(key, 0) for key in all_keys))
        table.sections[section_index] = struct.pack("<II", 8 + len(payload), len(all_keys)) + payload
    table.strings.update(LABELS)
    return table.write()


def tint_material(material, parameter, original, color):
    marker = struct.pack("<IB4f", parameter, 1, *original, 1.0)
    if material.count(marker) != 1:
        raise ValueError("Could not locate the FH2 material color parameter")
    return material.replace(marker, struct.pack("<IB4f", parameter, 1, *color, 1.0))


def material_blobs(model):
    count = struct.unpack_from("<H", model, 6)[0]
    for index in range(count):
        tag, _, _, _, offset, size, _ = BLOB.unpack_from(model, 16 + index * BLOB.size)
        if tag == b"ItaM":
            yield model[offset:offset + size]


def rewrite_material(bundle, replacements):
    data_start = struct.unpack_from("<I", bundle, 8)[0]
    result = bytearray(bundle[:data_start])
    for index in range(2):
        entry = 16 + index * BLOB.size
        tag, major, minor, metadata, offset, size, _ = BLOB.unpack_from(bundle, entry)
        payload = bundle[offset:offset + size]
        for old_ref, new_ref in replacements.get(tag, ()):
            if payload.count(old_ref) != 1:
                raise ValueError("Unexpected material reference")
            payload = payload.replace(old_ref, new_ref)
        result.extend(b"\0" * (-len(result) % 4))
        BLOB.pack_into(result, entry, tag, major, minor, metadata, len(result), len(payload), len(payload))
        result.extend(payload)
    result.extend(b"\0" * (-len(result) % 4))
    struct.pack_into("<I", result, 12, len(result))
    return bytes(result)


def path_ref(path):
    if len(path) >= 128:
        raise ValueError("Resource path exceeds one-byte length encoding")
    return bytes([len(path)]) + path


def retarget(instance, old_name, new_name, car):
    old_path = (b"Game:\\Media\\cars\\_library\\materials\\basematerials\\"
                + old_name + b".materialbin")
    new_path = b"Game:\\Media\\cars\\" + car + b"\\materials\\lightbars\\" + new_name + b".materialbin"
    return rewrite_material(instance, {b"ITAM": [(path_ref(old_path), path_ref(new_path))]})


def texture_ref(path):
    return path_ref(path) + struct.pack("<I", zlib.crc32(path.lower()))


def link_textures(material, assignments, car):
    replacements = []
    for original, name in assignments:
        index = material.index(original)
        start = material.rindex(b"Game:", 0, index)
        end = material.index(b".swatchbin", index) + len(b".swatchbin")
        src = material[start:end]
        dest = b"Game:\\Media\\cars\\" + car + b"\\textures\\lightbars\\" + name.encode("ascii")
        replacements.append((texture_ref(src), texture_ref(dest)))
    return rewrite_material(material, {b"RPTM": replacements})

def build_emitter(marker_model, variant, texture, car):
    """Use the stock Nissan marker's channel-driven lens material instance."""
    channel = bytes.fromhex("0200a0733049040d000000")
    mask_name = b"light_33_mask_"
    template = next(blob for blob in material_blobs(marker_model)
                    if b"\\lbk_custom_001.materialbin" in blob
                    and channel in blob and mask_name in blob
                    and bytes.fromhex("020031c908c301") in blob)
    rgb = (1.0, 0.30, 0.02) if variant == "amber" else (0.035, 0.25, 1.0)
    tint_marker = bytes.fromhex("020031c908c301")
    tint_start = template.index(tint_marker) + len(tint_marker)
    color = template[tint_start:tint_start + 16]
    gain = bytes.fromhex("0200f1c5456f0200000040")
    tinted = rewrite_material(template, {b"RPTM": [
        (tint_marker + color, tint_marker + struct.pack("<4f", *rgb, 1.0)),
        (gain, gain[:-4] + struct.pack("<f", 4.0)),
    ]})
    textured = link_textures(tinted, [(mask_name, texture)], car)
    return tuple(
        rewrite_material(textured, {b"RPTM": [(channel, channel[:-4] + struct.pack("<I", value))]})
        for value in (0x31, 0x32)
    )

def build_lamp_materials(library, marker_model, original_model, variant, textures, car):
    glass_instance = next(blob for blob in material_blobs(marker_model)
                          if b"\\gls_amber.materialbin" in blob)
    plastic_instance = next(blob for blob in material_blobs(original_model)
                            if b"\\basematerials\\blkplastic_mgl.materialbin" in blob)
    glass = library.read("basematerials/gls_amber.materialbin")
    if variant == "blue":
        glass = tint_material(glass, 0x1925D9BF, (1.0, 0.3613068163394928, 0.0),
                              (0.018, 0.22, 1.0))
    glass_name = f"glass_{variant}".encode("ascii")
    lens = retarget(glass_instance, b"gls_amber", glass_name, car)
    positive, negative = build_emitter(marker_model, variant, textures["led"][0], car)
    housing = link_textures(library.read("basematerials/blkplastic_mgl.materialbin"), [
        (b"defaultshaderb_diff_", textures["plastic_color"][0]),
        (b"dtl_roughtexture_001_nrml_", textures["plastic_normal"][0]),
    ], car)
    housing_instance = retarget(plastic_instance, b"blkplastic_mgl", b"housing", car)
    return {0: housing_instance, 1: housing_instance, 2: positive, 3: negative, 4: lens, 5: lens, 6: lens}, {
        f"Materials/lightbars/{glass_name.decode()}.materialbin": glass,
        "Materials/lightbars/housing.materialbin": housing,
    }

def replace_materials(model, materials):
    if model[:6] != b"burG\x01\x00":
        raise ValueError("Expected a converted FH2 model bundle")
    count, data_start = struct.unpack_from("<HI", model, 6)
    result = bytearray(model[:data_start])
    material_ids = set()
    for index in range(count):
        entry = 16 + index * BLOB.size
        tag, major, minor, metadata, offset, size, unpacked = BLOB.unpack_from(model, entry)
        if size != unpacked:
            raise ValueError("Unexpected compressed model blob")
        payload = model[offset:offset + size]
        if tag == b"ItaM":
            # FH2 stores material bindings in the model's per-blob ID metadata.
            if model[metadata + 8:metadata + 14] != b"  dI\x40\x00":
                raise ValueError("Missing material binding ID")
            id_record_size = struct.unpack_from("<H", model, metadata + 14)[0]
            material_id = struct.unpack_from("<I", model, metadata + 8 + id_record_size)[0]
            if material_id in materials:
                payload = materials[material_id]
                material_ids.add(material_id)
        result.extend(b"\0" * (-len(result) % 4))
        BLOB.pack_into(result, entry, tag, major, minor, metadata, len(result), len(payload), len(payload))
        result.extend(payload)
    if material_ids != materials.keys():
        raise ValueError("Unexpected lightbar material slots")
    result.extend(b"\0" * (-len(result) % 4))
    struct.pack_into("<I", result, 12, len(result))
    return bytes(result)


def fix_vertex_layout(model):
    """Match FH2's positional layout indices for a full and shadow layout pair."""
    result = bytearray(model)
    layouts = []
    meshes = []
    count = struct.unpack_from("<H", model, 6)[0]
    for index in range(count):
        tag, _, _, metadata, offset, _, _ = BLOB.unpack_from(model, 16 + index * BLOB.size)
        if tag == b"yaLV":
            key, size, relative = struct.unpack_from("<4sHH", model, metadata)
            if key != b"  dI" or size != 0x40:
                raise ValueError("Unexpected vertex-layout ID metadata")
            layouts.append(metadata + relative)
        elif tag == b"hseM":
            meshes.append(offset)
    ids = [struct.unpack_from("<i", model, offset)[0] for offset in layouts]
    if ids != [1, -1] or not meshes:
        raise ValueError("Unexpected lightbar vertex layout order")
    struct.pack_into("<i", result, layouts[0], 0)
    for offset in meshes:
        if struct.unpack_from("<i", model, offset + 0x31)[0] != 1:
            raise ValueError("Unexpected lightbar mesh layout slot")
        struct.pack_into("<i", result, offset + 0x31, 0)
    return bytes(result)

