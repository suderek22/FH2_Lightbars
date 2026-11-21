"""Repack selected FH6 PC texture mip chains into FH2 Durango swatchbins."""
import ctypes as ct
import struct
from pathlib import PurePosixPath

from cps.swatch import _Computer, _pitches, read_header

SOURCES = {
    "led": ("lgt_led_002_lite_", "lgt_pattern_002_lite_", 98),
    "lens_mask": ("gradient_011_mask_e5197", "rotor_edge_003_mask_", 80),
    "plastic_color": ("smooth_basecoloralpha_nybn", "gradient_002_diff_", 98),
    "plastic_normal": ("smooth_normal_n965", "rotor_drilled_002_nrml_", 83),
}


def mip_layout(width, height, count, fmt):
    return [_pitches(max(1, width >> level), max(1, height >> level), fmt)
            for level in range(count)]


def read_pc_mips(data, fmt):
    if data[:6] != b"burG\x01\x01" or data[20:24] != b"BCXT":
        raise ValueError("Expected an FH6 PC texture bundle")
    payload_offset, payload_size = struct.unpack_from("<II", data, 32)
    width, height = struct.unpack_from("<II", data, 76)
    count = data[90]
    payload = data[payload_offset:payload_offset + payload_size]
    mips = []
    offset = 0
    for _, length in mip_layout(width, height, count, fmt):
        mips.append(payload[offset:offset + length])
        offset += length
    if offset != len(payload):
        raise ValueError("FH6 texture is not a tightly packed mip chain")
    return (width, height, count), mips


def copy_method(computer, index):
    pointer = ct.c_void_p
    vtable = ct.cast(ct.cast(computer.ptr, ct.POINTER(pointer))[0], ct.POINTER(pointer))
    signature = ct.CFUNCTYPE(ct.c_int, pointer, pointer, ct.c_uint32, ct.c_uint32,
                              pointer, ct.c_uint32, ct.c_uint32)
    return signature(vtable[index])


def transfer(copy, computer, dest, level, source, row, length, detiling=False):
    subresources = (0, level)
    status = copy(computer.ptr, dest, *subresources, source, row, length)
    if status != 0:
        raise ValueError(f"XG copy failed for mip {level}, detiling={detiling}, status={status & 0xffffffff:#x}")


def retile(source, stock, fmt):
    dimensions, source_mips = read_pc_mips(source, fmt)
    width, height, count, _, stock_payload = read_header(stock)
    if dimensions != (width, height, count):
        raise ValueError("FH2 template dimensions or mip count differ from FH6")
    layout = mip_layout(width, height, count, fmt)
    original = ct.create_string_buffer(stock_payload)
    for mode in range(32):
        computer = _Computer(width, height, count, fmt, mode)
        try:
            if not computer.ok or computer.size() != len(stock_payload):
                continue
            to_tiled, from_tiled = (copy_method(computer, index) for index in (8, 9))
            roundtrip = ct.create_string_buffer(len(stock_payload))
            for level, (row, length) in enumerate(layout):
                linear = ct.create_string_buffer(length)
                transfer(from_tiled, computer, linear, level, original, row, length, detiling=True)
                transfer(to_tiled, computer, roundtrip, level, linear, row, length)
            if roundtrip.raw != stock_payload:
                continue
            tiled = ct.create_string_buffer(len(stock_payload))
            for level, ((row, length), mip) in enumerate(zip(layout, source_mips, strict=True)):
                linear = ct.create_string_buffer(mip, length)
                transfer(to_tiled, computer, tiled, level, linear, row, length)
                decoded = ct.create_string_buffer(length)
                transfer(from_tiled, computer, decoded, level, tiled, row, length, detiling=True)
                if decoded.raw != mip:
                    raise ValueError(f"FH2 swatchbin conversion failed to preserve mip {level}")
            header = bytearray(stock[:-len(stock_payload)])
            header[48:64] = source[60:76]  # FH6 source texture GUID
            return bytes(header) + tiled.raw
        finally:
            computer.close()
    raise ValueError("No FH2 template tile mode reproduced the stock mip chain")


def convert_textures(source, stock):
    textures = {}
    for key, (source_prefix, template_prefix, fmt) in SOURCES.items():
        source_name = next(name for name in source.namelist() if source_prefix in name)
        template = next(name for name in stock.namelist() if template_prefix in name)
        name = PurePosixPath(source_name).name
        textures[key] = (name, retile(source.read(source_name), stock.read(template), fmt))
    return textures
