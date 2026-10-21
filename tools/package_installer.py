"""Package luaVietsup Pro into a high-compression, single-file Solid SFX installer with custom icon."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RAR_EXE = Path(r"C:\Program Files\WinRAR\Rar.exe")
OUTPUT_NAME = "Setup_luaVietsup_Pro_v2.6.exe"
STAGING_DIR = ROOT / "work" / "staging"
SFX_CONFIG = ROOT / "work" / "sfx_config.txt"
ICON_PATH = ROOT / "source" / "assets" / "luaVietsup" / "icon.ico"
CUSTOM_SFX = ROOT / "work" / "luaVietsup.sfx"

# Training-only cudnn DLLs, duplicate alt DLLs, and SDK headers
# NOTE: CUDA 12 cublas64_12.dll is kept in _internal/ctranslate2/ and nvidia/cublas/bin/.
#       CUDA 12 cublasLt64_12.dll is kept in _internal/ctranslate2/ (where CTranslate2 loads it).
#       CUDA 11 cublas/cudnn DLLs are kept in _internal/torch/lib/ (where PyTorch loads them).
#       Excluding the duplicates from nvidia/cublas/bin and nvidia/cudnn/bin prevents the installer
#       from exceeding the Windows PE 4 GB SFX limit while maintaining 100% full GPU functionality.
EXCLUDES = {
    os.path.normpath("_internal/nvidia/cuda_nvrtc/bin/nvrtc64_120_0.alt.dll"),
    os.path.normpath("_internal/nvidia/cudnn/bin/cudnn_cnn_train64_8.dll"),
    os.path.normpath("_internal/nvidia/cudnn/bin/cudnn_adv_train64_8.dll"),
    os.path.normpath("_internal/nvidia/cudnn/bin/cudnn_ops_train64_8.dll"),
    os.path.normpath("_internal/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"),
    # Exclude CUDA 12 LT duplicate from nvidia/cublas/bin (kept in ctranslate2/)
    os.path.normpath("_internal/nvidia/cublas/bin/cublasLt64_12.dll"),
    # Exclude CUDA 11 duplicates from nvidia/cublas/bin (identical copies are in torch/lib/)
    os.path.normpath("_internal/nvidia/cublas/bin/cublasLt64_11.dll"),
    os.path.normpath("_internal/nvidia/cublas/bin/cublas64_11.dll"),
    # Exclude cuDNN 9 duplicates from nvidia/cudnn/bin (identical copies are in torch/lib/)
    os.path.normpath("_internal/nvidia/cudnn/bin/cudnn_engines_precompiled64_9.dll"),
    os.path.normpath("_internal/nvidia/cudnn/bin/cudnn_adv64_9.dll"),
    os.path.normpath("_internal/nvidia/cudnn/bin/cudnn_ops64_9.dll"),
}

EXCLUDE_DIRS = {
    os.path.normpath("_internal/paddle/include"),
    os.path.normpath("_internal/nvidia/cudnn/include"),
    os.path.normpath("_internal/nvidia/cuda_nvrtc/include"),
    os.path.normpath("_internal/nvidia/cublas/include"),
    os.path.normpath("_internal/nvidia/cudnn/lib"),
}


def prepare_staging():
    print("[1/3] Preparing clean optimized staging directory...", flush=True)
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Main executable
    main_exe = ROOT / "luaVietsup-ModelFix4.exe"
    if not main_exe.is_file():
        raise FileNotFoundError("Missing luaVietsup-ModelFix4.exe")
    os.link(str(main_exe), str(STAGING_DIR / main_exe.name))

    # 2. Native stub dll
    stub_dll = ROOT / "setupapx.dll"
    if not stub_dll.is_file():
        raise FileNotFoundError("Missing setupapx.dll")
    os.link(str(stub_dll), str(STAGING_DIR / stub_dll.name))

    # 3. Helper files
    shutil.copy2(ROOT / "work" / "CHAY_luaVietsup.bat", STAGING_DIR / "CHAY_luaVietsup.bat")
    shutil.copy2(ROOT / "work" / "HUONG_DAN_SU_DUNG.txt", STAGING_DIR / "HUONG_DAN_SU_DUNG.txt")

    # 4. _internal directory with optimized exclusions
    internal_src = ROOT / "_internal"
    internal_dst = STAGING_DIR / "_internal"
    
    file_count = 0
    total_bytes = 0
    saved_bytes = 0

    for root, dirs, files in os.walk(internal_src):
        rel_dir = os.path.normpath(str(Path(root).relative_to(ROOT)))
        if any(rel_dir.startswith(d) for d in EXCLUDE_DIRS):
            for f in files:
                saved_bytes += (Path(root) / f).stat().st_size
            continue

        rel = os.path.relpath(root, internal_src)
        target_dir = internal_dst / rel if rel != "." else internal_dst
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            src_file = Path(root) / f
            rel_f = os.path.normpath(str(Path(root).relative_to(ROOT) / f))
            sz = src_file.stat().st_size

            if rel_f in EXCLUDES or rel_f.endswith(".lib") or rel_f.endswith(".pdb"):
                saved_bytes += sz
                continue

            dst_file = target_dir / f
            try:
                os.link(str(src_file), str(dst_file))
            except Exception:
                shutil.copy2(src_file, dst_file)
            file_count += 1
            total_bytes += sz

    print(f"Staged {file_count} files ({total_bytes / (1024*1024):.2f} MB, {total_bytes / (1024**3):.2f} GB).", flush=True)
    print(f"Excluded {saved_bytes / (1024*1024):.2f} MB ({saved_bytes / (1024**3):.2f} GB) of redundant/unused bloat.", flush=True)


def prepare_custom_sfx():
    print("[2/3] Preparing branded SFX stub with custom logo icon...", flush=True)
    sfx_src = Path(r"C:\Program Files\WinRAR\Default.SFX")
    if not sfx_src.is_file():
        raise FileNotFoundError("Default.SFX not found in WinRAR")
    shutil.copy2(sfx_src, CUSTOM_SFX)

    if ICON_PATH.is_file():
        from tools.embed_pe_icon import update
        update(str(CUSTOM_SFX), str(ICON_PATH))
        print("Branded icon embedded into SFX stub.", flush=True)


def build_sfx():
    print("[3/3] Compressing with WinRAR Solid (-s -m4 -md64m)...", flush=True)
    output_exe = ROOT / OUTPUT_NAME
    if output_exe.exists():
        output_exe.unlink()

    cmd = [
        str(RAR_EXE),
        "a",
        f"-sfx{CUSTOM_SFX}", # Use our branded SFX module
        "-s",                 # Solid archive
        "-m4",                # Good compression ratio with high speed
        "-md64m",             # 64MB dictionary
        "-r",                 # Recursive
        f"-z{SFX_CONFIG}",    # SFX script configuration
        "-y",                 # Assume yes
        str(output_exe),
        "*",
    ]

    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(STAGING_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    elapsed = time.time() - t0

    if proc.returncode != 0:
        print("WinRAR output (last 2000 chars):\n", proc.stdout[-2000:], flush=True)
        raise RuntimeError(f"WinRAR failed with returncode {proc.returncode}")

    print(f"Compression completed in {elapsed:.1f}s ({elapsed/60:.1f} minutes).", flush=True)


def cleanup():
    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    if CUSTOM_SFX.exists():
        CUSTOM_SFX.unlink()

    output_exe = ROOT / OUTPUT_NAME
    if output_exe.is_file():
        sz_mb = output_exe.stat().st_size / (1024 * 1024)
        sz_gb = sz_mb / 1024

        # Hardlink to Desktop for immediate access
        desktop_link = Path(os.environ["USERPROFILE"]) / "Desktop" / OUTPUT_NAME
        if desktop_link.exists():
            desktop_link.unlink()
        try:
            os.link(str(output_exe), str(desktop_link))
            print(f"Created shortcut on Desktop: {desktop_link}", flush=True)
        except Exception:
            pass

        print("\n" + "="*60, flush=True)
        print("INSTALLER BUILD SUCCESSFUL!", flush=True)
        print(f"File: {output_exe}", flush=True)
        print(f"Size: {sz_mb:.2f} MB ({sz_gb:.2f} GB)", flush=True)
        print("="*60, flush=True)


def main():
    prepare_staging()
    prepare_custom_sfx()
    build_sfx()
    cleanup()


if __name__ == "__main__":
    main()
