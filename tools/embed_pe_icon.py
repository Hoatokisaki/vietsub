"""Replace a Windows executable's embedded icon resources from a multi-size ICO."""
import ctypes
import struct
import sys
from pathlib import Path


RT_ICON = 3
RT_GROUP_ICON = 14
GROUP_ICON_ID = 1
LANG_NEUTRAL = 0


def int_resource(value):
    return ctypes.c_void_p(value & 0xFFFF)


def read_ico(path):
    data = Path(path).read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or image_type != 1 or count == 0:
        raise ValueError("Input is not a Windows ICO file")
    images = []
    group = bytearray(struct.pack("<HHH", 0, 1, count))
    for index in range(count):
        at = 6 + index * 16
        width, height, colors, reserved, planes, bpp, size, offset = struct.unpack_from("<BBBBHHII", data, at)
        blob = data[offset:offset + size]
        if len(blob) != size:
            raise ValueError(f"ICO image {index} is truncated")
        resource_id = index + 1
        images.append((resource_id, blob))
        group.extend(struct.pack("<BBBBHHIH", width, height, colors, reserved,
                                 planes, bpp, size, resource_id))
    return images, bytes(group)


def update(exe_path, ico_path):
    if sys.platform != "win32":
        raise RuntimeError("Windows resource updates must run on Windows")
    exe = Path(exe_path).resolve()
    images, group = read_ico(ico_path)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.BeginUpdateResourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
    kernel.BeginUpdateResourceW.restype = ctypes.c_void_p
    kernel.UpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_ushort, ctypes.c_void_p, ctypes.c_uint]
    kernel.UpdateResourceW.restype = ctypes.c_int
    kernel.EndUpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    kernel.EndUpdateResourceW.restype = ctypes.c_int

    handle = kernel.BeginUpdateResourceW(str(exe), 0)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        resources = [(RT_ICON, resource_id, blob) for resource_id, blob in images]
        resources.append((RT_GROUP_ICON, GROUP_ICON_ID, group))
        for kind, resource_id, blob in resources:
            buffer = ctypes.create_string_buffer(blob)
            ok = kernel.UpdateResourceW(handle, int_resource(kind), int_resource(resource_id),
                                        LANG_NEUTRAL, buffer, len(blob))
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.EndUpdateResourceW(handle, 0):
            handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        handle = None
    finally:
        if handle:
            kernel.EndUpdateResourceW(handle, 1)
    print(f"Embedded {len(images)} icon sizes into {exe.name}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: embed_pe_icon.py <application.exe> <icon.ico>")
    update(sys.argv[1], sys.argv[2])
