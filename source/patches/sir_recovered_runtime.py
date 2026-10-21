"""Small reviewed fixes over the original PYZ, not the recreation project.

Only the explicitly replaced methods below change. Protected render/ASR/voice
cores and license decisions stay in their original modules.
"""
import math
import os
import re
import subprocess
import tempfile
import time
import wave
import ctypes
import sys
from pathlib import Path

INSTALLED = False


def ensure_cuda_dll_paths():
    """Ensure CUDA 11 & 12, CuDNN, and PyTorch DLLs can be loaded by CTranslate2, ONNX, and PyTorch."""
    try:
        base_dir = getattr(sys, '_MEIPASS', None)
        if not base_dir:
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
            cand = os.path.join(base_dir, '_internal')
            if os.path.isdir(cand):
                base_dir = cand
        if not base_dir or not os.path.isdir(base_dir):
            return

        for sub in (
            ('nvidia', 'cublas', 'bin'),
            ('nvidia', 'cudnn', 'bin'),
            ('nvidia', 'cuda_runtime', 'bin'),
            ('nvidia', 'cuda_nvrtc', 'bin'),
            ('torch', 'lib'),
            ('ctranslate2',),
            ('ffmpeg',),
        ):
            folder = os.path.join(base_dir, *sub)
            if os.path.isdir(folder):
                if hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(folder)
                    except Exception:
                        pass
                os.environ['PATH'] = folder + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass

ensure_cuda_dll_paths()


def rebrand_visible_sirvietsub(root):
    """Update recovered labels whose original brand is still inside the PYZ."""
    try:
        from PyQt6.QtWidgets import QWidget
        changed = 0
        for widget in root.findChildren(QWidget):
            getter = getattr(widget, "text", None)
            setter = getattr(widget, "setText", None)
            if not callable(getter) or not callable(setter):
                continue
            try:
                text = getter()
                if isinstance(text, str) and "SirVietsub" in text:
                    setter(text.replace("SirVietsub", "luaVietsup"))
                    changed += 1
            except Exception:
                continue
        _voice_log("Rebranded %d visible labels" % changed)
        return changed
    except Exception as exc:
        _voice_log("Visible-label rebrand failed: %r" % (exc,))
        return 0


def _voice_log(message):
    try:
        base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "SirVietsub" / "Logs"
        base.mkdir(parents=True, exist_ok=True)
        with (base / "rea_voice_preview.log").open("a", encoding="utf-8") as fp:
            fp.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except Exception:
        pass


def install():
    global INSTALLED
    if INSTALLED:
        return
    from PyQt6.QtCore import QRectF, QUrl
    from PyQt6.QtGui import QFontMetrics
    from app.views.home_interface import SrtListWidget
    from app.views.video_overlay import VideoCanvasWidget
    from app.views.tts_interface import TTSInterface

    def load_srt(self, srt_path):
        # Accept UTF-8 BOM and all newline forms, and keep the original editor
        # widgets/pagination. Do not swallow the parse error into a blank list.
        content = Path(srt_path).read_text(encoding="utf-8-sig")
        raw_cleaned = re.sub(r'\[(sirvietsub|luavietsup)\]\s*', '', content, flags=re.IGNORECASE)
        if raw_cleaned != content:
            content = raw_cleaned
            try:
                Path(srt_path).write_text(content, encoding="utf-8")
            except Exception:
                pass
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        blocks = [block.strip() for block in re.split(r"\n\s*\n", content.strip()) if block.strip()]
        valid = []
        stamp = re.compile(r"\d{1,3}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{1,3}:\d{2}:\d{2}[,.]\d{3}")
        for block in blocks:
            lines = block.splitlines()
            if lines and stamp.search(lines[0]):
                lines.insert(0, str(len(valid)+1))
            if len(lines)>=2 and stamp.search(lines[1]):
                valid.append("\n".join(lines))
        if content.strip() and not valid:
            raise ValueError("File SRT không có mốc thời gian hợp lệ: " + str(srt_path))
        # Reuse the page's item widgets. Repeatedly detaching/deleting Fluent
        # text widgets with deferred UI work pending can invalidate callbacks.
        self.all_blocks = valid
        self.current_page = 0
        self.render_page(False)

    SrtListWidget.load_srt = load_srt
    def clear_srt(self):
        self.all_blocks=[]
        self.current_page=0
        for item in self.items:
            item.block_idx=-1
            item.hide()
        self.pageChanged.emit(1,1)
    SrtListWidget.clear=clear_srt

    original_video_rect=VideoCanvasWidget._getVideoRect
    def video_rect(self):
        if self.width()<=0 or self.height()<=0:
            return 0.0,0.0,float(max(0,self.width())),float(max(0,self.height()))
        return original_video_rect(self)
    VideoCanvasWidget._getVideoRect=video_rect

    try:
        from app.views.home_interface import HomeInterface
        orig_home_init = HomeInterface.__init__
        def safe_home_init(self, *args, **kwargs):
            res = orig_home_init(self, *args, **kwargs)
            try:
                setup_chatgpt_home_ui(self)
            except Exception:
                pass
            return res
        HomeInterface.__init__ = safe_home_init
    except Exception:
        pass

    def finite(value, default):
        try:
            value=float(value)
            return value if math.isfinite(value) else default
        except (TypeError,ValueError):
            return default

    def fitted_rect(original, kind):
        def calculate(self, vx, vy, vw, vh):
            rel_x=kind+"_rel_x"; rel_y=kind+"_rel_y"; scale_key=kind+"_scale"
            setattr(self,rel_x,finite(getattr(self,rel_x,0.5),0.5))
            setattr(self,rel_y,finite(getattr(self,rel_y,0.5),0.5))
            setattr(self,scale_key,max(0.02,min(3.0,finite(getattr(self,scale_key,1.0),1.0))))
            rect,font=original(self,vx,vy,vw,vh)
            if font is None or vw<=0 or vh<=0:
                return rect,font
            text=getattr(self,kind+"_text","")
            pad=min(4.0,vw*0.01,vh*0.01)
            available_w=max(1.0,vw-2*pad); available_h=max(1.0,vh-2*pad)
            def measure():
                fm=QFontMetrics(font)
                lines=text.splitlines() or [""]
                return float(max(fm.horizontalAdvance(line) for line in lines)),float(fm.height()*len(lines))
            tw,th=measure()
            for _ in range(4):
                factor=min(1.0,available_w/max(tw,1),available_h/max(th,1))
                if factor>=1.0:
                    break
                old_size=max(0.1,font.pointSizeF())
                new_size=max(0.1,old_size*factor*0.97)
                font.setPointSizeF(new_size)
                setattr(self,scale_key,getattr(self,scale_key)*(new_size/old_size))
                tw,th=measure()
            tw=min(tw,available_w); th=min(th,available_h)
            x_min=(tw/2+pad)/vw; y_min=(th/2+pad)/vh
            x=max(x_min,min(1-x_min,getattr(self,rel_x)))
            y=max(y_min,min(1-y_min,getattr(self,rel_y)))
            setattr(self,rel_x,x); setattr(self,rel_y,y)
            for key in (rel_x,rel_y,scale_key):
                self.config[key]=getattr(self,key)
            return QRectF(vx+x*vw-tw/2,vy+y*vh-th/2,tw,th),font
        return calculate

    VideoCanvasWidget._getWMRect=fitted_rect(VideoCanvasWidget._getWMRect,"wm")
    VideoCanvasWidget._getSubRect=fitted_rect(VideoCanvasWidget._getSubRect,"sub")

    def normalize(self):
        vx,vy,vw,vh=self._getVideoRect()
        if vw>0 and vh>0:
            self._getWMRect(vx,vy,vw,vh)
            self._getSubRect(vx,vy,vw,vh)

    def normalized_method(original):
        def wrapped(self,*args,**kwargs):
            result=original(self,*args,**kwargs)
            normalize(self)
            return result
        return wrapped

    for method in ("applyConfig","mouseMoveEvent","setWatermarkText"):
        setattr(VideoCanvasWidget,method,normalized_method(getattr(VideoCanvasWidget,method)))
    original_save=VideoCanvasWidget.saveConfig
    def save_config(self):
        normalize(self)
        return original_save(self)
    VideoCanvasWidget.saveConfig=save_config
    original_frame=VideoCanvasWidget.setVideoFrame
    def set_frame(self,frame):
        before=(self.native_vw,self.native_vh)
        result=original_frame(self,frame)
        if before!=(self.native_vw,self.native_vh):
            save_config(self)
        return result
    VideoCanvasWidget.setVideoFrame=set_frame

    # Qt 6.11's FFmpeg multimedia plug-in can terminate the whole process when
    # it receives some concatenated/stream-produced MP3 files.  The TTS core is
    # left untouched; preview is normalised to PCM WAV with the bundled FFmpeg
    # and played by the Windows waveOut path instead of feeding that MP3 to Qt.
    def _preview_wav(source):
        source = Path(source).resolve()
        cache = Path(tempfile.gettempdir()) / "SirVietsub-REA-preview"
        cache.mkdir(parents=True, exist_ok=True)
        target = cache / (source.stem + "_preview.wav")
        ffmpeg = os.environ.get("FFMPEG_BINARY") or os.environ.get("IMAGEIO_FFMPEG_EXE") or "ffmpeg"
        command = [ffmpeg, "-y", "-v", "error", "-i", str(source),
                   "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(target)]
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode != 0 or not target.is_file() or target.stat().st_size <= 44:
            detail = completed.stderr.decode("utf-8", "replace")[-800:]
            raise RuntimeError("FFmpeg preview failed: " + detail)
        return target

    def _safe_play(self, source):
        try:
            ctypes.windll.winmm.PlaySoundW(None, None, 0)
            wav_path = _preview_wav(source)
            # SND_FILENAME | SND_ASYNC | SND_NODEFAULT.  Calling winmm
            # directly keeps this patch self-contained because the original
            # PyInstaller bundle does not include CPython's winsound.pyd.
            if not ctypes.windll.winmm.PlaySoundW(str(wav_path), None, 0x00020003):
                raise RuntimeError("Windows waveOut rejected the preview file")
            self._rea_preview_playing = True
            self.btn_play.setText("Dừng")
            _voice_log("PLAY source=%s preview=%s" % (source, wav_path))
            try:
                with wave.open(str(wav_path), "rb") as wav:
                    duration_ms = int(1000 * wav.getnframes() / max(1, wav.getframerate()))
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(max(250, duration_ms + 100), lambda: _preview_ended(self))
            except Exception:
                pass
            return True
        except Exception as exc:
            self._rea_preview_playing = False
            self.btn_play.setText("Phát")
            _voice_log("ERROR source=%s error=%r" % (source, exc))
            self.lbl_status.setText("Đã tạo file; nghe thử gặp lỗi. Xem rea_voice_preview.log")
            return False

    def _preview_ended(self):
        self._rea_preview_playing = False
        self.btn_play.setText("Phát")

    original_tts_finished=TTSInterface._on_finished
    def tts_finished(self,result,success):
        original_tts_finished(self,result,success)
        if not success:
            return
        path=Path(str(result))
        if not path.is_file():
            _voice_log("MISSING result=%r" % (result,))
            return
        # Select the exact generated file and preview only after it has been
        # completely closed by TTSWorker.
        for i in range(self.list_history.count()):
            item=self.list_history.item(i)
            if item.text()==path.name:
                self.list_history.blockSignals(True)
                self.list_history.clearSelection()
                self.list_history.setCurrentItem(item)
                item.setSelected(True)
                self.list_history.blockSignals(False)
                break
        _safe_play(self, path)

    def safe_toggle_play(self, *args):
        if getattr(self, "_rea_preview_playing", False):
            safe_stop_audio(self)
            return
        items = self.list_history.selectedItems()
        item = items[0] if len(items) == 1 else self.list_history.currentItem()
        if item is None:
            return
        path = Path(self.line_output.text().strip()) / item.text()
        if path.is_file():
            _safe_play(self, path)

    def safe_stop_audio(self, *args):
        try:
            ctypes.windll.winmm.PlaySoundW(None, None, 0)
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass
        _preview_ended(self)

    TTSInterface._on_finished=tts_finished
    TTSInterface._toggle_play=safe_toggle_play
    TTSInterface._stop_audio=safe_stop_audio
    install_espeak_patch()
    install_render_patch()
    install_transcribe_patch()
    install_chatgpt_translation_patch()
    install_speed_optimizations()
    INSTALLED=True


SPEED_OPTIMIZATIONS_INSTALLED = False


def install_speed_optimizations():
    global SPEED_OPTIMIZATIONS_INSTALLED
    if SPEED_OPTIMIZATIONS_INSTALLED:
        return

    # 1. Step 1: Faster-Whisper (Original transcription decoding & VAD restored, multi-core CPU preserved)
    try:
        from faster_whisper import WhisperModel
        orig_wm_init = WhisperModel.__init__

        def speed_wm_init(self, model_size_or_path, *args, **kwargs):
            import multiprocessing
            cores = multiprocessing.cpu_count()
            dev = kwargs.get("device")
            if dev == "cpu" or dev is None:
                kwargs["cpu_threads"] = max(kwargs.get("cpu_threads", 0), cores)
                kwargs["num_workers"] = max(kwargs.get("num_workers", 0), 2)
            _voice_log(f"WhisperModel init optimized: threads={kwargs.get('cpu_threads')}, workers={kwargs.get('num_workers')}")
            return orig_wm_init(self, model_size_or_path, *args, **kwargs)

        WhisperModel.__init__ = speed_wm_init
        _voice_log("Step 1 (Whisper) original decoding restored (VAD filter & beam search unchanged from defaults)")
    except Exception as exc:
        _voice_log(f"Whisper speed patch error: {exc!r}")

    # 2. Step 3: Concurrency booster for TTS voice generation
    try:
        import concurrent.futures
        orig_tpe_init = concurrent.futures.ThreadPoolExecutor.__init__

        def speed_tpe_init(self, max_workers=None, *args, **kwargs):
            import multiprocessing
            cores = multiprocessing.cpu_count()
            if max_workers is not None and max_workers <= 6:
                # Boost default 5 workers to 16 workers for concurrent TTS audio generation
                max_workers = max(12, cores + 4)
            return orig_tpe_init(self, max_workers=max_workers, *args, **kwargs)

        concurrent.futures.ThreadPoolExecutor.__init__ = speed_tpe_init
        _voice_log("Step 3 (TTS concurrency) speed optimization installed")
    except Exception as exc:
        _voice_log(f"TTS concurrency patch error: {exc!r}")

    SPEED_OPTIMIZATIONS_INSTALLED = True


ESPEAK_PATCH_INSTALLED = False


def install_espeak_patch():
    global ESPEAK_PATCH_INSTALLED
    if ESPEAK_PATCH_INSTALLED:
        return
    # Fix for piper-tts / espeak-ng crash when generating voice on Windows:
    # 1. espeak-ng C library uses ANSI fopen() which fails if the application
    #    directory contains non-ASCII characters (e.g. Vietnamese 'dịc sir').
    # 2. Piper passes the subdirectory '.../espeak-ng-data' to espeak_Initialize,
    #    but espeak-ng on Windows expects the parent directory that contains
    #    'espeak-ng-data'.
    # When initialization fails, espeak-ng aborts/exits the process immediately
    # ("văng app"). We sanitize the path into an ASCII 8.3 short path or copy
    # the data to %TEMP%\SirVietsub_espeak as a robust fallback.
    try:
        import piper.phonemize_espeak as pe
        import piper.voice as pv
        from piper import espeakbridge
        import shutil

        def _get_safe_espeak_dir(requested=None):
            base_internal = Path(os.path.dirname(sys.executable)) / "_internal" / "piper"
            if not base_internal.exists():
                base_internal = Path(__file__).resolve().parent / "piper"
            if not base_internal.exists():
                base_internal = Path(__file__).resolve().parent.parent / "_internal" / "piper"

            candidates = []
            if requested:
                r = Path(requested).resolve()
                candidates.append(r)
                if r.name == "espeak-ng-data":
                    candidates.append(r.parent)
            candidates.append(base_internal)

            found_parent = None
            for cand in candidates:
                if (cand / "espeak-ng-data" / "phontab").is_file():
                    found_parent = cand
                    break
                if (cand / "phontab").is_file():
                    found_parent = cand.parent
                    break
            if not found_parent:
                found_parent = base_internal

            if os.name == "nt":
                buf = ctypes.create_unicode_buffer(512)
                ctypes.windll.kernel32.GetShortPathNameW(str(found_parent), buf, 512)
                short_val = buf.value
                if short_val and all(ord(c) < 128 for c in short_val) and (Path(short_val) / "espeak-ng-data" / "phontab").is_file():
                    return Path(short_val)

                temp_root = Path(tempfile.gettempdir()) / "SirVietsub_espeak"
                temp_root.mkdir(parents=True, exist_ok=True)
                temp_data = temp_root / "espeak-ng-data"
                if not (temp_data / "phontab").is_file():
                    src_data = found_parent / "espeak-ng-data"
                    if src_data.is_dir():
                        shutil.copytree(src_data, temp_data, dirs_exist_ok=True)
                return temp_root

            return found_parent

        safe_dir = _get_safe_espeak_dir()
        orig_espeak_init = espeakbridge.initialize
        _espeak_init_done = [False]

        def safe_espeak_init(path=None):
            if not _espeak_init_done[0]:
                target = str(_get_safe_espeak_dir(path))
                orig_espeak_init(target)
                _espeak_init_done[0] = True

        espeakbridge.initialize = safe_espeak_init
        safe_espeak_init()

        pe.ESPEAK_DATA_DIR = safe_dir
        pv.ESPEAK_DATA_DIR = safe_dir
        pv._ESPEAK_PHONEMIZER = pe.EspeakPhonemizer(safe_dir)
        ESPEAK_PATCH_INSTALLED = True
        _voice_log("PIPER/ESPEAK initialized with safe_dir=%s" % safe_dir)
    except Exception as _espeak_err:
        _voice_log("PIPER/ESPEAK patch error=%r" % (_espeak_err,))


RENDER_PATCH_INSTALLED = False


def install_render_patch():
    global RENDER_PATCH_INSTALLED
    if RENDER_PATCH_INSTALLED:
        return

    def get_short_path(p):
        if os.name == 'nt' and os.path.exists(p):
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.kernel32.GetShortPathNameW(str(p), buf, 512)
            if buf.value:
                return buf.value
        return str(p)

    project_root = str(Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent)
    short_project_root = get_short_path(project_root)

    known_replacements = []
    candidates = [project_root]
    try:
        appdata_dir = os.getenv('APPDATA')
        if appdata_dir:
            cfg_path = os.path.join(appdata_dir, 'SirVietsub', 'config.json')
            if os.path.exists(cfg_path):
                import json as _json
                with open(cfg_path, 'r', encoding='utf-8') as _cf:
                    _cdata = _json.load(_cf)
                    if _cdata.get('output_dir'):
                        candidates.append(_cdata['output_dir'])
    except Exception:
        pass

    for orig in candidates:
        if orig and os.path.exists(orig):
            short = get_short_path(orig)
            if short and orig != short:
                known_replacements.append((orig, short))
                known_replacements.append((orig.replace('\\', '/'), short.replace('\\', '/')))
                known_replacements.append((orig.replace('\\', '/').replace(':', '\\:'), short.replace('\\', '/').replace(':', '\\:')))

    _enc_cache = {}
    render_threads = [max(1, os.cpu_count() or 1)]
    render_license_status = ["free"]

    def has_full_license(status):
        return str(status or "").strip().casefold() in {"premium", "paid"}

    def make_unlicensed_srt(source_path, workspace_dir):
        """Create a render-only SRT with a branded cue every 15 subtitle entries."""
        if not source_path or not os.path.isfile(source_path):
            return source_path
        try:
            source = Path(source_path)
            content = source.read_text(encoding="utf-8-sig")
            blocks = [b for b in re.split(r"\r?\n[ \t]*\r?\n", content.strip()) if b.strip()]
            timestamp = re.compile(r"^\s*\d{1,3}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{1,3}:\d{2}:\d{2}[,.]\d{3}")
            cue_index = 0
            output = []
            for block in blocks:
                lines = block.splitlines()
                time_index = next((i for i, line in enumerate(lines) if timestamp.match(line)), None)
                if time_index is None:
                    output.append(block)
                    continue
                cue_index += 1
                lines = [line for line in lines if line.strip() != "[Lụa-Vietsub]"]
                if cue_index % 15 == 0:
                    lines.append("[Lụa-Vietsub]")
                output.append("\n".join(lines))
            if cue_index == 0:
                return source_path
            target_dir = Path(workspace_dir) if workspace_dir else source.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / (source.stem + "_luaVietsup_free.srt")
            target.write_text("\n\n".join(output) + "\n", encoding="utf-8")
            return str(target)
        except Exception as exc:
            _voice_log("Subtitle watermark injection failed: %r" % (exc,))
            return source_path

    def is_codec_supported(enc_name):
        if enc_name in _enc_cache:
            return _enc_cache[enc_name]
        ffmpeg_exe = os.environ.get("FFMPEG_BINARY") or os.environ.get("IMAGEIO_FFMPEG_EXE") or "ffmpeg"
        try:
            cmd = [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=1", "-c:v", enc_name, "-f", "null", "-"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            _enc_cache[enc_name] = (res.returncode == 0)
        except Exception:
            _enc_cache[enc_name] = False
        return _enc_cache[enc_name]

    orig_popen = subprocess.Popen

    class RobustPopen(orig_popen):
        def __init__(self, cmd, *args, **kwargs):
            if isinstance(cmd, list) and len(cmd) > 0 and 'ffmpeg' in str(cmd[0]).lower():
                new_cmd = []
                for item in cmd:
                    if isinstance(item, str):
                        for orig, short in known_replacements:
                            if orig in item:
                                item = item.replace(orig, short)
                    new_cmd.append(item)

                output_path = str(new_cmd[-1]) if len(new_cmd) > 1 else ""
                is_render = ("-y" in new_cmd) and any(x in new_cmd for x in ("-filter_complex", "-vf", "-c:v"))
                video_output = is_render and (Path(output_path).suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"})

                # Ensure FFmpeg runs in the workspace directory so relative subtitle and font files are found
                if not kwargs.get('cwd') and output_path:
                    target_cwd = os.path.dirname(output_path)
                    if target_cwd and os.path.isdir(target_cwd):
                        kwargs['cwd'] = target_cwd

                # Clean up legacy SirVietsub drawtext filter syntax that causes FFmpeg filter parsing errors
                if "-filter_complex" in new_cmd:
                    fc_idx = new_cmd.index("-filter_complex")
                    if fc_idx + 1 < len(new_cmd):
                        fc_val = str(new_cmd[fc_idx + 1])
                        if "pingvaocode" in fc_val or "SIRVIETSUB" in fc_val:
                            fc_val = re.sub(r'\[v_anticopy\]drawtext=.*?,subtitles=', '[v_anticopy]subtitles=', fc_val)
                            new_cmd[fc_idx + 1] = fc_val

                is_stream_copy = False
                if "-c:v" in new_cmd:
                    idx = new_cmd.index("-c:v")
                    enc = new_cmd[idx + 1].lower() if idx + 1 < len(new_cmd) else ""
                    if enc == "copy":
                        is_stream_copy = True
                    else:
                        hardware_codecs = {
                            "h264_nvenc", "h264_amf", "h264_qsv", "h264_videotoolbox",
                            "hevc_nvenc", "hevc_amf", "hevc_qsv", "hevc_videotoolbox",
                            "av1_nvenc", "av1_amf", "av1_qsv",
                        }
                        if enc in hardware_codecs:
                            new_cmd[idx + 1] = "libx264"
                            hardware_only = {"-rc", "-qp_i", "-qp_p", "-spatial_aq", "-temporal_aq", "-aq-strength", "-b_ref_mode", "-multipass", "-surfaces"}
                            i = 0
                            while i < len(new_cmd):
                                if new_cmd[i] in hardware_only:
                                    del new_cmd[i:min(i + 2, len(new_cmd))]
                                else:
                                    i += 1
                        if "-cq" in new_cmd:
                            cq_index = new_cmd.index("-cq")
                            new_cmd[cq_index] = "-crf"
                        if "-preset" in new_cmd:
                            preset_index = new_cmd.index("-preset")
                            if preset_index + 1 < len(new_cmd) and (new_cmd[preset_index + 1].startswith("p") or new_cmd[preset_index + 1] in {"slow", "medium", "fast"}):
                                new_cmd[preset_index + 1] = "veryfast"
                        try:
                            from app.core.video_renderer import get_cpu_threads
                            thread_count = max(1, int(get_cpu_threads()))
                        except Exception:
                            thread_count = max(1, min(16, int((os.cpu_count() or 4) * 0.75)))
                        render_threads[0] = thread_count
                        insert_options = []
                        if "-threads" in new_cmd:
                            thread_index = new_cmd.index("-threads")
                            if thread_index + 1 < len(new_cmd):
                                new_cmd[thread_index + 1] = str(thread_count)
                        else:
                            insert_options.extend(["-threads", str(thread_count)])
                        if "-preset" not in new_cmd:
                            insert_options.extend(["-preset", "veryfast"])
                        if "-crf" not in new_cmd:
                            insert_options.extend(["-crf", "23"])
                        if insert_options and len(new_cmd) > 1 and not str(new_cmd[-1]).startswith("-"):
                            new_cmd[-1:-1] = insert_options

                # Bake watermark only for full video renders, never for stream copy or probe
                joined_cmd = " ".join(str(part) for part in new_cmd)
                if (not has_full_license(render_license_status[0]) and video_output
                        and not is_stream_copy
                        and "testsrc=" not in joined_cmd.lower()
                        and "_silent_audio_fixed" not in joined_cmd.lower()
                        and "@lua-vietsub-d9y" not in joined_cmd.casefold()):
                    drawtext = "drawtext=text='@Lua-Vietsub-d9y':x=w-tw-16:y=16:fontcolor=white@0.08:fontsize=14"
                    filter_index = next((i for i, part in enumerate(new_cmd[:-1]) if str(part) in {"-vf", "-filter:v", "-filter"}), None)
                    complex_filter_present = any(str(part) == "-filter_complex" for part in new_cmd[:-1])
                    if filter_index is not None and filter_index + 1 < len(new_cmd):
                        new_cmd[filter_index + 1] = str(new_cmd[filter_index + 1]) + "," + drawtext
                    elif not complex_filter_present:
                        new_cmd[-1:-1] = ["-vf", drawtext]
                    metadata_index = next((i for i, part in enumerate(new_cmd[:-1]) if str(part) == "-metadata"), None)
                    if metadata_index is None:
                        new_cmd[-1:-1] = ["-metadata", "comment=@Lua-Vietsub-d9y"]
                    elif metadata_index + 1 < len(new_cmd) and str(new_cmd[metadata_index + 1]).startswith("comment="):
                        new_cmd[metadata_index + 1] = "comment=@Lua-Vietsub-d9y"
                cmd = new_cmd
            super().__init__(cmd, *args, **kwargs)

    subprocess.Popen = RobustPopen

    try:
        from app.common import font_manager as fm
        orig_get_font_file = fm.get_font_file
        def safe_get_font_file(display_name):
            fpath = orig_get_font_file(display_name)
            if fpath:
                return get_short_path(fpath)
            return fpath
        fm.get_font_file = safe_get_font_file
    except Exception:
        pass

    try:
        import app.core.video_renderer as vr
        import app.common.workers as workers
        orig_render_logic = getattr(vr, "render_logic", None)

        def safe_render_logic(video_path, srt_path, audio_path, workspace_dir, status_cb, cancel_event, license_status=None, video_config=None):
            if video_config is None:
                video_config = {}
            if not isinstance(video_config, dict):
                video_config = dict(video_config)

            try:
                import app.core.security as core_sec
                license_status = getattr(core_sec, "CURRENT_LICENSE_STATUS", None) or license_status or "free"
            except Exception:
                license_status = license_status or "free"

            if not has_full_license(license_status):
                srt_path = make_unlicensed_srt(srt_path, workspace_dir)
            render_license_status[0] = license_status

            try:
                from app.core.video_renderer import get_cpu_threads
                render_threads[0] = max(1, int(get_cpu_threads()))
            except Exception:
                render_threads[0] = max(1, min(16, int((os.cpu_count() or 4) * 0.75)))

            # Check if video has audio; if not, attach silent audio track to prevent FFmpeg [0:a] filter crash
            temp_silent_video = None
            render_video_input = video_path
            try:
                _b = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(sys.executable), '_internal'))
                _ff = os.environ.get('FFMPEG_BINARY') or os.path.join(_b, 'ffmpeg', 'ffmpeg.exe')
                if not os.path.exists(_ff):
                    _ff = 'ffmpeg'
                probe = subprocess.run(
                    [_ff, '-i', str(video_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if "Audio:" not in probe.stderr:
                    temp_dir = os.path.join(workspace_dir, "Data")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_silent_video = os.path.join(temp_dir, "_silent_audio_fixed.mp4")
                    sub_res = subprocess.run(
                        [
                            _ff, '-y',
                            '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                            '-i', str(video_path),
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            '-shortest',
                            temp_silent_video
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=60,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    if sub_res.returncode == 0 and os.path.exists(temp_silent_video) and os.path.getsize(temp_silent_video) > 0:
                        render_video_input = temp_silent_video
            except Exception:
                pass

            user_wanted_gpu = bool(video_config.get("use_gpu"))
            if user_wanted_gpu:
                video_config["render_codec"] = "h264_nvenc"
                video_config["use_gpu"] = True
                video_config["render_preset"] = "p4"
            else:
                video_config["render_codec"] = "libx264"
                video_config["use_gpu"] = False
                video_config["cpu_threads"] = render_threads[0]
                video_config["render_preset"] = "veryfast"

            try:
                return orig_render_logic(render_video_input, srt_path, audio_path, workspace_dir, status_cb, cancel_event, license_status, video_config)
            except Exception as e:
                err_text = str(e).lower()
                # If GPU failed, or codec error, cleanly fallback to multi-threaded CPU libx264:
                if user_wanted_gpu or "nvenc" in err_text or "not in list" in err_text or "codec" in err_text or isinstance(e, ValueError):
                    try:
                        if callable(status_cb):
                            status_cb("Chuyển sang CPU render để đảm bảo xuất video thành công...", 0.1)
                    except Exception:
                        pass
                    video_config["render_codec"] = "libx264"
                    video_config["use_gpu"] = False
                    video_config["cpu_threads"] = render_threads[0]
                    video_config["render_preset"] = "veryfast"
                    return orig_render_logic(render_video_input, srt_path, audio_path, workspace_dir, status_cb, cancel_event, license_status, video_config)
                raise
            finally:
                render_license_status[0] = "free"
                if temp_silent_video and os.path.exists(temp_silent_video):
                    try:
                        os.remove(temp_silent_video)
                    except Exception:
                        pass

        vr.render_logic = safe_render_logic
        workers.render_logic = safe_render_logic
    except Exception:
        pass

    RENDER_PATCH_INSTALLED = True


TRANSCRIBE_PATCH_INSTALLED = False


def install_transcribe_patch():
    global TRANSCRIBE_PATCH_INSTALLED
    if TRANSCRIBE_PATCH_INSTALLED:
        return

    def clean_srt_watermarks(path_or_dir):
        if not path_or_dir or not os.path.exists(path_or_dir):
            return
        try:
            if os.path.isfile(path_or_dir) and path_or_dir.lower().endswith(".srt"):
                content = Path(path_or_dir).read_text(encoding="utf-8-sig")
                cleaned = re.sub(r'\[(sirvietsub|luavietsup)\]\s*', '', content, flags=re.IGNORECASE)
                if cleaned != content:
                    Path(path_or_dir).write_text(cleaned, encoding="utf-8")
            elif os.path.isdir(path_or_dir):
                for root, _, files in os.walk(path_or_dir):
                    for f in files:
                        if f.lower().endswith(".srt"):
                            sp = os.path.join(root, f)
                            clean_srt_watermarks(sp)
        except Exception:
            pass

    try:
        import app.core.transcriber as transcriber
        import app.common.workers as workers
        orig_transcribe_logic = getattr(transcriber, "transcribe_logic", None)

        def safe_transcribe_logic(video_path, status_cb, cancel_event, workspace_dir, model_size='base', source_lang='auto', arg_ocr_bbox=None):
            res = orig_transcribe_logic(video_path, status_cb, cancel_event, workspace_dir, model_size, source_lang, arg_ocr_bbox)

            clean_srt_watermarks(workspace_dir)
            if isinstance(res, str) and res.lower().endswith(".srt"):
                clean_srt_watermarks(res)
            return res

        transcriber.transcribe_logic = safe_transcribe_logic
        workers.transcribe_logic = safe_transcribe_logic
    except Exception:
        pass

    TRANSCRIBE_PATCH_INSTALLED = True




def hide_contact_information(root):
    """Hide obsolete HWID and contact controls from the account card."""
    try:
        from PyQt6.QtWidgets import QWidget

        license_group = getattr(root, "group_license", None) or root
        hidden = set()

        def widget_text(widget):
            parts = []
            for attr in ("text", "toolTip", "accessibleName"):
                value = getattr(widget, attr, None)
                try:
                    value = value() if callable(value) else value
                except Exception:
                    value = ""
                if value:
                    parts.append(str(value))
            return " ".join(parts).casefold()

        def hide_layout_contents(layout):
            for index in range(layout.count()):
                item = layout.itemAt(index)
                child_widget = item.widget()
                child_layout = item.layout()
                if child_widget is not None:
                    child_widget.hide()
                    hidden.add(id(child_widget))
                if child_layout is not None:
                    hide_layout_contents(child_layout)
            layout.setSpacing(0)
            layout.setContentsMargins(0, 0, 0, 0)

        def visit_layout(layout):
            if layout is None:
                return
            direct_widgets = []
            child_layouts = []
            text_parts = []
            for index in range(layout.count()):
                item = layout.itemAt(index)
                child_widget = item.widget()
                child_layout = item.layout()
                if child_widget is not None:
                    direct_widgets.append(child_widget)
                    text_parts.append(widget_text(child_widget))
                if child_layout is not None:
                    child_layouts.append(child_layout)
            combined = " ".join(text_parts)
            contact_row = any(token in combined for token in (
                "telegram", "bio", "contact", "liên hệ", "liã", "thông tin liên hệ"
            ))
            if contact_row:
                for child_widget in direct_widgets:
                    child_widget.hide()
                    hidden.add(id(child_widget))
                for child_layout in child_layouts:
                    hide_layout_contents(child_layout)
                layout.setSpacing(0)
                layout.setContentsMargins(0, 0, 0, 0)
                return
            for child_layout in child_layouts:
                visit_layout(child_layout)

        visit_layout(license_group.layout())
        for widget in license_group.findChildren(QWidget):
            text = widget_text(widget)
            if "admin" in text or "renew" in text:
                widget.hide()
                hidden.add(id(widget))
        _voice_log("Hidden %d obsolete HWID/contact widgets" % len(hidden))
        return len(hidden)
    except Exception as exc:
        _voice_log("HWID/contact UI patch failed: %r" % (exc,))
        return 0


def add_hwid_copy_controls(root):
    """Show the current HWID and let the owner copy it for license approval."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton
        from app.common import security
        try:
            import license_runtime
        except Exception:
            license_runtime = None

        group = getattr(root, "group_license", None)
        layout = group.layout() if group is not None else None
        if layout is None or getattr(group, "_lua_hwid_controls_added", False):
            return False
        hwid = str(security.get_hwid())
        row = QHBoxLayout()
        label = QLabel("HWID thiết bị: " + hwid, group)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        button = QPushButton("Sao chép HWID", group)
        button.setToolTip("Sao chép mã thiết bị để cấp quyền trong hệ thống quản lý bản quyền.")

        def copy_hwid():
            QApplication.clipboard().setText(hwid)
            button.setToolTip("Đã sao chép HWID.")

        button.clicked.connect(copy_hwid)
        row.addWidget(label, 1)
        row.addWidget(button)
        layout.addLayout(row)

        group._lua_hwid_controls_added = True
        return True
    except Exception as exc:
        _voice_log("HWID copy control failed: %r" % (exc,))
        return False


def install_model_download_fixes():
    """Make extension-model downloads use writable caches and report real failures."""
    try:
        import os
        import subprocess
        import sys
        import tempfile
        import textwrap
        from pathlib import Path

        from app.common import config_manager
        from app.views import setting_interface

        original_get_models_dir = getattr(
            config_manager.get_models_dir,
            "_luavietsup_original",
            config_manager.get_models_dir,
        )

        def is_writable_directory(path):
            try:
                os.makedirs(path, exist_ok=True)
                fd, probe = tempfile.mkstemp(prefix=".luaVietsup-write-check-", dir=path)
                os.close(fd)
                os.remove(probe)
                return True
            except Exception:
                return False

        def get_writable_models_dir():
            try:
                preferred = original_get_models_dir()
                if is_writable_directory(preferred):
                    return preferred
            except Exception as exc:
                _voice_log("Primary model cache is unavailable: %r" % (exc,))
            local_app_data = os.environ.get("LOCALAPPDATA")
            if not local_app_data:
                local_app_data = str(Path.home() / "AppData" / "Local")
            fallback = os.path.join(local_app_data, "luaVietsup", "models")
            os.makedirs(fallback, exist_ok=True)
            if not is_writable_directory(fallback):
                raise OSError("Cannot write model cache to " + fallback)
            return fallback

        get_writable_models_dir._luavietsup_original = original_get_models_dir
        config_manager.get_models_dir = get_writable_models_dir

        worker_cls = setting_interface.ModelDownloaderWorker
        if getattr(worker_cls, "_luavietsup_download_patch", False):
            return True

        def run_script(self, python_exe, script):
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8:replace"
            env["PYTHONUTF8"] = "1"
            env["HF_HUB_DISABLE_SYMLINKS"] = "1"
            env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            env["HF_HUB_DISABLE_TELEMETRY"] = "1"
            # The parent Qt app may have unpacked PyInstaller to a different
            # temporary directory. Never let the model worker load that
            # process's Qt plugins; the child bootloader configures its bundle.
            for name in (
                "QT_PLUGIN_PATH",
                "QT_QPA_PLATFORM_PLUGIN_PATH",
                "QT_QPA_FONTDIR",
            ):
                env.pop(name, None)
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            if hasattr(sys, "_MEIPASS"):
                ffmpeg_dir = os.path.join(sys._MEIPASS, "ffmpeg")
                if os.path.isdir(ffmpeg_dir):
                    env["BUNDLE_FFMPEG_DIR"] = ffmpeg_dir
            script_path = None
            try:
                fd, script_path = tempfile.mkstemp(
                    prefix="luaVietsup-model-", suffix=".py", text=True
                )
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as script_file:
                    script_file.write("# -*- coding: utf-8 -*-\n")
                    script_file.write(script)
                process = subprocess.Popen(
                    [python_exe, "--run-script", script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
            except Exception as exc:
                if script_path and os.path.isfile(script_path):
                    try:
                        os.remove(script_path)
                    except OSError:
                        pass
                self.progress.emit("Không thể khởi chạy trình tải model: %s" % exc)
                return False

            if process.stdout is not None:
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        self.progress.emit(line)
            return_code = process.wait()
            if script_path and os.path.isfile(script_path):
                try:
                    os.remove(script_path)
                except OSError:
                    pass
            if return_code != 0:
                self.progress.emit("Tải model thất bại (mã tiến trình %s)." % return_code)
                return False
            return True

        def make_script(setup_lines, body_lines):
            body = textwrap.indent("\n".join(body_lines), "    ")
            return "\n".join(
                setup_lines
                + [
                    "import sys",
                    "for stream in (sys.stdout, sys.stderr):",
                    "    try:",
                    "        stream.reconfigure(encoding='utf-8', errors='replace')",
                    "    except (AttributeError, OSError, ValueError):",
                    "        pass",
                    "try:",
                    body,
                    "except BaseException as exc:",
                    "    error_text = repr(exc)",
                    "    if len(error_text) > 1200:",
                    "        error_text = error_text[:1200] + '...[truncated]'",
                    "    print('DOWNLOAD_ERROR: ' + type(exc).__name__ + ': ' + error_text, file=sys.stderr, flush=True)",
                    "    try:",
                    "        tb = exc.__traceback__",
                    "        while tb is not None:",
                    "            code = tb.tb_frame.f_code",
                    "            print('  at %s:%s in %s' % (code.co_filename, tb.tb_lineno, code.co_name), file=sys.stderr, flush=True)",
                    "            tb = tb.tb_next",
                    "    except BaseException:",
                    "        pass",
                    "    sys.exit(1)",
                ]
            )

        def run(self):
            target = getattr(self, "target_model", "all")
            whisper_names = {
                "whisper_tiny": [("Chế độ 1", "tiny")],
                "whisper_base": [("Chế độ 2", "base")],
                "whisper_small": [("Chế độ 3", "small")],
                "whisper_medium": [("Chế độ 4", "medium")],
                "whisper_large-v3": [("Chế độ 5", "large-v3")],
            }
            all_whisper = [
                ("Chế độ 1", "tiny"),
                ("Chế độ 2", "base"),
                ("Chế độ 3", "small"),
                ("Chế độ 4", "medium"),
                ("Chế độ 5", "large-v3"),
            ]
            tasks = []
            if target in ("all", "whisper") or target in whisper_names:
                models = all_whisper if target in ("all", "whisper") else whisper_names[target]
                from app.common.config_manager import get_hf_cache_dir

                hf_home = get_hf_cache_dir()
                whisper_setup = [
                    "import os, warnings, logging",
                    "os.environ['HF_HOME'] = " + repr(hf_home),
                    "os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'",
                    "os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'",
                    "os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'",
                    "warnings.filterwarnings('ignore')",
                    "logging.getLogger('huggingface_hub').setLevel(logging.ERROR)",
                ]
                whisper_body = [
                    "from faster_whisper import WhisperModel",
                    "models = " + repr(models),
                    "failures = []",
                    "for label, model_size in models:",
                    "    print(f'Đang kiểm tra/tải {label}...', flush=True)",
                    "    try:",
                    "        WhisperModel(model_size, device='cpu', compute_type='int8')",
                    "    except Exception as exc:",
                    "        print('MODEL_ERROR: ' + label + ': ' + repr(exc), flush=True)",
                    "        failures.append(label)",
                    "if failures:",
                    "    raise RuntimeError('Không tải được: ' + ', '.join(failures))",
                    "print('Hoàn tất các model Whisper.', flush=True)",
                ]
                tasks.append(("Whisper / nhận diện giọng nói", make_script(whisper_setup, whisper_body)))

            if target in ("all", "paddleocr"):
                from app.common.config_manager import get_paddleocr_cache_dir

                paddle_home = get_paddleocr_cache_dir()
                paddle_setup = [
                    "import os, warnings, logging",
                    "os.environ['USERPROFILE'] = " + repr(paddle_home),
                    "os.environ['HOME'] = " + repr(paddle_home),
                    "os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'",
                    "os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'",
                    "warnings.filterwarnings('ignore')",
                    "logging.getLogger('huggingface_hub').setLevel(logging.ERROR)",
                ]
                paddle_body = [
                    "from paddleocr import PaddleOCR",
                    "failures = []",
                    "for lang in ('vi', 'en'):",
                    "    print('Đang kiểm tra/tải model OCR (' + lang + ')...', flush=True)",
                    "    try:",
                    "        PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=False, show_log=False)",
                    "    except Exception as exc:",
                    "        print('MODEL_ERROR: OCR ' + lang + ': ' + repr(exc), flush=True)",
                    "        failures.append(lang)",
                    "if failures:",
                    "    raise RuntimeError('Không tải được OCR: ' + ', '.join(failures))",
                    "print('Hoàn tất các model OCR.', flush=True)",
                ]
                tasks.append(("PaddleOCR / bóc chữ", make_script(paddle_setup, paddle_body)))

            if target in ("all", "demucs"):
                from app.common.config_manager import get_audio_sep_cache_dir

                audio_cache = get_audio_sep_cache_dir()
                demucs_setup = [
                    "import os, warnings, logging, urllib.request",
                    "warnings.filterwarnings('ignore')",
                    "logging.getLogger('huggingface_hub').setLevel(logging.ERROR)",
                ]
                demucs_body = [
                    "ffmpeg_dir = os.environ.get('BUNDLE_FFMPEG_DIR', '')",
                    "if ffmpeg_dir and os.path.isdir(ffmpeg_dir):",
                    "    os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')",
                    "original_urlopen = urllib.request.urlopen",
                    "def patched_urlopen(url, *args, **kwargs):",
                    "    value = url if isinstance(url, str) else getattr(url, 'full_url', str(url))",
                    "    old = 'raw.githubusercontent.com/TRvlvr/application_data/main'",
                    "    new = 'cdn.jsdelivr.net/gh/TRvlvr/application_data@main'",
                    "    if old in value:",
                    "        value = value.replace(old, new)",
                    "        if isinstance(url, str):",
                    "            url = value",
                    "        else:",
                    "            url = urllib.request.Request(value, headers=dict(url.header_items()), method=url.get_method())",
                    "    return original_urlopen(url, *args, **kwargs)",
                    "urllib.request.urlopen = patched_urlopen",
                    "import requests",
                    "original_get = requests.Session.get",
                    "def patched_get(self, url, *args, **kwargs):",
                    "    old = 'raw.githubusercontent.com/TRvlvr/application_data/main'",
                    "    new = 'cdn.jsdelivr.net/gh/TRvlvr/application_data@main'",
                    "    if isinstance(url, str):",
                    "        url = url.replace(old, new)",
                    "    return original_get(self, url, *args, **kwargs)",
                    "requests.Session.get = patched_get",
                    "from audio_separator.separator import Separator",
                    "cache_dir = " + repr(audio_cache),
                    "os.makedirs(cache_dir, exist_ok=True)",
                    "models = ('model_bs_roformer_ep_317_sdr_12.9755.ckpt', 'UVR-MDX-NET-Inst_HQ_3.onnx')",
                    "for model_name in models:",
                    "    print('Đang kiểm tra/tải model tách nhạc: ' + model_name, flush=True)",
                    "    Separator(output_dir=cache_dir, model_file_dir=cache_dir).load_model(model_filename=model_name)",
                    "print('Hoàn tất các model tách nhạc.', flush=True)",
                ]
                tasks.append(("Tách nhạc", make_script(demucs_setup, demucs_body)))

            success = bool(tasks)
            failures = []
            self.progress.emit("Đang tải/kiểm tra gói mở rộng. Nhật ký lỗi sẽ hiện ngay bên dưới.")
            for index, (label, script) in enumerate(tasks, 1):
                self.progress.emit("\n[%d/%d] %s" % (index, len(tasks), label))
                try:
                    completed = self._run_script(sys.executable, script)
                except Exception as exc:
                    completed = False
                    self.progress.emit("Lỗi trình tải %s: %s" % (label, exc))
                if not completed:
                    success = False
                    failures.append(label)

            if not tasks:
                self.progress.emit("Không nhận diện được loại model cần tải: %s" % target)
            if failures:
                self.error_summary = "; ".join(failures)
                self.progress.emit("\nTẢI CHƯA HOÀN TẤT: " + self.error_summary)
            elif success:
                self.error_summary = ""
                self.progress.emit("\nĐÃ KIỂM TRA/TẢI THÀNH CÔNG CÁC GÓI ĐƯỢC CHỌN.")
            self._luaVietsup_finished_emitted = True
            self.finished_signal.emit(success)

        def guarded_run(self):
            self._luaVietsup_finished_emitted = False
            try:
                run(self)
            except Exception as exc:
                self.error_summary = str(exc)
                try:
                    self.progress.emit("Lỗi khi chuẩn bị tải gói mở rộng: %s" % exc)
                except Exception:
                    pass
            finally:
                if not getattr(self, "_luaVietsup_finished_emitted", False):
                    self._luaVietsup_finished_emitted = True
                    self.finished_signal.emit(False)

        worker_cls._run_script = run_script
        worker_cls.run = guarded_run
        worker_cls._luavietsup_download_patch = True

        setting_cls = setting_interface.SettingInterface
        original_finished = setting_cls._onModelDownloadFinished

        def on_download_finished(self, success):
            original_finished(self, success)
            if not success:
                from qfluentwidgets import InfoBar, InfoBarPosition

                worker = getattr(self, "model_worker", None)
                detail = getattr(worker, "error_summary", "") or "Mở nhật ký trong mục Gói Mở Rộng để xem lỗi chi tiết."
                InfoBar.error(
                    title="Tải gói mở rộng chưa hoàn tất",
                    content=detail,
                    parent=self.window(),
                    position=InfoBarPosition.TOP,
                    duration=10000,
                )

        setting_cls._onModelDownloadFinished = on_download_finished
        _voice_log("Model downloader patch installed; download return codes will be checked")
        return True
    except Exception as exc:
        _voice_log("install_model_download_fixes failed: %r" % (exc,))
        return False


def setup_chatgpt_settings_ui(setting_interface):
    try:
        if getattr(setting_interface, "_chatgpt_ui_ready", False):
            return
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
        from qfluentwidgets import (
            CardWidget, SubtitleLabel, BodyLabel, CaptionLabel,
            StrongBodyLabel, TextEdit, LineEdit, ComboBox, PushButton, InfoBar, InfoBarPosition,
            FluentIcon as FIF
        )
        from app.common.config_manager import load_config, save_config
        import chatgpt_web
        import custom_api

        page_ai = getattr(setting_interface, "page_ai_services", None)
        if not page_ai:
            return

        # 1. Engine selector in group_trans
        group_trans = getattr(setting_interface, "group_trans", None)
        if group_trans and group_trans.layout():
            layout_trans = group_trans.layout()
            row_eng = QHBoxLayout()
            lbl_eng = StrongBodyLabel("Công cụ Dịch thuật Mặc định:")
            combo_eng = ComboBox(group_trans)
            combo_eng.addItem("Google Gemini AI (API Key)", userData="gemini")
            combo_eng.addItem("ChatGPT Web (Cookie Trình Duyệt)", userData="chatgpt_web")
            combo_eng.addItem("Custom API (OpenAI / DeepSeek / Groq)", userData="custom_api")
            row_eng.addWidget(lbl_eng)
            row_eng.addWidget(combo_eng)
            row_eng.addStretch(1)
            layout_trans.insertLayout(0, row_eng)
            setting_interface.combo_default_engine = combo_eng

        # 2. ChatGPT Web Card
        group_chatgpt = CardWidget(page_ai)
        layout_cg = QVBoxLayout(group_chatgpt)
        layout_cg.setSpacing(12)

        layout_cg.addWidget(SubtitleLabel("Dịch thuật bằng ChatGPT Web (chatgpt.com)"))
        layout_cg.addWidget(BodyLabel("Cookie tài khoản ChatGPT Web (Mỗi dòng 1 cookie, tự động xoay vòng khi quá tải):"))

        lbl_guide = CaptionLabel(
            "• Cách 1 (Khuyên dùng - Chuẩn 100%): Mở tab mới vào https://chatgpt.com/api/auth/session -> Copy toàn bộ JSON "
            "(hoặc giá trị accessToken) dán vào đây.\n"
            "• Cách 2: Copy giá trị '__Secure-next-auth.session-token' từ F12 Application -> Cookies, hoặc copy toàn bộ "
            "header 'Cookie:' từ F12 Network tab (hỗ trợ cả session-token, cookie chunk .0/.1, Cookie-Editor).\n"
            "• Hỗ trợ nhập nhiều tài khoản (mỗi tài khoản 1 dòng) để tự động xoay vòng khi đầy hạn mức."
        )
        lbl_guide.setStyleSheet("color: #94A3B8; font-style: italic;")
        layout_cg.addWidget(lbl_guide)

        text_cookies = TextEdit(group_chatgpt)
        text_cookies.setPlaceholderText("Dán AccessToken, nội dung JSON từ chatgpt.com/api/auth/session hoặc Cookie vào đây...")
        text_cookies.setFixedHeight(95)
        layout_cg.addWidget(text_cookies)
        setting_interface.text_chatgpt_cookies = text_cookies

        row_ctrl = QHBoxLayout()
        btn_test = PushButton(FIF.PLAY, "Kiểm tra Cookie / Token", group_chatgpt)
        btn_test.setFixedWidth(180)
        row_ctrl.addWidget(btn_test)

        lbl_status = BodyLabel("Trạng thái: Chưa kiểm tra", group_chatgpt)
        lbl_status.setStyleSheet("color: gray;")
        row_ctrl.addWidget(lbl_status)
        row_ctrl.addStretch(1)
        layout_cg.addLayout(row_ctrl)

        # 3. Custom API Card (OpenAI / DeepSeek / Groq / Ollama / etc.)
        group_custom_api = CardWidget(page_ai)
        layout_ca = QVBoxLayout(group_custom_api)
        layout_ca.setSpacing(12)

        layout_ca.addWidget(SubtitleLabel("Custom API (OpenAI / DeepSeek / Groq / OpenRouter / Ollama...)"))

        layout_ca.addWidget(BodyLabel("Base URL (Mặc định để trống để dùng OpenAI):"))
        line_ca_base_url = LineEdit(group_custom_api)
        line_ca_base_url.setPlaceholderText("Mặc định để trống (dùng https://api.openai.com/v1) hoặc nhập https://api.deepseek.com...")
        line_ca_base_url.setClearButtonEnabled(True)
        layout_ca.addWidget(line_ca_base_url)
        setting_interface.line_custom_api_base_url = line_ca_base_url

        layout_ca.addWidget(BodyLabel("API Key (Mỗi dòng 1 key, tự động xoay vòng khi quá tải):"))
        text_ca_key = TextEdit(group_custom_api)
        text_ca_key.setPlaceholderText("Dán API Key vào đây (ví dụ: sk-..., gsk_...)...")
        text_ca_key.setFixedHeight(75)
        layout_ca.addWidget(text_ca_key)
        setting_interface.text_custom_api_key = text_ca_key

        layout_ca.addWidget(BodyLabel("Mô hình (Model name):"))
        line_ca_model = LineEdit(group_custom_api)
        line_ca_model.setPlaceholderText("Để trống để tự động nhận diện theo Base URL (hoặc nhập: deepseek-chat, gpt-4o, llama-3.3-70b-versatile...)")
        line_ca_model.setClearButtonEnabled(True)
        layout_ca.addWidget(line_ca_model)
        setting_interface.line_custom_api_model = line_ca_model

        lbl_ca_guide = CaptionLabel(
            "• Tự động nhận diện từ Base URL: DeepSeek -> deepseek-chat | Groq -> llama-3.3-70b-versatile | OpenRouter -> google/gemini-2.0-flash-001 | xkiro -> qwen/qwen3.7-flash:free | OpenAI -> gpt-4o-mini | Ollama -> llama3.2.\n"
            "• Hoặc bạn có thể nhập thủ công bất kỳ tên model nào của nhà cung cấp vào ô bên trên (lưu ý: tài khoản dùng credits thử nghiệm hãy chọn model có đuôi :free)."
        )
        lbl_ca_guide.setStyleSheet("color: #94A3B8; font-style: italic;")
        layout_ca.addWidget(lbl_ca_guide)

        row_ca_ctrl = QHBoxLayout()
        btn_test_ca = PushButton(FIF.PLAY, "Kiểm tra API", group_custom_api)
        btn_test_ca.setFixedWidth(180)
        row_ca_ctrl.addWidget(btn_test_ca)

        lbl_ca_status = BodyLabel("Trạng thái: Chưa kiểm tra", group_custom_api)
        lbl_ca_status.setStyleSheet("color: gray;")
        row_ca_ctrl.addWidget(lbl_ca_status)
        row_ca_ctrl.addStretch(1)
        layout_ca.addLayout(row_ca_ctrl)

        page_layout = page_ai.layout()
        if page_layout:
            trans_idx = -1
            for i in range(page_layout.count()):
                if page_layout.itemAt(i).widget() == group_trans:
                    trans_idx = i
                    break
            if trans_idx >= 0:
                page_layout.insertWidget(trans_idx + 1, group_chatgpt)
                page_layout.insertWidget(trans_idx + 2, group_custom_api)
            else:
                page_layout.addWidget(group_chatgpt)
                page_layout.addWidget(group_custom_api)
        setting_interface.group_chatgpt = group_chatgpt
        setting_interface.group_custom_api = group_custom_api

        def _on_test_clicked():
            raw_text = text_cookies.toPlainText().strip()
            if not raw_text:
                InfoBar.warning(
                    title="Chưa nhập Cookie",
                    content="Vui lòng dán Cookie hoặc AccessToken ChatGPT vào ô bên trên!",
                    parent=setting_interface.window(),
                    position=InfoBarPosition.TOP,
                    duration=5000
                )
                lbl_status.setText("Trạng thái: Chưa nhập Cookie")
                lbl_status.setStyleSheet("color: #EF4444;")
                return

            btn_test.setEnabled(False)
            lbl_status.setText("Trạng thái: Đang kết nối tới chatgpt.com...")
            lbl_status.setStyleSheet("color: #E6A23C;")

            worker = chatgpt_web.ChatGPTCookieCheckWorker(raw_text, parent=setting_interface)
            def _on_result(ok, msg):
                btn_test.setEnabled(True)
                if ok:
                    lbl_status.setText("Trạng thái: " + msg)
                    lbl_status.setStyleSheet("color: #10B981; font-weight: bold;")
                    InfoBar.success(
                        title="Cookie / Token ChatGPT OK",
                        content=msg,
                        parent=setting_interface.window(),
                        position=InfoBarPosition.TOP,
                        duration=6000
                    )
                    setting_interface._saveConfig(show_msg=False)
                else:
                    lbl_status.setText("Trạng thái: " + msg)
                    lbl_status.setStyleSheet("color: #EF4444; font-weight: bold;")
                    InfoBar.error(
                        title="Cookie Lỗi",
                        content=msg,
                        parent=setting_interface.window(),
                        position=InfoBarPosition.TOP,
                        duration=8000
                    )

            worker.result.connect(_on_result)
            setting_interface._chatgpt_check_worker = worker
            worker.start()

        btn_test.clicked.connect(_on_test_clicked)

        def _on_test_ca_clicked():
            raw_url = line_ca_base_url.text().strip()
            raw_keys = text_ca_key.toPlainText().strip()
            raw_model = line_ca_model.text().strip()

            norm_url = custom_api.normalize_base_url(raw_url)
            is_local = any(loc in norm_url.lower() for loc in ("localhost", "127.0.0.1", "11434", "1234"))
            if not raw_keys and not is_local:
                InfoBar.warning(
                    title="Chưa nhập API Key",
                    content="Vui lòng nhập API Key trước khi kiểm tra!",
                    parent=setting_interface.window(),
                    position=InfoBarPosition.TOP,
                    duration=5000
                )
                lbl_ca_status.setText("Trạng thái: Chưa nhập API Key")
                lbl_ca_status.setStyleSheet("color: #EF4444;")
                return

            btn_test_ca.setEnabled(False)
            lbl_ca_status.setText(f"Trạng thái: Đang kết nối tới {norm_url}...")
            lbl_ca_status.setStyleSheet("color: #E6A23C;")

            worker = custom_api.CustomAPICheckWorker(raw_url, raw_keys, raw_model, parent=setting_interface)
            def _on_ca_result(ok, msg):
                btn_test_ca.setEnabled(True)
                if ok:
                    lbl_ca_status.setText("Trạng thái: " + msg.replace("\n", " | "))
                    lbl_ca_status.setStyleSheet("color: #10B981; font-weight: bold;")
                    InfoBar.success(
                        title="Kết nối API thành công",
                        content=msg,
                        parent=setting_interface.window(),
                        position=InfoBarPosition.TOP,
                        duration=6000
                    )
                    setting_interface._saveConfig(show_msg=False)
                else:
                    short_err = msg.splitlines()[0] if msg else "Lỗi kết nối"
                    lbl_ca_status.setText("Trạng thái: " + short_err[:80])
                    lbl_ca_status.setStyleSheet("color: #EF4444; font-weight: bold;")
                    InfoBar.error(
                        title="Kết nối API thất bại",
                        content=msg,
                        parent=setting_interface.window(),
                        position=InfoBarPosition.TOP,
                        duration=8000
                    )

            worker.result.connect(_on_ca_result)
            setting_interface._custom_api_check_worker = worker
            worker.start()

        btn_test_ca.clicked.connect(_on_test_ca_clicked)

        orig_load = setting_interface._loadConfigToUI
        def patched_load(self_si):
            orig_load()
            cfg = load_config()
            self_si.config = cfg
            eng = cfg.get("translation_engine", "gemini")
            if hasattr(self_si, "combo_default_engine"):
                for idx in range(self_si.combo_default_engine.count()):
                    if self_si.combo_default_engine.itemData(idx) == eng:
                        self_si.combo_default_engine.setCurrentIndex(idx)
                        break
            cg_cookies = cfg.get("chatgpt_cookies", [])
            if hasattr(self_si, "text_chatgpt_cookies"):
                self_si.text_chatgpt_cookies.setPlainText("\n".join(cg_cookies))
            if hasattr(self_si, "line_custom_api_base_url"):
                self_si.line_custom_api_base_url.setText(cfg.get("custom_api_base_url", ""))
            if hasattr(self_si, "text_custom_api_key"):
                ca_key = cfg.get("custom_api_key", "")
                if isinstance(ca_key, list):
                    self_si.text_custom_api_key.setPlainText("\n".join(ca_key))
                else:
                    self_si.text_custom_api_key.setPlainText(str(ca_key or ""))
            if hasattr(self_si, "line_custom_api_model"):
                self_si.line_custom_api_model.setText(cfg.get("custom_api_model", ""))

        orig_save = setting_interface._saveConfig
        def patched_save(self_si, show_msg=True):
            orig_save(show_msg=False)
            cfg = load_config()
            if hasattr(self_si, "combo_default_engine"):
                cfg["translation_engine"] = self_si.combo_default_engine.currentData()
            if hasattr(self_si, "text_chatgpt_cookies"):
                lines_txt = self_si.text_chatgpt_cookies.toPlainText().strip()
                from chatgpt_web import extract_cookie_entries
                cfg["chatgpt_cookies"] = extract_cookie_entries(lines_txt)
            cfg["chatgpt_model"] = "auto"
            if hasattr(self_si, "line_custom_api_base_url"):
                cfg["custom_api_base_url"] = self_si.line_custom_api_base_url.text().strip()
            if hasattr(self_si, "text_custom_api_key"):
                cfg["custom_api_key"] = self_si.text_custom_api_key.toPlainText().strip()
            if hasattr(self_si, "line_custom_api_model"):
                cfg["custom_api_model"] = self_si.line_custom_api_model.text().strip()
            save_config(cfg)
            self_si.config = cfg
            if show_msg:
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.success(
                    title="Thành công",
                    content="Đã lưu cài đặt!",
                    parent=self_si.window(),
                    position=InfoBarPosition.TOP,
                    duration=5000
                )

        setting_interface._loadConfigToUI = lambda: patched_load(setting_interface)
        setting_interface._saveConfig = lambda show_msg=True: patched_save(setting_interface, show_msg=show_msg)
        setting_interface.get_chatgpt_cookies = lambda: chatgpt_web.extract_cookie_entries(setting_interface.text_chatgpt_cookies.toPlainText())
        setting_interface.get_chatgpt_model = lambda: "auto"
        setting_interface.get_custom_api_base_url = lambda: (setting_interface.line_custom_api_base_url.text().strip() if hasattr(setting_interface, "line_custom_api_base_url") else "")
        setting_interface.get_custom_api_key = lambda: (setting_interface.text_custom_api_key.toPlainText().strip() if hasattr(setting_interface, "text_custom_api_key") else "")
        setting_interface.get_custom_api_model = lambda: (setting_interface.line_custom_api_model.text().strip() if hasattr(setting_interface, "line_custom_api_model") else "")
        setting_interface.get_translation_engine = lambda: setting_interface.combo_default_engine.currentData()

        patched_load(setting_interface)
        setting_interface._chatgpt_ui_ready = True
        _voice_log("ChatGPT settings UI configured")
    except Exception as exc:
        _voice_log("setup_chatgpt_settings_ui failed: %r" % (exc,))


def setup_chatgpt_home_ui(home_interface):
    try:
        if getattr(home_interface, "_chatgpt_ui_ready", False):
            return
        from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy
        from qfluentwidgets import BodyLabel, ComboBox
        from app.common.config_manager import get_config, set_config

        parent_w = getattr(home_interface, "combo_prompt", None)
        if not parent_w or not parent_w.parentWidget():
            return
        container = parent_w.parentWidget()
        layout = container.layout()
        if not layout:
            return

        prompt_idx = -1
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() == home_interface.combo_prompt:
                prompt_idx = i
                break

        lbl_eng = BodyLabel("Động cơ Dịch:")
        lbl_eng.setStyleSheet("color: #94A3B8; font-weight: bold;")
        combo_eng = ComboBox(container)
        combo_eng.addItem("Google Gemini AI", userData="gemini")
        combo_eng.addItem("ChatGPT Web (Cookie)", userData="chatgpt_web")
        combo_eng.addItem("Custom API (OpenAI / DeepSeek / Groq)", userData="custom_api")
        combo_eng.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo_eng.setMinimumWidth(50)

        target_idx = max(0, prompt_idx - 1) if prompt_idx >= 1 else 0
        layout.insertWidget(target_idx, lbl_eng)
        layout.insertWidget(target_idx + 1, combo_eng)
        home_interface.combo_trans_engine = combo_eng

        curr_eng = get_config("translation_engine", "gemini")
        for idx in range(combo_eng.count()):
            if combo_eng.itemData(idx) == curr_eng:
                combo_eng.setCurrentIndex(idx)
                break

        def _on_engine_changed():
            set_config("translation_engine", combo_eng.currentData())

        combo_eng.currentIndexChanged.connect(_on_engine_changed)

        # Optimize column proportions: compact control panel (col1), large video canvas (col2)
        try:
            if hasattr(home_interface, "col1_widget") and home_interface.col1_widget:
                home_interface.col1_widget.setMaximumWidth(295)
                home_interface.col1_widget.setMinimumWidth(260)

            if hasattr(home_interface, "col3_widget") and home_interface.col3_widget:
                home_interface.col3_widget.setMaximumWidth(330)
                home_interface.col3_widget.setMinimumWidth(270)

            if hasattr(home_interface, "col2_widget") and home_interface.col2_widget:
                home_interface.col2_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                home_interface.col2_widget.setMinimumWidth(550)

            if hasattr(home_interface, "hBoxLayout") and home_interface.hBoxLayout:
                home_interface.hBoxLayout.setStretch(0, 0)
                home_interface.hBoxLayout.setStretch(1, 1)
                home_interface.hBoxLayout.setStretch(2, 0)

            if hasattr(home_interface, "btn_preview_voice") and home_interface.btn_preview_voice:
                home_interface.btn_preview_voice.setMinimumWidth(75)

            if hasattr(home_interface, "combo_voice") and home_interface.combo_voice:
                home_interface.combo_voice.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                home_interface.combo_voice.setMinimumWidth(50)

            for btn_name in ["btn_add_mask", "btn_remove_item", "btn_add_bg_frame", "btn_add_logo", "btn_style"]:
                b = getattr(home_interface, btn_name, None)
                if b:
                    b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception as _e_layout:
            _voice_log("column layout optimization error: %r" % (_e_layout,))

        home_interface._chatgpt_ui_ready = True
        _voice_log("ChatGPT home UI configured")
    except Exception as exc:
        _voice_log("setup_chatgpt_home_ui failed: %r" % (exc,))


def install_chatgpt_translation_patch():
    try:
        import app.core.ai_translator as ai_translator
        import app.common.workers as workers
        from app.common.config_manager import load_config, save_config
        import chatgpt_web

        orig_tl = getattr(ai_translator, "translate_logic", None)

        def call_original_with_vietnamese_rules(srt_path, api_keys, status_cb, cancel_event, workspace_dir, prompt_style, custom_prompt_text, target_lang, kwargs):
            """Temporarily add the literary rules to the original Gemini prompt data."""
            changed_rules = []
            try:
                from translation_rules import rules_for_target_lang
                from app.common import prompts as prompts_module
                novel_rules = rules_for_target_lang(target_lang)
                if novel_rules:
                    prompt_data = getattr(prompts_module, "PROMPTS_DATA", {})
                    normalized_target = str(target_lang or "").strip().casefold()
                    matching = [
                        value for language, value in prompt_data.items()
                        if str(language).strip().casefold() == normalized_target
                        and isinstance(value, dict)
                    ] if isinstance(prompt_data, dict) else []
                    if not matching:
                        generic = getattr(prompts_module, "GENERIC_PROMPT", None)
                        if isinstance(generic, dict):
                            matching = [generic]
                    for value in matching:
                        old_rules = value.get("system_rules", "") or ""
                        if not isinstance(old_rules, str):
                            old_rules = str(old_rules)
                        if novel_rules not in old_rules:
                            value["system_rules"] = (old_rules.rstrip() + "\n\n" + novel_rules).strip()
                            changed_rules.append((value, old_rules))
            except Exception as exc:
                _voice_log("Vietnamese novel prompt injection warning: %r" % (exc,))

            try:
                return orig_tl(
                    srt_path, api_keys, status_cb, cancel_event, workspace_dir,
                    prompt_style, custom_prompt_text, target_lang, **kwargs
                )
            finally:
                for value, old_rules in changed_rules:
                    value["system_rules"] = old_rules

        def unified_translate_logic(srt_path, api_keys, status_cb, cancel_event, workspace_dir, prompt_style='Mặc định', custom_prompt_text='', target_lang='Tiếng Việt', **kwargs):
            cfg = load_config()
            engine = cfg.get("translation_engine", "gemini")

            if engine == "custom_api":
                import custom_api
                base_url = cfg.get("custom_api_base_url", "")
                model = cfg.get("custom_api_model", "")
                keys = api_keys if api_keys else cfg.get("custom_api_key", "")
                return custom_api.custom_api_translate_logic(
                    srt_path=srt_path,
                    base_url=base_url,
                    api_keys=keys,
                    model=model,
                    status_cb=status_cb,
                    cancel_event=cancel_event,
                    workspace_dir=workspace_dir,
                    prompt_style=prompt_style,
                    custom_prompt_text=custom_prompt_text,
                    target_lang=target_lang,
                    **kwargs
                )
            elif engine == "chatgpt_web":
                model = cfg.get("chatgpt_model", "auto")
                cookies = api_keys if api_keys else cfg.get("chatgpt_cookies", [])
                if not cookies:
                    raise ValueError("Chưa cấu hình Cookie ChatGPT Web! Vui lòng nhập Cookie trong phần Cài đặt.")
                return chatgpt_web.chatgpt_translate_logic(
                    srt_path=srt_path,
                    cookies=cookies,
                    status_cb=status_cb,
                    cancel_event=cancel_event,
                    workspace_dir=workspace_dir,
                    prompt_style=prompt_style,
                    custom_prompt_text=custom_prompt_text,
                    target_lang=target_lang,
                    model=model,
                )
            else:
                if not api_keys:
                    api_keys = cfg.get("gemini_keys", [])
                if not api_keys:
                    raise ValueError("Chưa cấu hình Gemini API Keys! Vui lòng nhập Key trong phần Cài đặt.")
                if orig_tl:
                    return call_original_with_vietnamese_rules(srt_path, api_keys, status_cb, cancel_event, workspace_dir, prompt_style, custom_prompt_text, target_lang, kwargs)
                raise RuntimeError("Không tìm thấy engine dịch Gemini gốc.")

        ai_translator.translate_logic = unified_translate_logic
        workers.translate_logic = unified_translate_logic

        from app.views.home_interface import HomeInterface
        from qfluentwidgets import InfoBar, InfoBarPosition

        def patched_on_translate_clicked(self):
            self._verify_license_sync()
            if not getattr(self, "selected_videos", None):
                InfoBar.warning(title="Cảnh báo", content="Vui lòng chọn video đầu vào trước!", parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return

            output_dir = self.line_output_path.text()
            if not output_dir:
                InfoBar.warning(title="Cảnh báo", content="Vui lòng chọn Đường dẫn lưu file trước!", parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return

            current_idx = self.video_combo.currentIndex()
            if current_idx < 0 or current_idx >= len(self.selected_videos):
                return

            from app.views.home_interface import get_safe_basename
            video_path = self.selected_videos[current_idx]
            base_name = get_safe_basename(video_path)
            workspace_dir = os.path.join(output_dir, base_name)
            data_dir = os.path.join(workspace_dir, "Data")
            srt_path = os.path.join(data_dir, "temp_original.srt")

            if not os.path.exists(srt_path):
                InfoBar.error(title="Lỗi", content="Không tìm thấy file phụ đề gốc! Vui lòng Bóc băng trước.", parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return

            cfg = load_config()
            if hasattr(self, "combo_trans_engine"):
                engine = self.combo_trans_engine.currentData()
                cfg["translation_engine"] = engine
                save_config(cfg)
            else:
                engine = cfg.get("translation_engine", "gemini")

            if engine == "custom_api":
                keys_val = cfg.get("custom_api_key", "")
                base_url = cfg.get("custom_api_base_url", "")
                import custom_api
                norm_url = custom_api.normalize_base_url(base_url)
                is_local = any(loc in norm_url.lower() for loc in ("localhost", "127.0.0.1", "11434", "1234"))
                if not keys_val and not is_local:
                    InfoBar.error(title="Lỗi", content="Vui lòng cấu hình API Key trong phần Cài đặt -> Custom API!", parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                    return
                keys = custom_api.extract_api_keys(keys_val)
            elif engine == "chatgpt_web":
                keys = cfg.get("chatgpt_cookies", [])
                if not keys:
                    InfoBar.error(title="Lỗi", content="Vui lòng cấu hình Cookie ChatGPT Web trong phần Cài đặt!", parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                    return
            else:
                keys = cfg.get("gemini_keys", [])
                if not keys:
                    InfoBar.error(title="Lỗi", content="Vui lòng cấu hình Gemini API Keys trong phần Cài đặt!", parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                    return

            self.media_player.pause()
            self._setButtonsEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.progress_bar.setValue(0)

            prompt_style = self.combo_prompt.currentData()
            custom_prompt = self.text_custom_prompt.toPlainText()
            target_lang = self.combo_target_lang.currentText()

            from app.common.workers import TranslateWorker
            self.translate_worker = TranslateWorker(
                srt_path, workspace_dir, keys, prompt_style, custom_prompt, target_lang, parent=self
            )
            self.translate_worker.progress.connect(self.progress_bar.setValue)
            self.translate_worker.log.connect(self._appendLog)
            self.translate_worker.finished_srt.connect(self._onTranslateFinished)
            self.translate_worker.error.connect(self._onTranscribeError)
            self.translate_worker.start()

        HomeInterface._onTranslateClicked = patched_on_translate_clicked

        orig_hi_init = HomeInterface.__init__
        def patched_hi_init(self, *args, **kwargs):
            orig_hi_init(self, *args, **kwargs)
            setup_chatgpt_home_ui(self)
        HomeInterface.__init__ = patched_hi_init

        from app.views.setting_interface import SettingInterface
        orig_si_init = SettingInterface.__init__
        def patched_si_init(self, *args, **kwargs):
            orig_si_init(self, *args, **kwargs)
            setup_chatgpt_settings_ui(self)
            setup_update_settings_ui(self, "2.6")
        SettingInterface.__init__ = patched_si_init

        _voice_log("ChatGPT translation runtime patch installed successfully")
    except Exception as exc:
        _voice_log("install_chatgpt_translation_patch failed: %r" % (exc,))


def setup_update_settings_ui(setting_interface, app_version="2.6"):
    """Inject modern Software Update Card into SettingInterface."""
    try:
        import updater_runtime
        updater_runtime.setup_update_settings_ui(setting_interface, app_version)
    except Exception as exc:
        _voice_log("setup_update_settings_ui failed: %r" % (exc,))


def handle_check_update(window, app_version="2.6"):
    """Check for updates at startup and show interactive dialog if new release found."""
    try:
        import updater_runtime
        updater_runtime.handle_app_start_update_check(window, app_version)
    except Exception as exc:
        _voice_log("handle_check_update failed: %r" % (exc,))



