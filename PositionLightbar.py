"""Reposition FH2-native roof meshes in the target car's root coordinates."""
import struct

from PackAssets import BLOB


def position_lightbar(model, skeleton, offset_y, offset_z):
    count, start = struct.unpack_from("<HI", model, 6)
    result = bytearray(model[:start])
    translated_position = False
    for index in range(count):
        entry = 16 + index * BLOB.size
        tag, version, metadata_count, metadata, offset, size, _ = BLOB.unpack_from(model, entry)
        payload = model[offset:offset + size]
        metadata_id = None
        for i in range(metadata_count):
            base = metadata + 8 * i
            name, length, relative = struct.unpack_from("<4sHH", model, base)
            if name == b"  dI" and length == 0x40:
                metadata_id = struct.unpack_from("<i", model, base + relative)[0]
            if name == b"xoBB":
                if length != 0x180:
                    raise ValueError("Unexpected lightbar bounds format")
                for component, delta in ((1, offset_y), (2, offset_z), (4, offset_y), (5, offset_z)):
                    address = base + relative + component * 4
                    value = struct.unpack_from("<f", model, address)[0]
                    struct.pack_into("<f", result, address, value + delta)
        if tag == b"lekS":
            payload = skeleton
        elif tag == b"BreV" and metadata_id == -1:
            count_vertices, byte_count, stride, _, _ = struct.unpack_from("<IIHHI", payload)
            if stride != 12 or count_vertices * stride != byte_count or len(payload) != 16 + byte_count:
                raise ValueError("Expected a float3 position stream")
            updated = bytearray(payload)
            for vertex in range(count_vertices):
                address = 16 + vertex * stride + 4
                y, z = struct.unpack_from("<2f", payload, address)
                struct.pack_into("<2f", updated, address, y + offset_y, z + offset_z)
            payload = updated
            translated_position = True
        result.extend(b"\0" * (-len(result) % 4))
        BLOB.pack_into(result, entry, tag, version, metadata_count, metadata, len(result), len(payload), len(payload))
        result.extend(payload)
    if not translated_position:
        raise ValueError("No lightbar position stream found")
    result.extend(b"\0" * (-len(result) % 4))
    struct.pack_into("<I", result, 12, len(result))
    return bytes(result)
