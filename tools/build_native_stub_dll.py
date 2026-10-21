import struct
from pathlib import Path

def build_stub_dll(out_path):
    file_align = 0x200
    sec_align = 0x1000
    image_base = 0x180000000

    # 1. Prepare .text section content
    text_data = bytearray(0x200)
    # DllMain at 0x1000
    text_data[0x00:0x06] = b'\xb8\x01\x00\x00\x00\xc3' # mov eax, 1; ret
    # 0: SetupDiGetClassDevsW at 0x1010
    text_data[0x10:0x18] = b'\x48\xc7\xc0\xff\xff\xff\xff\xc3' # mov rax, -1; ret
    # 1: SetupDiDestroyDeviceInfoList at 0x1020
    text_data[0x20:0x26] = b'\xb8\x01\x00\x00\x00\xc3' # mov eax, 1; ret
    # 2: SetupDiOpenDeviceInterfaceW at 0x1030
    text_data[0x30:0x33] = b'\x31\xc0\xc3' # xor eax, eax; ret
    # 3: SetupDiGetDeviceInterfaceDetailW at 0x1040
    text_data[0x40:0x43] = b'\x31\xc0\xc3' # xor eax, eax; ret
    # 4: SetupDiOpenDevRegKey at 0x1050
    text_data[0x50:0x58] = b'\x48\xc7\xc0\xff\xff\xff\xff\xc3' # mov rax, -1; ret
    # 5: SetupDiEnumDeviceInfo at 0x1060
    text_data[0x60:0x63] = b'\x31\xc0\xc3' # xor eax, eax; ret
    # 6: SetupDiGetClassDevsA at 0x1070
    text_data[0x70:0x78] = b'\x48\xc7\xc0\xff\xff\xff\xff\xc3' # mov rax, -1; ret
    # 7: SetupDiGetDeviceRegistryPropertyW at 0x1080
    text_data[0x80:0x83] = b'\x31\xc0\xc3' # xor eax, eax; ret

    func_rvas = [
        0x1010, # 0: SetupDiGetClassDevsW
        0x1020, # 1: SetupDiDestroyDeviceInfoList
        0x1030, # 2: SetupDiOpenDeviceInterfaceW
        0x1040, # 3: SetupDiGetDeviceInterfaceDetailW
        0x1050, # 4: SetupDiOpenDevRegKey
        0x1060, # 5: SetupDiEnumDeviceInfo
        0x1070, # 6: SetupDiGetClassDevsA
        0x1080, # 7: SetupDiGetDeviceRegistryPropertyW
    ]

    # Exported names sorted alphabetically:
    sorted_exports = [
        ("SetupDiDestroyDeviceInfoList", 1),
        ("SetupDiEnumDeviceInfo", 5),
        ("SetupDiGetClassDevsA", 6),
        ("SetupDiGetClassDevsW", 0),
        ("SetupDiGetDeviceInterfaceDetailW", 3),
        ("SetupDiGetDeviceRegistryPropertyW", 7),
        ("SetupDiOpenDevRegKey", 4),
        ("SetupDiOpenDeviceInterfaceW", 2),
    ]

    edata = bytearray(0x400)
    exp_dir_rva = 0x2000
    functions_rva = 0x2028
    names_rva = 0x2048
    ordinals_rva = 0x2068
    strings_offset = 0x80

    for i, rva in enumerate(func_rvas):
        struct.pack_into('<I', edata, 0x28 + i * 4, rva)

    current_str_offset = strings_offset
    dll_name_bytes = b"setupapx.dll\0"
    edata[current_str_offset:current_str_offset+len(dll_name_bytes)] = dll_name_bytes
    dll_name_rva = exp_dir_rva + current_str_offset
    current_str_offset += len(dll_name_bytes)

    for i, (name, fn_idx) in enumerate(sorted_exports):
        name_bytes = name.encode('ascii') + b'\0'
        edata[current_str_offset:current_str_offset+len(name_bytes)] = name_bytes
        name_rva = exp_dir_rva + current_str_offset
        current_str_offset += len(name_bytes)
        struct.pack_into('<I', edata, 0x48 + i * 4, name_rva)
        struct.pack_into('<H', edata, 0x68 + i * 2, fn_idx)

    struct.pack_into('<IIHHIIIIIII', edata, 0,
                     0, 0, 0, 0,
                     dll_name_rva,
                     1, # Base
                     8, # NumberOfFunctions
                     8, # NumberOfNames
                     functions_rva,
                     names_rva,
                     ordinals_rva)

    header = bytearray(0x200)
    header[0:2] = b'MZ'
    struct.pack_into('<I', header, 0x3C, 0x80)
    header[0x80:0x84] = b'PE\0\0'

    struct.pack_into('<HHIIIHH', header, 0x84,
                     0x8664, 2, 0, 0, 0, 0xF0, 0x2022)

    struct.pack_into('<HBBIIIII', header, 0x98,
                     0x20B, 14, 0, 0x200, 0x400, 0, 0x1000, 0x1000)

    struct.pack_into('<Q', header, 0x98 + 24, image_base)
    struct.pack_into('<II', header, 0x98 + 32, sec_align, file_align)
    struct.pack_into('<HHHHHHI', header, 0x98 + 40,
                     6, 0, 0, 0, 6, 0, 0)
    struct.pack_into('<IIHH', header, 0x98 + 56,
                     0x3000, 0x200, 0, 2)
    struct.pack_into('<H', header, 0x98 + 70, 0x0100) # NX_COMPAT, NO DYNAMIC_BASE
    struct.pack_into('<QQQQII', header, 0x98 + 72,
                     0x100000, 0x1000, 0x100000, 0x1000, 0, 16)

    # Export Directory: RVA 0x2000, Size 0x400
    struct.pack_into('<II', header, 0x108, 0x2000, 0x400)

    # .text section header
    header[0x188:0x190] = b'.text\0\0\0'
    struct.pack_into('<IIIIIIHHI', header, 0x190,
                     0x200, 0x1000, 0x200, 0x200, 0, 0, 0, 0, 0x60000020)

    # .edata section header
    header[0x1B0:0x1B8] = b'.edata\0\0'
    struct.pack_into('<IIIIIIHHI', header, 0x1B8,
                     0x400, 0x2000, 0x400, 0x400, 0, 0, 0, 0, 0x40000040)

    dll_bytes = bytes(header) + bytes(text_data) + bytes(edata)
    Path(out_path).write_bytes(dll_bytes)
    print(f"Generated stub DLL {out_path} ({len(dll_bytes)} bytes) with 8 exports.")

if __name__ == '__main__':
    build_stub_dll('work/setupapx.dll')
