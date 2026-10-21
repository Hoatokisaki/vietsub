"""Rebuild the original CPython 3.10 PyInstaller CArchive, without DLL rescanning.

The decompiled entry point is compiled by the original app's Python runtime.
Unverified decompilations and PyArmor modules remain original bytecode in PYZ.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NAME = "luaVietsup-ModelFix4.exe"
MAGIC = b"MEI\014\013\012\013\016"


def archive(path):
    data = path.read_bytes()
    cookie_at = data.rfind(MAGIC)
    _, length, toc_off, toc_len, pyver, pylib = struct.unpack("!8sIIII64s", data[cookie_at:cookie_at+88])
    start = cookie_at + 88 - length
    toc = data[start+toc_off:start+toc_off+toc_len]
    items = []
    at = 0
    while at < len(toc):
        size, off, packed, unpacked, compressed, typ = struct.unpack("!IIIIBc", toc[at:at+18])
        name = toc[at+18:at+size].rstrip(b"\0").decode("utf-8")
        blob = data[start+off:start+off+packed]
        raw = zlib.decompress(blob) if compressed else blob
        assert len(raw) == unpacked, name
        items.append((name, typ, compressed, raw, blob))
        at += size
    return data[:start], items, pyver, pylib


def compact_ico(source, destination, sizes=(16, 24, 32)):
    """Keep small branded icon variants so resource growth cannot move .reloc."""
    data = source.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or image_type != 1 or count == 0:
        raise ValueError("Input is not a Windows ICO file")
    wanted = set(sizes)
    selected = []
    for index in range(count):
        at = 6 + index * 16
        entry = bytearray(data[at:at + 16])
        width = entry[0] or 256
        height = entry[1] or 256
        if width not in wanted or height not in wanted:
            continue
        size = struct.unpack_from("<I", entry, 8)[0]
        offset = struct.unpack_from("<I", entry, 12)[0]
        blob = data[offset:offset + size]
        if len(blob) != size:
            raise ValueError(f"ICO image {index} is truncated")
        selected.append((entry, blob))
        wanted.discard(width)
        wanted.discard(height)
    if wanted or not selected:
        raise ValueError("ICO is missing requested small sizes: " + repr(sorted(wanted)))
    cursor = 6 + 16 * len(selected)
    entries = []
    blobs = []
    for entry, blob in selected:
        struct.pack_into("<I", entry, 12, cursor)
        entries.append(bytes(entry))
        blobs.append(blob)
        cursor += len(blob)
    header = struct.pack("<HHH", reserved, image_type, len(selected))
    destination.write_bytes(header + b"".join(entries) + b"".join(blobs))
    print("Prepared compact icon with sizes " + ", ".join(str(entry[0] or 256) for entry, _ in selected))


def carchive_start(data):
    """Return the PE file offset where its PyInstaller CArchive begins."""
    cookie_at = data.rfind(MAGIC)
    if cookie_at < 0 or cookie_at + 88 > len(data):
        raise ValueError("Could not find a complete PyInstaller CArchive cookie")
    length = struct.unpack_from("!I", data, cookie_at + 8)[0]
    start = cookie_at + 88 - length
    if start < 0 or start > cookie_at:
        raise ValueError("Invalid PyInstaller CArchive bounds")
    return start


def repair_pe_resource_shift(data, original_data):
    """Repair PE RVAs after Windows' resource updater grows and moves sections."""
    image = bytearray(data)
    pe_at = struct.unpack_from("<I", image, 0x3C)[0]
    if image[pe_at:pe_at + 4] != b"PE\0\0":
        raise ValueError("Icon-updated executable has no valid PE signature")
    section_count = struct.unpack_from("<H", image, pe_at + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe_at + 20)[0]
    optional_at = pe_at + 24
    original_pe_at = struct.unpack_from("<I", original_data, 0x3C)[0]
    original_optional_at = original_pe_at + 24
    original_optional_size = struct.unpack_from("<H", original_data, original_pe_at + 20)[0]
    original_section_count = struct.unpack_from("<H", original_data, original_pe_at + 6)[0]
    section_alignment = struct.unpack_from("<I", image, optional_at + 32)[0]
    if not section_alignment:
        raise ValueError("PE SectionAlignment is zero")
    section_at = optional_at + optional_size
    section_ends = []
    new_sections = {}
    for index in range(section_count):
        header = section_at + index * 40
        name = bytes(image[header:header + 8].split(b"\0", 1)[0])
        virtual_size, virtual_address = struct.unpack_from("<II", image, header + 8)
        section_ends.append(virtual_address + virtual_size)
        new_sections[name] = (virtual_address, virtual_size)
    if not section_ends:
        raise ValueError("PE has no sections")

    original_section_at = original_optional_at + original_optional_size
    original_sections = {}
    for index in range(original_section_count):
        header = original_section_at + index * 40
        name = bytes(original_data[header:header + 8].split(b"\0", 1)[0])
        virtual_size, virtual_address = struct.unpack_from("<II", original_data, header + 8)
        original_sections[name] = (virtual_address, virtual_size)

    def moved_rva(old_rva):
        for name, (old_va, old_size) in original_sections.items():
            if old_va <= old_rva < old_va + old_size and name in new_sections:
                new_va, _ = new_sections[name]
                return old_rva + (new_va - old_va)
        return old_rva

    # UpdateResourceW may move the later section RVA, but on this PyInstaller
    # PE it leaves AddressOfEntryPoint at its old RVA. Update the entry point
    # and any data-directory RVA that belonged to a moved section.
    old_entry = struct.unpack_from("<I", original_data, original_optional_at + 16)[0]
    struct.pack_into("<I", image, optional_at + 16, moved_rva(old_entry))
    optional_magic = struct.unpack_from("<H", image, optional_at)[0]
    directories_offset, count_offset = ((112, 108) if optional_magic == 0x20B else (96, 92))
    directory_count = struct.unpack_from("<I", image, optional_at + count_offset)[0]
    original_directory_count = struct.unpack_from("<I", original_data, original_optional_at + count_offset)[0]
    for index in range(min(directory_count, original_directory_count)):
        old_rva = struct.unpack_from("<I", original_data, original_optional_at + directories_offset + index * 8)[0]
        if old_rva:
            new_rva = moved_rva(old_rva)
            current_size = struct.unpack_from("<I", image, optional_at + directories_offset + index * 8 + 4)[0]
            struct.pack_into("<II", image, optional_at + directories_offset + index * 8, new_rva, current_size)

    max_end = max(section_ends)
    expected = ((max_end + section_alignment - 1) // section_alignment) * section_alignment
    struct.pack_into("<I", image, optional_at + 56, expected)
    return bytes(image), expected, moved_rva(old_entry)


def pe_raw_file_end(data):
    """Return the minimum file length required by the PE section table."""
    pe_at = struct.unpack_from("<I", data, 0x3C)[0]
    section_count = struct.unpack_from("<H", data, pe_at + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_at + 20)[0]
    section_at = pe_at + 24 + optional_size
    ends = []
    for index in range(section_count):
        header = section_at + index * 40
        raw_size, raw_pointer = struct.unpack_from("<II", data, header + 16)
        ends.append(raw_pointer + raw_size)
    return max(ends, default=0)


def pack(prefix, entries, pyver, pylib, target_size=None, trailer=b""):
    chunks = []; toc = []; off = 0
    for entry in entries:
        name, typ, compressed, raw = entry[:4]
        stored_blob = entry[4] if len(entry) > 4 else None
        blob = stored_blob if stored_blob is not None else (zlib.compress(raw, 9) if compressed else raw)
        if compressed and zlib.decompress(blob) != raw:
            raise ValueError("Compressed CArchive entry does not match its contents: " + name)
        if not compressed and blob != raw:
            raise ValueError("Uncompressed CArchive entry does not match its contents: " + name)
        name_data = name.encode("utf-8") + b"\0"
        entry_size = 18 + len(name_data)
        entry_size = (entry_size + 15) // 16 * 16
        toc.append(struct.pack("!IIIIBc", entry_size, off, len(blob), len(raw), compressed, typ) + name_data.ljust(entry_size-18,b"\0"))
        chunks.append(blob); off += len(blob)
    toc = b"".join(toc)
    archive_length = off + len(toc) + 88
    padding = 0
    if target_size is not None:
        padding = target_size - len(prefix) - archive_length - len(trailer)
        if padding < 0:
            raise ValueError("Rebuilt archive and PE entry-point trailer exceed section capacity")
    cookie = struct.pack("!8sIIII64s", MAGIC, archive_length + padding, off, len(toc), pyver, pylib)
    return prefix+b"".join(chunks)+toc+(b"\0"*padding)+cookie+trailer


def main():
    (ROOT / "work").mkdir(parents=True, exist_ok=True)
    (ROOT / "evidence").mkdir(parents=True, exist_ok=True)
    original = ROOT / "backup" / "SirVietsub_v2.6.original.exe"
    if not original.exists():
        raise SystemExit("Missing backup/SirVietsub_v2.6.original.exe")
    runner = ROOT / NAME
    build_exe = ROOT / "work" / NAME
    build_exe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, build_exe)
    brand_assets = ROOT / "source" / "assets" / "luaVietsup"
    shutil.copy2(brand_assets / "icon.ico", ROOT / "_internal" / "icon.ico")
    shutil.copy2(brand_assets / "icon.png", ROOT / "_internal" / "icon.png")
    shutil.copy2(ROOT / 'source' / 'patches' / 'sir_recovered_runtime.py', ROOT / '_internal' / 'sir_recovered_runtime.py')
    shutil.copy2(ROOT / 'source' / 'patches' / 'chatgpt_web.py', ROOT / '_internal' / 'chatgpt_web.py')
    shutil.copy2(ROOT / 'source' / 'patches' / 'custom_api.py', ROOT / '_internal' / 'custom_api.py')
    shutil.copy2(ROOT / 'source' / 'patches' / 'translation_rules.py', ROOT / '_internal' / 'translation_rules.py')
    shutil.copy2(ROOT / 'source' / 'patches' / 'license_runtime.py', ROOT / '_internal' / 'license_runtime.py')
    service_config = ROOT / 'source' / 'patches' / 'license_service_config.json'
    if service_config.is_file():
        shutil.copy2(service_config, ROOT / '_internal' / 'license_service_config.json')
    public_key = ROOT / 'source' / 'patches' / 'license_public_key.pem'
    if public_key.is_file():
        shutil.copy2(public_key, ROOT / '_internal' / 'license_public_key.pem')
    # Keep the original PYZ's PyArmor import wrapper, not unrelated experimental
    # hooks left in the installed application's filesystem __init__.py.
    shutil.copy2(ROOT / 'source' / 'runtime' / 'pyarmor_runtime_000000' / '__init__.py', ROOT / '_internal' / 'pyarmor_runtime_000000' / '__init__.py')

    # Ensure native setupapx.dll and patched qwindows.dll are in place to prevent WinError 1114 on Qt platform plugin load
    stub_src = ROOT / "work" / "setupapx.dll"
    if not stub_src.is_file():
        from tools.build_native_stub_dll import build_stub_dll
        build_stub_dll(str(stub_src))
    for target_dir in [
        ROOT / "_internal" / "PyQt6" / "Qt6" / "plugins" / "platforms",
        ROOT / "_internal" / "PyQt6" / "Qt6" / "bin",
        ROOT / "_internal" / "onnxruntime" / "capi",
        ROOT / "_internal",
        ROOT,
    ]:
        target_dir.mkdir(parents=True, exist_ok=True)
        dst_dll = target_dir / "setupapx.dll"
        if not dst_dll.is_file() or dst_dll.stat().st_size != stub_src.stat().st_size:
            try:
                shutil.copy2(stub_src, dst_dll)
            except Exception:
                pass
    for patch_rel in [
        ROOT / "_internal" / "PyQt6" / "Qt6" / "plugins" / "platforms" / "qwindows.dll",
        ROOT / "_internal" / "onnxruntime" / "capi" / "onnxruntime_pybind11_state.pyd",
        ROOT / "_internal" / "onnxruntime" / "capi" / "onnxruntime.dll",
    ]:
        if patch_rel.is_file():
            p_data = bytearray(patch_rel.read_bytes())
            s_idx = p_data.find(b"SETUPAPI.dll\0")
            if s_idx != -1:
                p_data[s_idx:s_idx + 13] = b"setupapx.dll\0"
                patch_rel.write_bytes(p_data)
    helper = ROOT / "tools" / "runtime_prepare.py"
    compile_runner = ROOT / "luaVietsup.exe"
    if not compile_runner.exists():
        compile_runner = ROOT / "SirVietsub-REA-Updated.exe"
    if not compile_runner.exists():
        compile_runner = ROOT / NAME
    if not compile_runner.exists():
        raise SystemExit("Missing compiler runner, required to run the recovered-source compiler")
    result = subprocess.run([str(compile_runner), "--run-script", str(helper), "compile"], timeout=60, cwd=str(ROOT))
    if result.returncode:
        raise SystemExit(f"CPython 3.10 compile failed: {result.returncode}")
    status = (ROOT / "evidence" / "runtime_status.txt").read_text(encoding="utf-8")
    if status != "PASS compile":
        raise SystemExit(status)
    base_exe = ROOT / "luaVietsup.exe"
    if not base_exe.is_file() and (ROOT / NAME).is_file():
        base_exe = ROOT / NAME
    if base_exe.is_file():
        base_data = base_exe.read_bytes()
        cookie_at = base_data.rfind(MAGIC)
        trailer = base_data[cookie_at + 88:]
        prefix, entries, pyver, pylib = archive(base_exe)
        target_size = len(base_data)
    else:
        original_prefix, entries, pyver, pylib = archive(original)
        icon_base = ROOT / "work" / "luaVietsup_iconbase.exe"
        embedded_icon = ROOT / "work" / "luaVietsup_embedded.ico"
        compact_ico(brand_assets / "icon.ico", embedded_icon)
        shutil.copy2(original, icon_base)
        icon_update = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "embed_pe_icon.py"), str(icon_base), str(embedded_icon)],
            timeout=60,
            cwd=str(ROOT),
        )
        if icon_update.returncode:
            raise SystemExit(f"Could not embed luaVietsup icon: {icon_update.returncode}")
        icon_data = icon_base.read_bytes()
        icon_data, corrected_image_size, corrected_entrypoint = repair_pe_resource_shift(icon_data, original.read_bytes())
        orig_data = original.read_bytes()
        cookie_orig = orig_data.rfind(MAGIC)
        trailer = orig_data[cookie_orig + 88:]
        target_size = len(orig_data)
        cstart = carchive_start(icon_data)
        prefix = icon_data[:cstart]
        if icon_base.exists():
            icon_base.unlink()

    main_bytes = (ROOT / "work" / "compiled" / "main.marshal").read_bytes()
    rebuilt = [(n,t,c,main_bytes,None) if n=="main" else (n,t,c,raw,blob)
               for n,t,c,raw,blob in entries]
    build_exe.write_bytes(pack(prefix, rebuilt, pyver, pylib, target_size=target_size, trailer=trailer))
    # Re-read the emitted archive: verify every retained member byte-for-byte.
    _, actual, actual_pyver, _ = archive(build_exe)
    assert actual_pyver==310
    for old, new in zip(entries,actual):
        assert old[:3]==new[:3]
        if old[0]!="main": assert old[3]==new[3],old[0]
    copied = False
    for attempt in range(3):
        try:
            shutil.copy2(build_exe, runner)
            copied = True
            break
        except Exception:
            time.sleep(1.0)
    if not copied:
        print("[Notice] Target " + str(runner.name) + " is currently in use. Build artifact ready at " + str(build_exe.name))

    # Sync to C:\SirVietsub_Pro if directory exists
    pro_dir = Path("C:/SirVietsub_Pro")
    if pro_dir.is_dir():
        try:
            shutil.copy2(build_exe, pro_dir / NAME)
            for sync_rel in [
                "setupapx.dll",
                "QUAN_LY_PREMIUM_TU_XA.exe",
                "_internal/setupapx.dll",
                "_internal/PyQt6/Qt6/bin/setupapx.dll",
                "_internal/PyQt6/Qt6/plugins/platforms/setupapx.dll",
                "_internal/PyQt6/Qt6/plugins/platforms/qwindows.dll",
                "_internal/onnxruntime/capi/setupapx.dll",
                "_internal/onnxruntime/capi/onnxruntime_pybind11_state.pyd",
                "_internal/onnxruntime/capi/onnxruntime.dll",
                "_internal/onnxruntime/capi/onnxruntime_validation.py",
                "_internal/sir_recovered_runtime.py",
                "_internal/chatgpt_web.py",
                "_internal/custom_api.py",
                "_internal/translation_rules.py",
                "_internal/license_runtime.py",
            ]:
                src_p = ROOT / sync_rel
                dst_p = pro_dir / sync_rel
                if src_p.is_file():
                    dst_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_p, dst_p)
            print("Successfully synced all patched files to " + str(pro_dir))
        except Exception as e:
            print("Warning syncing to C:/SirVietsub_Pro:", e)

    info={"type":"decompiled-entrypoint-rebuild-with-original-PYZ", "display_name":"luaVietsup", "icon":"source/assets/luaVietsup/icon.ico", "original_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),"output":str(runner),"output_sha256":hashlib.sha256(runner.read_bytes()).hexdigest(),"main_source_sha256":hashlib.sha256((ROOT/'source'/'main.py').read_bytes()).hexdigest(),"python":pyver,"retained_entries_verified":len(entries)-1,"original_PYZ_sha256":hashlib.sha256(next(e[3] for e in entries if e[0]=='PYZ.pyz')).hexdigest()}
    info['runtime_patch_sha256']=hashlib.sha256((ROOT / '_internal' / 'sir_recovered_runtime.py').read_bytes()).hexdigest()
    info['runtime_wrapper_sha256']=hashlib.sha256((ROOT / '_internal' / 'pyarmor_runtime_000000' / '__init__.py').read_bytes()).hexdigest()
    (ROOT / "evidence" / "build_manifest.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BUILD PASS: " + str(runner).encode('ascii', 'replace').decode('ascii'))
    print("SHA256: " + info["output_sha256"])


if __name__ == "__main__":
    main()
