"""Port FH6 4C roof-light attachments to the FH2 light and preset formats."""
import struct

RECORD = struct.Struct("<III16f")
LIGHTBAR_PRESETS = {
    0x507663B0: "amber",
    0x81DBF4E6: "amber",
    0x5FFD7638: "blue",
    0x8E50E16E: "blue",
}
AMBER = (0.865, 0.378, 0.010)
BLUE = (0.010, 0.010, 1.000)
# Four distinct beam ranges let the runtime recognize only our two banks per color.
BANK_RANGES = (8.0625, 8.125, 8.1875, 8.25)


def take_lights(data):
    magic, version, count = struct.unpack_from("<III", data)
    if (magic, version) != (0xDEADBEEF, 1):
        raise ValueError("Expected FH2/FH6 version 1 car lights")
    offset = 12
    attachments = []
    for _ in range(count):
        length = struct.unpack_from("<I", data, offset)[0]
        end = offset + 4 + length + 2
        attachments.append(data[offset:end])
        offset = end
    count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    end = offset + count * RECORD.size
    records = list(RECORD.iter_unpack(data[offset:end]))
    if len(records) != count or len(data) - end != 4:
        raise ValueError("Unexpected light record count or LOD data")
    return attachments, records, data[end:]


def preset_records(data, version):
    magic, size, actual_version, count = struct.unpack_from("<4sIII", data)
    if magic != b"LDFB" or size != len(data) or actual_version != version:
        raise ValueError("Unexpected car light preset format")
    offset = 16
    ids = list(range(count))
    if version == 3:
        ids = struct.unpack_from(f"<{count}I", data, offset)
        offset += 4 * count
    records = {}
    for preset_id in ids:
        length, _ = struct.unpack_from("<II", data, offset)
        records[preset_id] = data[offset:offset + length]
        offset += length
    if offset != len(data):
        raise ValueError("Preset directory does not cover the file")
    return records


def fields(record):
    _, count = struct.unpack_from("<II", record)
    cursor = 8
    result = {}
    for _ in range(count):
        key, size = record[cursor:cursor + 2]
        result[key] = record[cursor + 2:cursor + 2 + size]
        cursor += 2 + size
    return result


def build_roof_lights(stock, donor):
    attachments, lights, suffix = take_lights(stock["Lights.bin"])
    source_attachments, source_lights, _ = take_lights(donor.read("Lights.bin"))
    stock_presets = preset_records(stock["LightPresets.bin"], 1)
    source_presets = preset_records(donor.read("LightPresets.bin"), 3)
    if len(stock_presets) != 12:
        raise ValueError("Unexpected stock 4C preset count")
    slots = {}
    for old_index, attachment in enumerate(source_attachments):
        if b"\\lightbars\\" in attachment.lower():
            slots[old_index] = len(attachments)
            attachments.append(attachment)
    if len(slots) != 2:
        raise ValueError("Expected an FH6 amber and blue model attachment")
    counts = [0, 0, 0, 0]
    for preset, flags, attachment, *transform in source_lights:
        if attachment not in slots:
            continue
        bank = (2 if LIGHTBAR_PRESETS[preset] == "blue" else 0) + ((flags & 0xFF) == 0x32)
        # The plugin drives the two roof channels before FH2 positions attached lights.
        # Keep the glow centered on the lens with a small clearance.
        transform[1] += 0.02
        transform[9] += 0.02
        lights.append((len(stock_presets) + bank, 0x20031 + (bank & 1), slots[attachment], *transform))
        counts[bank] += 1
    if counts != [11, 11, 11, 11]:
        raise ValueError(f"Unexpected FH6 roof-light bank sizes: {counts}")
    stock["Lights.bin"] = (
        struct.pack("<III", 0xDEADBEEF, 1, len(attachments)) + b"".join(attachments)
        + struct.pack("<I", len(lights)) + b"".join(RECORD.pack(*light) for light in lights) + suffix
    )
    records = list(stock_presets.values())
    template = fields(stock_presets[9])
    for bank, light_range in enumerate(BANK_RANGES):
        source = fields(source_presets[0x8E50E16E if bank >= 2 else 0x81DBF4E6])
        attributes = {**template, **source}
        color = struct.pack("<3f", *(BLUE if bank >= 2 else AMBER))
        attributes.update({key: color for key in (0x02, 0x11, 0x1D, 0x28, 0x31)})
        attributes[0x03] = struct.pack("<f", light_range)
        attributes[0x04] = struct.pack("<f", 1.5)
        for tag in (0x08, 0x09):
            attributes[tag] = struct.pack("<f", 0.0)
        attributes[0x0D] = struct.pack("<f", 0.085)
        attributes[0x10] = struct.pack("<f", 2.5)
        payload = b"".join(bytes([key, len(value)]) + value for key, value in sorted(attributes.items()))
        records.append(struct.pack("<II", 8 + len(payload), len(attributes)) + payload)
    payload = b"".join(records)
    stock["LightPresets.bin"] = struct.pack("<4sIII", b"LDFB", 16 + len(payload), 1, len(records)) + payload
