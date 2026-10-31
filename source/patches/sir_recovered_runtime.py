"""Small reviewed fixes over the original PYZ, not the recreation project.

Only the explicitly replaced methods below change. Protected render/ASR/voice
cores and license decisions stay in their original modules.
"""
import math
import os
import re
import subprocess
import tempfile
import threading
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
            ('onnxruntime', 'capi'),
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


def ensure_piper_models_dir():
    """Ensure models/piper is available in root directory if present in _internal/models/piper."""
    try:
        if getattr(sys, 'frozen', False):
            root_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_piper = os.path.join(root_dir, 'models', 'piper')
        if not os.path.isdir(target_piper):
            internal_piper = os.path.join(root_dir, '_internal', 'models', 'piper')
            if os.path.isdir(internal_piper):
                import shutil
                os.makedirs(os.path.dirname(target_piper), exist_ok=True)
                shutil.copytree(internal_piper, target_piper, dirs_exist_ok=True)
    except Exception:
        pass

ensure_piper_models_dir()


def ensure_fonts_dir():
    """Ensure assets/fonts has all fonts from _internal/assets/fonts if empty or missing."""
    try:
        if getattr(sys, 'frozen', False):
            root_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_fonts = os.path.join(root_dir, 'assets', 'fonts')
        internal_fonts = os.path.join(root_dir, '_internal', 'assets', 'fonts')
        if os.path.isdir(internal_fonts):
            os.makedirs(target_fonts, exist_ok=True)
            for f in os.listdir(internal_fonts):
                tf = os.path.join(target_fonts, f)
                if not os.path.exists(tf):
                    import shutil
                    shutil.copy2(os.path.join(internal_fonts, f), tf)
    except Exception:
        pass

ensure_fonts_dir()


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
            try:
                setup_original_voice_dual_sub_ui(self)
            except Exception:
                pass
            try:
                self.setStyleSheet("QScrollArea, #homeInterface { background-color: #202020; border: none; }")
                if hasattr(self, 'view') and self.view:
                    self.view.setStyleSheet("background-color: #202020; border: none;")
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
    install_original_voice_dual_sub_patch()
    install_douyin_downloader_patch()
    install_unified_ai_bridge()
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
            candidates = []
            if requested:
                r = Path(requested).resolve()
                candidates.append(r)
                if r.name == "espeak-ng-data":
                    candidates.append(r.parent)
            search_roots = [
                Path.cwd(),
                Path(os.path.dirname(sys.executable)),
                Path(__file__).resolve().parent,
                Path(__file__).resolve().parent.parent,
            ]
            if len(Path(__file__).resolve().parents) > 2:
                search_roots.append(Path(__file__).resolve().parents[2])
            mei = getattr(sys, '_MEIPASS', None)
            if mei:
                search_roots.append(Path(mei))

            for root in search_roots:
                candidates.append(root / "_internal" / "piper")
                candidates.append(root / "piper")

            found_parent = None
            for cand in candidates:
                if (cand / "espeak-ng-data" / "phontab").is_file():
                    found_parent = cand
                    break
                if (cand / "phontab").is_file():
                    found_parent = cand.parent
                    break
            if not found_parent:
                found_parent = candidates[0] if candidates else Path.cwd()

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

        # Hook PiperVoice.load to enforce GPU CUDA acceleration with CPU fallback on RTX 5060
        _orig_pv_load = pv.PiperVoice.load
        def _gpu_pv_load(*args, **kwargs):
            if "use_cuda" not in kwargs or not kwargs["use_cuda"]:
                kwargs["use_cuda"] = True
            return _orig_pv_load(*args, **kwargs)
        pv.PiperVoice.load = _gpu_pv_load

        ESPEAK_PATCH_INSTALLED = True
        _voice_log("PIPER/ESPEAK initialized with GPU acceleration & safe_dir=%s" % safe_dir)
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
            if buf.value and '?' not in buf.value:
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
            if short and orig != short and '?' not in short:
                known_replacements.append((orig, short))
                known_replacements.append((orig.replace('\\', '/'), short.replace('\\', '/')))
                known_replacements.append((orig.replace('\\', '/').replace(':', '\\:'), short.replace('\\', '/').replace(':', '\\:')))

    _enc_cache = {}
    _force_cpu_render = [False]
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

    def get_ffmpeg_binary():
        env_bin = os.environ.get("FFMPEG_BINARY") or os.environ.get("IMAGEIO_FFMPEG_EXE")
        if env_bin and os.path.isfile(env_bin):
            return env_bin
        search_dirs = [
            Path.cwd() / "_internal" / "ffmpeg",
            Path.cwd() / "ffmpeg",
            Path(os.path.dirname(sys.executable)) / "_internal" / "ffmpeg",
            Path(__file__).resolve().parent.parent / "_internal" / "ffmpeg",
            Path(getattr(sys, '_MEIPASS', '')) / "ffmpeg",
        ]
        for d in search_dirs:
            candidate = d / "ffmpeg.exe"
            if candidate.is_file():
                os.environ["FFMPEG_BINARY"] = str(candidate)
                return str(candidate)
        try:
            import imageio_ffmpeg
            candidate = imageio_ffmpeg.get_ffmpeg_exe()
            if candidate and os.path.isfile(candidate):
                os.environ["FFMPEG_BINARY"] = str(candidate)
                return str(candidate)
        except Exception:
            pass
        return "ffmpeg"

    def get_aria2c_binary():
        search_dirs = [
            Path.cwd() / "_internal" / "ffmpeg",
            Path.cwd() / "ffmpeg",
            Path(os.path.dirname(sys.executable)) / "_internal" / "ffmpeg",
            Path(__file__).resolve().parent.parent / "_internal" / "ffmpeg",
            Path(getattr(sys, '_MEIPASS', '')) / "ffmpeg",
        ]
        for d in search_dirs:
            candidate = d / "aria2c.exe"
            if candidate.is_file():
                return str(candidate)
        return None

    orig_popen = subprocess.Popen

    def is_codec_supported(enc_name):
        if enc_name in _enc_cache:
            return _enc_cache[enc_name]
        ffmpeg_exe = get_ffmpeg_binary()
        try:
            candidates = []
            if "nvenc" in enc_name:
                # Blackwell (RTX 50-series) and Windows WDDM D3D11 hardware context probe
                candidates.append([
                    ffmpeg_exe, "-init_hw_device", "d3d11va=d3d", "-filter_hw_device", "d3d",
                    "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                    "-c:v", enc_name, "-f", "null", "-"
                ])
            candidates.append([
                ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", enc_name, "-f", "null", "-"
            ])
            success = False
            for cmd in candidates:
                try:
                    p = orig_popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    p.communicate(timeout=5)
                    if p.returncode == 0:
                        success = True
                        break
                except Exception:
                    continue
            _enc_cache[enc_name] = success
        except Exception:
            _enc_cache[enc_name] = False
        return _enc_cache[enc_name]

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

                # Ensure valid executable path for ffmpeg
                if new_cmd and (str(new_cmd[0]).lower() == 'ffmpeg' or not os.path.isfile(str(new_cmd[0]))):
                    real_ffmpeg = get_ffmpeg_binary()
                    if real_ffmpeg and os.path.isfile(real_ffmpeg):
                        new_cmd[0] = real_ffmpeg

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
                        # Subtitle font auto-healing: ensure libass uses exact TrueType family matching preview
                        fixed_fc = _lua_fix_render_fonts(str(new_cmd[fc_idx + 1]), output_path, kwargs.get('cwd'))
                        if fixed_fc:
                            new_cmd[fc_idx + 1] = fixed_fc
                        # Dual-subtitle mode: burn the original-language SRT on top
                        # of the translated one (only for the render of this workspace).
                        dual_fc = _lua_inject_dual_subtitle(str(new_cmd[fc_idx + 1]), output_path, kwargs.get('cwd'))
                        if dual_fc:
                            new_cmd[fc_idx + 1] = dual_fc

                for vf_flag in ("-vf", "-filter:v"):
                    if vf_flag in new_cmd:
                        vfi = new_cmd.index(vf_flag)
                        if vfi + 1 < len(new_cmd) and "subtitles=" in str(new_cmd[vfi + 1]):
                            fixed_v = _lua_fix_render_fonts(str(new_cmd[vfi + 1]), output_path, kwargs.get('cwd'))
                            if fixed_v:
                                new_cmd[vfi + 1] = fixed_v

                is_stream_copy = False
                if "-vcodec" in new_cmd and "-c:v" not in new_cmd:
                    v_idx = new_cmd.index("-vcodec")
                    new_cmd[v_idx] = "-c:v"

                if "-c:v" in new_cmd:
                    idx = new_cmd.index("-c:v")
                    enc = new_cmd[idx + 1].lower() if idx + 1 < len(new_cmd) else ""
                    if enc == "copy":
                        is_stream_copy = True
                    else:
                        has_nvenc = is_codec_supported("h264_nvenc")
                        has_hevc_nvenc = is_codec_supported("hevc_nvenc")
                        hardware_codecs = {
                            "h264_nvenc", "h264_amf", "h264_qsv", "h264_videotoolbox",
                            "hevc_nvenc", "hevc_amf", "hevc_qsv", "hevc_videotoolbox",
                            "av1_nvenc", "av1_amf", "av1_qsv",
                        }

                        # Check if we should use NVIDIA NVENC
                        use_nvenc = False
                        if not _force_cpu_render[0] and has_nvenc and (enc in ("h264_nvenc", "libx264", "h264_amf", "h264_qsv", "") or enc in hardware_codecs):
                            new_cmd[idx + 1] = "h264_nvenc"
                            use_nvenc = True
                        elif not _force_cpu_render[0] and has_hevc_nvenc and enc in ("hevc_nvenc", "libx265", "hevc"):
                            new_cmd[idx + 1] = "hevc_nvenc"
                            use_nvenc = True

                        if use_nvenc:
                            # Direct3D 11 hardware context required for Blackwell (RTX 50-series) NVENC
                            if "-init_hw_device" not in new_cmd:
                                new_cmd[1:1] = ["-init_hw_device", "d3d11va=d3d", "-filter_hw_device", "d3d"]

                            # 1. GPU RTX 5060 NVENC DEEP QUALITY PASS (9th Gen Blackwell NVENC):
                            # Constant Quality (CQ 20) for crisp, professional visual quality
                            if "-crf" in new_cmd:
                                crf_idx = new_cmd.index("-crf")
                                new_cmd[crf_idx] = "-cq"
                                new_cmd[crf_idx + 1] = "20"
                            elif "-cq" not in new_cmd:
                                new_cmd[-1:-1] = ["-cq", "20"]

                            # Preset p5: High Quality GPU Pass on RTX 5060 & tune hq
                            if "-preset" in new_cmd:
                                preset_idx = new_cmd.index("-preset")
                                new_cmd[preset_idx + 1] = "p5"
                            else:
                                new_cmd[-1:-1] = ["-preset", "p5"]

                            if "-tune" in new_cmd:
                                tune_idx = new_cmd.index("-tune")
                                new_cmd[tune_idx + 1] = "hq"
                            else:
                                new_cmd[-1:-1] = ["-tune", "hq"]

                            # Clean up CPU-only flags if present
                            for cpu_flag in ("-x264-params",):
                                if cpu_flag in new_cmd:
                                    f_idx = new_cmd.index(cpu_flag)
                                    del new_cmd[f_idx:min(f_idx + 2, len(new_cmd))]

                            # Add deep quality GPU computation passes:
                            # - Full-resolution 2-pass GPU analysis (-multipass fullres)
                            # - Spatial & Temporal Adaptive Quantization (-spatial-aq 1, -temporal-aq 1, -aq-strength 8)
                            # - Deep 32-frame Lookahead Analysis (-rc-lookahead 32)
                            # - Hierarchical B-frame reference (-b_ref_mode middle)
                            # - Extended VRAM pipeline surfaces (-surfaces 32)
                            for extra_flag in (
                                ["-multipass", "fullres"],
                                ["-spatial-aq", "1"],
                                ["-temporal-aq", "1"],
                                ["-aq-strength", "8"],
                                ["-rc-lookahead", "32"],
                                ["-b_ref_mode", "middle"],
                                ["-surfaces", "32"],
                            ):
                                if extra_flag[0] not in new_cmd:
                                    new_cmd[-1:-1] = extra_flag

                            # 2. CPU i5-14600F OPTIMIZATION:
                            # Cap filter processing threads to 4-6 threads to keep CPU cool and prevent fan noise
                            filter_threads = max(2, min(6, (os.cpu_count() or 4) // 2))
                            if "-threads" in new_cmd:
                                t_idx = new_cmd.index("-threads")
                                if t_idx + 1 < len(new_cmd):
                                    new_cmd[t_idx + 1] = str(filter_threads)
                            else:
                                new_cmd[-1:-1] = ["-threads", str(filter_threads)]

                        else:
                            # FALLBACK: When NVENC is not supported
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
                            # Cap CPU libx264 threads to 8 (P-cores only) so 14400F does not hit 100%
                            thread_count = max(2, min(8, int((os.cpu_count() or 4) * 0.5)))
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
                if is_render or video_output:
                    _voice_log("FFmpeg Render Popen starting with cmd:\n" + " ".join(f'"{x}"' if ' ' in str(x) else str(x) for x in new_cmd))
                cmd = new_cmd
            elif isinstance(cmd, list) and any('yt_dlp' in str(x).lower() for x in cmd):
                new_cmd = list(cmd)
                aria2c_bin = get_aria2c_binary()
                ffmpeg_bin = get_ffmpeg_binary()
                if aria2c_bin and '--external-downloader' not in new_cmd:
                    new_cmd.extend([
                        '--external-downloader', aria2c_bin,
                        '--external-downloader-args', 'aria2c:-s 16 -x 16 -k 1M -j 16',
                        '--concurrent-fragments', '16'
                    ])
                if ffmpeg_bin and ffmpeg_bin != 'ffmpeg' and '--ffmpeg-location' not in new_cmd:
                    new_cmd.extend(['--ffmpeg-location', ffmpeg_bin])
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

        orig_get_font_family = getattr(fm, "get_font_family", None)
        def safe_get_font_family(display_name):
            fmap = _lua_get_libass_font_map()
            if display_name:
                cand = fmap.get(display_name) or fmap.get(display_name.lower())
                if cand:
                    return cand
            if orig_get_font_family:
                try:
                    return orig_get_font_family(display_name)
                except Exception:
                    pass
            return display_name
        fm.get_font_family = safe_get_font_family
    except Exception:
        pass

    try:
        import app.core.video_renderer as vr
        import app.common.workers as workers
        orig_render_logic = getattr(vr, "render_logic", None)

        def safe_render_logic(video_path, srt_path, audio_path, workspace_dir, status_cb, cancel_event, license_status=None, video_config=None):
            if cancel_event and cancel_event.is_set():
                _voice_log("safe_render_logic: cancel_event đã bật từ trước, hủy render ngay lập tức.")
                return "CANCELLED"

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

            # Dual-subtitle mode: prepare the original-language SRT that the
            # FFmpeg patch will burn above the translated one.
            _LUA_DUAL_PENDING['srt'] = None
            _LUA_DUAL_PENDING['rel'] = None
            _LUA_DUAL_PENDING['keys'] = None
            if dual_subtitle_on():
                _lua_orig_srt = os.path.join(str(workspace_dir), 'Data', 'temp_original.srt')
                if os.path.isfile(_lua_orig_srt):
                    if not has_full_license(license_status):
                        _lua_orig_srt = make_unlicensed_srt(_lua_orig_srt, workspace_dir)
                    try:
                        _lua_ws = str(workspace_dir)
                        _LUA_DUAL_PENDING['srt'] = str(_lua_orig_srt)
                        _LUA_DUAL_PENDING['rel'] = os.path.relpath(str(_lua_orig_srt), _lua_ws).replace('\\', '/')
                        _LUA_DUAL_PENDING['keys'] = _lua_workspace_keys(_lua_ws)
                    except Exception as _lua_dual_exc:
                        _voice_log("Dual-subtitle prepare failed: %r" % (_lua_dual_exc,))
                        _LUA_DUAL_PENDING['srt'] = None

            # Original-voice mode: replace the TTS voice track with the video's
            # own audio so the render keeps the original sound.
            if use_original_voice_on():
                audio_path = _lua_ensure_original_pcm_for_render(video_path, workspace_dir, status_cb, audio_path)

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

            has_nvenc = is_codec_supported("h264_nvenc")
            # Auto-detect GPU: enable GPU NVENC whenever NVIDIA GPU is available
            user_wanted_gpu = video_config.get("use_gpu")
            if user_wanted_gpu is None:
                user_wanted_gpu = has_nvenc
            else:
                user_wanted_gpu = bool(user_wanted_gpu) and has_nvenc

            _force_cpu_render[0] = not user_wanted_gpu

            if user_wanted_gpu:
                video_config["render_codec"] = "h264_nvenc"
                video_config["use_gpu"] = True
                video_config["render_preset"] = "p5"
                video_config["cpu_threads"] = max(2, min(6, (os.cpu_count() or 4) // 2))
                _voice_log("GPU RTX Hardware Render enabled: h264_nvenc (preset=p5, cpu_threads=%d)" % video_config["cpu_threads"])
            else:
                video_config["render_codec"] = "libx264"
                video_config["use_gpu"] = False
                video_config["cpu_threads"] = max(2, min(8, int((os.cpu_count() or 4) * 0.5)))
                video_config["render_preset"] = "veryfast"
                _voice_log("CPU Software Render: libx264 (cpu_threads=%d)" % video_config["cpu_threads"])

            # Pre-populate workspace temp_fonts with all custom fonts so libass has 100% font coverage
            try:
                _ws_tf = os.path.join(str(workspace_dir), "Data", "temp_fonts")
                os.makedirs(_ws_tf, exist_ok=True)
                _af_dir = _lua_get_assets_fonts_dir()
                if _af_dir and os.path.isdir(_af_dir):
                    for _f_name in os.listdir(_af_dir):
                        if _f_name.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                            _sp = os.path.join(_af_dir, _f_name)
                            _dp = os.path.join(_ws_tf, _f_name)
                            if not os.path.isfile(_dp) or os.path.getsize(_dp) != os.path.getsize(_sp):
                                try:
                                    shutil.copy2(_sp, _dp)
                                except Exception:
                                    pass
            except Exception as _e_tf:
                _voice_log("Pre-populate temp_fonts failed: %r" % (_e_tf,))

            try:
                return orig_render_logic(render_video_input, srt_path, audio_path, workspace_dir, status_cb, cancel_event, license_status, video_config)
            except Exception as e:
                if cancel_event and cancel_event.is_set():
                    _voice_log("safe_render_logic: Ngoại lệ xảy ra do người dùng hủy bỏ, dừng render ngay lập tức.")
                    return "CANCELLED"
                err_text = str(e).lower()
                if "cancel" in err_text or "abort" in err_text:
                    _voice_log("safe_render_logic: Phát hiện ngoại lệ hủy bỏ, trả về CANCELLED.")
                    return "CANCELLED"
                # If GPU failed, or codec error, cleanly fallback to multi-threaded CPU libx264:
                if user_wanted_gpu or "nvenc" in err_text or "not in list" in err_text or "codec" in err_text or isinstance(e, ValueError):
                    try:
                        if callable(status_cb):
                            status_cb("Chuyển sang CPU render để đảm bảo xuất video thành công...", 0.1)
                    except Exception:
                        pass
                    _force_cpu_render[0] = True
                    video_config["render_codec"] = "libx264"
                    video_config["use_gpu"] = False
                    video_config["cpu_threads"] = max(2, min(8, int((os.cpu_count() or 4) * 0.5)))
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
                    if getattr(child_widget, "_lua_keep", False):
                        continue
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
                    if getattr(child_widget, "_lua_keep", False):
                        continue
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
                    if getattr(child_widget, "_lua_keep", False):
                        continue
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
            if getattr(widget, "_lua_keep", False):
                continue
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
    """Show the current HWID, copy button, and Telegram activation contact controls."""
    try:
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtWidgets import (
            QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
        )
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

        # Khung liên hệ Telegram kích hoạt bản quyền
        tg_box = QWidget(group)
        tg_box._lua_keep = True
        tg_box.setObjectName("luaTelegramBox")
        tg_layout = QVBoxLayout(tg_box)
        tg_layout.setContentsMargins(14, 12, 14, 12)
        tg_layout.setSpacing(8)
        tg_box.setStyleSheet("""
            #luaTelegramBox {
                background-color: #17212B;
                border: 1px solid #2481CC;
                border-radius: 8px;
            }
        """)

        # Nút bấm mở trực tiếp Telegram https://t.me/oxhexs
        tg_btn_row = QHBoxLayout()
        btn_tg = QPushButton("💬 Liên hệ qua Telegram: @oxhexs", tg_box)
        btn_tg._lua_keep = True
        btn_tg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tg.setToolTip("Nhấn để mở thẳng đến liên kết https://t.me/oxhexs")
        btn_tg.setStyleSheet("""
            QPushButton {
                background-color: #2481CC;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2A96E8;
            }
            QPushButton:pressed {
                background-color: #1E6EB0;
            }
        """)

        def open_telegram():
            import webbrowser
            tg_url = "https://t.me/oxhexs"
            try:
                if not QDesktopServices.openUrl(QUrl(tg_url)):
                    webbrowser.open(tg_url)
            except Exception:
                webbrowser.open(tg_url)

        btn_tg.clicked.connect(open_telegram)
        tg_btn_row.addWidget(btn_tg)
        tg_btn_row.addStretch(1)

        # Chữ ở dưới: "liên hệ qua telegram để kích hoạt bản quyền"
        lbl_tg_sub = QLabel(tg_box)
        lbl_tg_sub._lua_keep = True
        lbl_tg_sub.setWordWrap(True)
        lbl_tg_sub.setTextFormat(Qt.TextFormat.RichText)
        lbl_tg_sub.setOpenExternalLinks(True)
        lbl_tg_sub.setText(
            "<span style='color: #CBD5E1; font-size: 13px;'>👉 </span>"
            "<a href='https://t.me/oxhexs' style='color: #38BDF8; font-size: 13px; font-weight: 600; text-decoration: underline;'>"
            "liên hệ qua telegram để kích hoạt bản quyền"
            "</a>"
            "<span style='color: #94A3B8; font-size: 12px;'> (Link: https://t.me/oxhexs)</span>"
        )
        lbl_tg_sub.setStyleSheet("background: transparent; border: none;")

        tg_layout.addLayout(tg_btn_row)
        tg_layout.addWidget(lbl_tg_sub)
        layout.addWidget(tg_box)

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
            lbl_eng = StrongBodyLabel("Động cơ AI Toàn hệ thống (Dịch, Rút gọn câu, Tiêu đề, Highlight):")
            combo_eng = ComboBox(group_trans)
            combo_eng.addItem("Google Gemini AI (API Key)", userData="gemini")
            combo_eng.addItem("ChatGPT Web (Cookie Trình Duyệt)", userData="chatgpt_web")
            combo_eng.addItem("Custom API", userData="custom_api")
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

        layout_ca.addWidget(SubtitleLabel("Custom API"))

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
            if hasattr(self_si, "text_api_keys"):
                curr_text = self_si.text_api_keys.toPlainText()
                clean_lines = [
                    line.strip() for line in curr_text.splitlines()
                    if line.strip() and not any(k in line for k in ("ROUTED_KEY", "CUSTOM_API", "CHATGPT_WEB", "AIzaSy_DUMMY"))
                ]
                self_si.text_api_keys.setPlainText("\n".join(clean_lines))
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
            if hasattr(self_si, "text_api_keys"):
                curr_text = self_si.text_api_keys.toPlainText()
                clean_lines = [
                    line.strip() for line in curr_text.splitlines()
                    if line.strip() and not any(k in line for k in ("ROUTED_KEY", "CUSTOM_API", "CHATGPT_WEB", "AIzaSy_DUMMY"))
                ]
                self_si.text_api_keys.setPlainText("\n".join(clean_lines))
            orig_save(show_msg=False)
            cfg = load_config()
            if "gemini_keys" in cfg and isinstance(cfg["gemini_keys"], list):
                cfg["gemini_keys"] = [
                    k for k in cfg["gemini_keys"]
                    if not any(r in str(k) for r in ("ROUTED_KEY", "CUSTOM_API", "CHATGPT_WEB", "AIzaSy_DUMMY"))
                ]
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

        lbl_eng = BodyLabel("Động cơ AI:")
        lbl_eng.setStyleSheet("color: #94A3B8; font-weight: bold;")
        combo_eng = ComboBox(container)
        combo_eng.addItem("Google Gemini AI", userData="gemini")
        combo_eng.addItem("ChatGPT Web (Cookie)", userData="chatgpt_web")
        combo_eng.addItem("Custom API", userData="custom_api")
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

        
        def _get_current_ws(hi):
            try:
                out_d = hi.line_output_path.text() if hasattr(hi, "line_output_path") else ""
                idx = hi.video_combo.currentIndex() if hasattr(hi, "video_combo") else -1
                if out_d and hasattr(hi, "selected_videos") and 0 <= idx < len(hi.selected_videos):
                    from app.views.home_interface import get_safe_basename
                    v_p = hi.selected_videos[idx]
                    return os.path.join(out_d, get_safe_basename(v_p))
            except Exception:
                pass
            return None

        def _update_btn_step2_status():
            try:
                ws = _get_current_ws(home_interface)
                if not ws or not hasattr(home_interface, "btn_step2"):
                    return
                from translation_checkpoint import get_workspace_translation_status
                comp, tot = get_workspace_translation_status(ws)
                if 0 < comp < tot:
                    home_interface.btn_step2.setText(f"2. Tiếp tục dịch ({comp}/{tot})")
                    home_interface.btn_step2.setToolTip(f"Đã dịch {comp}/{tot} câu. Nhấn để tiếp tục dịch {tot - comp} câu còn lại.\n(Chuột phải để chọn 'Dịch lại từ đầu')")
                else:
                    home_interface.btn_step2.setText("2. Dịch")
                    home_interface.btn_step2.setToolTip("Dịch kịch bản gốc sang ngôn ngữ đã chọn.")
            except Exception as _e_status:
                pass

        home_interface._update_translate_btn_status = _update_btn_step2_status

        try:
            if hasattr(home_interface, "btn_step2") and home_interface.btn_step2:
                from PyQt6.QtCore import Qt
                from PyQt6.QtWidgets import QMenu
                home_interface.btn_step2.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                def _on_btn_step2_menu(pos):
                    ws = _get_current_ws(home_interface)
                    menu = QMenu(home_interface)
                    act_resume = menu.addAction("Tiếp tục dịch (giữ các câu đã dịch)")
                    act_restart = menu.addAction("Dịch lại từ đầu (0%)")
                    action = menu.exec(home_interface.btn_step2.mapToGlobal(pos))
                    if action == act_restart:
                        if ws:
                            from translation_checkpoint import TranslationProgressManager
                            target_l = home_interface.combo_target_lang.currentText() if hasattr(home_interface, "combo_target_lang") else "Tiếng Việt"
                            pm = TranslationProgressManager(ws, target_l)
                            pm.clear()
                            _update_btn_step2_status()
                        home_interface._onTranslateClicked()
                    elif action == act_resume:
                        home_interface._onTranslateClicked()
                home_interface.btn_step2.customContextMenuRequested.connect(_on_btn_step2_menu)
        except Exception as _e_menu:
            _voice_log("btn_step2 context menu setup error: %r" % (_e_menu,))

        if hasattr(home_interface, "video_combo") and home_interface.video_combo:
            home_interface.video_combo.currentIndexChanged.connect(lambda: _update_btn_step2_status())
        _update_btn_step2_status()

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

                from translation_checkpoint import TranslationProgressManager, parse_srt_subtitles, format_srt_content
                pm = TranslationProgressManager(workspace_dir, target_lang)
                with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    subtitles = parse_srt_subtitles(f.read())
                total_subs = len(subtitles)

                translated_map, missing_indices = pm.load_progress(subtitles)
                if len(missing_indices) == 0:
                    status_cb(f"Tất cả {total_subs} câu đã được dịch hoàn tất từ trước.", 1.0)
                    pm.mark_completed(subtitles)
                    return pm.out_srt_file

                if len(translated_map) > 0:
                    status_cb(
                        f"[TIẾP TỤC DỊCH] Đã có {len(translated_map)}/{total_subs} câu. "
                        f"Đang tiếp tục dịch {len(missing_indices)} câu còn lại với Gemini...",
                        0.05 + 0.90 * (len(translated_map) / total_subs)
                    )

                # Attempt using official Google Generative Language OpenAI endpoint with custom_api
                try:
                    import custom_api
                    g_keys = api_keys if isinstance(api_keys, (list, tuple)) else [api_keys]
                    return custom_api.custom_api_translate_logic(
                        srt_path=srt_path,
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                        api_keys=g_keys,
                        model="gemini-1.5-flash",
                        status_cb=status_cb,
                        cancel_event=cancel_event,
                        workspace_dir=workspace_dir,
                        prompt_style=prompt_style,
                        custom_prompt_text=custom_prompt_text,
                        target_lang=target_lang,
                        **kwargs
                    )
                except Exception as g_exc:
                    _voice_log("Gemini OpenAI endpoint attempt error: %r; fallback to orig_tl" % (g_exc,))
                    if orig_tl:
                        if len(translated_map) > 0 and len(missing_indices) < total_subs:
                            missing_subs = [subtitles[i] for i in missing_indices]
                            sub_dir = os.path.join(workspace_dir, "Data", "_temp_gemini_part")
                            os.makedirs(sub_dir, exist_ok=True)
                            sub_srt = os.path.join(sub_dir, "temp_original.srt")
                            with open(sub_srt, "w", encoding="utf-8") as f:
                                f.write(format_srt_content(missing_subs))
                            call_original_with_vietnamese_rules(sub_srt, api_keys, status_cb, cancel_event, sub_dir, prompt_style, custom_prompt_text, target_lang, kwargs)
                            res_srt = os.path.join(sub_dir, "temp_translated.srt")
                            if os.path.isfile(res_srt):
                                with open(res_srt, "r", encoding="utf-8-sig", errors="replace") as f:
                                    t_subs = parse_srt_subtitles(f.read())
                                for idx, ts in zip(missing_indices, t_subs):
                                    pm.translations[idx] = ts.get("text", "")
                                pm.mark_completed(subtitles)
                                return pm.out_srt_file
                        return call_original_with_vietnamese_rules(srt_path, api_keys, status_cb, cancel_event, workspace_dir, prompt_style, custom_prompt_text, target_lang, kwargs)
                    raise g_exc

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

            # Check if there is partial translation to notify in log
            try:
                from translation_checkpoint import get_workspace_translation_status
                comp, tot = get_workspace_translation_status(workspace_dir)
                if 0 < comp < tot:
                    self._appendLog(f"[TIẾP TỤC DỊCH] Phát hiện tiến trình dịch dở dang ({comp}/{tot} câu). Đang tiếp tục dịch {tot - comp} câu còn lại...")
            except Exception:
                pass

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

            def _wrapped_translate_finished(res_srt):
                self._onTranslateFinished(res_srt)
                if hasattr(self, "_update_translate_btn_status"):
                    self._update_translate_btn_status()

            def _wrapped_translate_error(err_msg):
                self._onTranscribeError(err_msg)
                if hasattr(self, "_update_translate_btn_status"):
                    self._update_translate_btn_status()
                try:
                    from translation_checkpoint import get_workspace_translation_status
                    comp, tot = get_workspace_translation_status(workspace_dir)
                    if 0 < comp < tot:
                        InfoBar.info(
                            title="Đã lưu tiến trình dịch",
                            content=f"Đã lưu an toàn {comp}/{tot} câu vào file. Nhấn 'Tiếp tục dịch' để dịch tiếp các câu còn lại!",
                            parent=self.window(),
                            position=InfoBarPosition.TOP,
                            duration=9000
                        )
                except Exception:
                    pass

            self.translate_worker.finished_srt.connect(_wrapped_translate_finished)
            self.translate_worker.error.connect(_wrapped_translate_error)
            self.translate_worker.start()

        HomeInterface._onTranslateClicked = patched_on_translate_clicked

        # Patch _onApplyToAllClicked to sync wm_scale, wm_rel_x, wm_rel_y, etc. across all videos and config.json
        orig_hi_apply_all = getattr(HomeInterface, "_onApplyToAllClicked", None)
        def lua_on_apply_to_all_clicked(self):
            try:
                from qfluentwidgets import InfoBar, InfoBarPosition
                current_idx = self.video_combo.currentIndex()
                if current_idx < 0 or current_idx >= len(self.selected_videos):
                    return
                video_path = self.selected_videos[current_idx]
                current_config = self.per_video_configs.get(video_path, {})
                if not current_config:
                    current_config = {}

                # 1. Sync canvas state to current_config
                if hasattr(self, "video_canvas") and self.video_canvas:
                    vc = self.video_canvas
                    try:
                        if hasattr(vc, "saveConfig"):
                            vc.saveConfig()
                    except Exception:
                        pass
                    for attr in (
                        "wm_scale", "wm_rel_x", "wm_rel_y", "wm_text", "wm_font_name",
                        "wm_font_color", "wm_border_style", "wm_border_color", "wm_effect_style", "wm_opacity",
                        "sub_scale", "sub_rel_x", "sub_rel_y", "sub_font_name", "sub_font_color",
                        "sub_border_style", "sub_border_color", "sub_effect_style",
                        "logo_scale", "logo_rel_x", "logo_rel_y", "logo_path",
                        "bg_frame_scale", "bg_frame_rel_x", "bg_frame_rel_y", "bg_frame_path",
                        "masks_rel", "ocr_rel"
                    ):
                        if hasattr(vc, attr):
                            val = getattr(vc, attr)
                            if attr == "masks_rel":
                                current_config["mask_logos"] = val
                            elif attr == "ocr_rel":
                                current_config["ocr_bbox_rel"] = val
                            else:
                                current_config[attr] = val

                # 2. Copy current_config to all other videos in per_video_configs
                import copy
                for path in self.selected_videos:
                    if path != video_path:
                        self.per_video_configs[path] = copy.deepcopy(current_config)

                # 3. Save to global config.json including wm_scale
                from app.common.config_manager import load_config, save_config
                glob_cfg = load_config()
                all_sync_keys = [
                    "sub_rel_x", "sub_rel_y", "sub_scale", "sub_font_name", "sub_font_color",
                    "sub_border_color", "sub_border_style", "sub_effect_style", "sub_karaoke_color",
                    "watermark_text", "watermark_sub_text", "wm_text", "wm_moving", "wm_speed",
                    "wm_rel_x", "wm_rel_y", "wm_scale", "wm_font_name", "wm_font_color",
                    "wm_border_style", "wm_border_color", "wm_effect_style", "wm_opacity",
                    "logo_path", "logo_rel_x", "logo_rel_y", "logo_scale",
                    "bg_frame_path", "bg_frame_rel_x", "bg_frame_rel_y", "bg_frame_scale",
                    "abs_ocr_bbox", "ocr_preprocess", "ocr_conf_thresh", "ocr_fps",
                    "show_subtitle", "audio_mode", "vol_bgm", "vol_voice", "mask_regions", "mask_logos"
                ]
                for k in all_sync_keys:
                    if k in current_config:
                        glob_cfg[k] = current_config[k]
                save_config(glob_cfg)

                InfoBar.success(
                    title="Thành công",
                    content="Đã áp dụng cấu hình (vị trí, kích thước watermark/phụ đề) cho tất cả video và lưu làm mặc định!",
                    parent=self.window(),
                    position=InfoBarPosition.TOP,
                    duration=7000
                )
            except Exception as exc:
                _voice_log("lua_on_apply_to_all_clicked error: %r" % (exc,))
                if orig_hi_apply_all:
                    orig_hi_apply_all(self)

        HomeInterface._onApplyToAllClicked = lua_on_apply_to_all_clicked

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
            setup_update_settings_ui(self, get_current_app_version())
        SettingInterface.__init__ = patched_si_init

        _voice_log("ChatGPT translation runtime patch installed successfully")
    except Exception as exc:
        _voice_log("install_chatgpt_translation_patch failed: %r" % (exc,))
UNIFIED_AI_BRIDGE_INSTALLED = False

def install_unified_ai_bridge():
    """Unifies all AI features across the application (Translation, Audio Sentence Shortening,
    Title & Prompt generation, Highlight analysis) to follow the user's selected translation_engine.
    Guarantees seamless routing for google.genai, google.generativeai, requests, and urllib.
    """
    global UNIFIED_AI_BRIDGE_INSTALLED
    if UNIFIED_AI_BRIDGE_INSTALLED:
        return
    try:
        import app.common.config_manager as cm

        # 1. Config Manager Patch:
        # Never corrupt gemini_keys for the Settings UI. Only supply routed key for backend validation.
        _real_load_config = cm.load_config
        def _bridged_load_config(*args, **kwargs):
            cfg = _real_load_config(*args, **kwargs)
            if not isinstance(cfg, dict):
                return cfg

            # Inspect stack to check if called by SettingInterface / UI
            import inspect
            is_ui = False
            try:
                for frame_info in inspect.stack()[1:5]:
                    f_name = str(frame_info.filename).lower()
                    if "setting_interface" in f_name or "ai_dialog" in f_name:
                        is_ui = True
                        break
            except Exception:
                pass

            if is_ui:
                clean_cfg = dict(cfg)
                if "gemini_keys" in clean_cfg and isinstance(clean_cfg["gemini_keys"], list):
                    clean_cfg["gemini_keys"] = [
                        k for k in clean_cfg["gemini_keys"]
                        if not any(r in str(k) for r in ("ROUTED_KEY", "CUSTOM_API", "CHATGPT_WEB", "AIzaSy_DUMMY"))
                    ]
                return clean_cfg

            # For backend AI callers (audio_generator, ai_translator):
            engine = cfg.get("translation_engine", "gemini")
            if engine in ("custom_api", "chatgpt_web"):
                backed_cfg = dict(cfg)
                g_keys = backed_cfg.get("gemini_keys", [])
                if not g_keys or (len(g_keys) == 1 and str(g_keys[0]).startswith("AQ.")):
                    backed_cfg["gemini_keys"] = ["ROUTED_AI_KEY"]
                return backed_cfg

            return cfg
        cm.load_config = _bridged_load_config

        _real_get_config = cm.get_config
        def _bridged_get_config(key, default=None):
            if key == "gemini_keys":
                cfg = _bridged_load_config()
                return cfg.get("gemini_keys", default)
            return _real_get_config(key, default)
        cm.get_config = _bridged_get_config

        class UnifiedPart:
            def __init__(self, text):
                self.text = text
            def __str__(self):
                return self.text
            def __repr__(self):
                return f"UnifiedPart(text={self.text!r})"

        class UnifiedContent:
            def __init__(self, text):
                self.parts = [UnifiedPart(text)]
                self.role = "model"

        class UnifiedCandidate:
            def __init__(self, text):
                self.content = UnifiedContent(text)
                self.finish_reason = 1
                self.index = 0

        class UnifiedAIResponse:
            def __init__(self, text):
                self._text = text
                self.parts = [UnifiedPart(text)]
                self.candidates = [UnifiedCandidate(text)]

            @property
            def text(self):
                return self._text

            @text.setter
            def text(self, val):
                self._text = val

            def to_dict(self):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": self._text}],
                                "role": "model"
                            },
                            "finishReason": "STOP",
                            "index": 0
                        }
                    ]
                }

            def __str__(self):
                return self._text

            def __repr__(self):
                return f"UnifiedAIResponse(text={self._text!r})"

        def _extract_prompt_text(contents):
            if isinstance(contents, str):
                return contents
            if isinstance(contents, (list, tuple)):
                parts = []
                for item in contents:
                    if isinstance(item, str):
                        parts.append(item)
                    elif hasattr(item, "text") and isinstance(item.text, str):
                        parts.append(item.text)
                    elif isinstance(item, dict):
                        sub_parts = item.get("parts", [])
                        for sp in sub_parts:
                            if isinstance(sp, str):
                                parts.append(sp)
                            elif isinstance(sp, dict) and "text" in sp:
                                parts.append(sp["text"])
                            elif hasattr(sp, "text"):
                                parts.append(str(sp.text))
                    elif hasattr(item, "parts"):
                        for sp in getattr(item, "parts", []):
                            if isinstance(sp, str):
                                parts.append(sp)
                            elif hasattr(sp, "text"):
                                parts.append(str(sp.text))
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            if hasattr(contents, "text"):
                return contents.text
            return str(contents)

        def _extract_original_sentence_fallback(prompt_text):
            import re
            m = re.findall(r'["“](.+?)["”]', prompt_text)
            if m:
                return max(m, key=len).strip()
            m = re.findall(r"['‘](.+?)['’]", prompt_text)
            if m:
                return max(m, key=len).strip()
            if ":" in prompt_text:
                return prompt_text.split(":", 1)[1].strip()
            lines = [l.strip() for l in prompt_text.splitlines() if l.strip()]
            return lines[-1] if lines else prompt_text

        def _execute_unified_completion(cfg, engine, contents, config=None):
            prompt_text = _extract_prompt_text(contents)
            if not prompt_text:
                return UnifiedAIResponse("")

            is_shorten = any(kw in prompt_text.lower() for kw in ("rút gọn", "rut gon", "ngắn hơn", "thu gọn", "shorten", "lược bỏ"))

            if engine == "custom_api":
                import custom_api
                base_url = cfg.get("custom_api_base_url", "")
                keys = cfg.get("custom_api_key", "")
                ca_model = cfg.get("custom_api_model", "")
                keys_list = custom_api.extract_api_keys(keys)
                if not keys_list:
                    raise ValueError("Chưa cấu hình Custom API Key trong Cài đặt!")

                client = custom_api.CustomAPIClient(base_url, keys_list, ca_model)
                try:
                    resp_text = client.send_completion([
                        {"role": "user", "content": prompt_text}
                    ], temperature=0.3)
                except Exception as api_err:
                    if is_shorten:
                        _voice_log("AI rút gọn câu gặp giới hạn tần suất API (%r), tự động giữ nguyên câu gốc để tiếp tục xuất video..." % (api_err,))
                        fallback_text = _extract_original_sentence_fallback(prompt_text)
                        return UnifiedAIResponse(fallback_text)
                    raise api_err

                if not resp_text:
                    if is_shorten:
                        return UnifiedAIResponse(_extract_original_sentence_fallback(prompt_text))
                    raise RuntimeError("Custom API trả về kết quả rỗng khi gọi AI.")

                # If json is expected, strip markdown code fences
                is_json = False
                if config and hasattr(config, "response_mime_type") and "json" in str(config.response_mime_type).lower():
                    is_json = True
                elif "json" in prompt_text.lower() and "{" in prompt_text:
                    is_json = True

                if is_json:
                    clean = resp_text.strip()
                    if clean.startswith("```json"):
                        clean = clean[7:]
                    elif clean.startswith("```"):
                        clean = clean[3:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    resp_text = clean.strip()

                return UnifiedAIResponse(resp_text)

            elif engine == "chatgpt_web":
                import chatgpt_web
                cookies = cfg.get("chatgpt_cookies", [])
                if not cookies:
                    raise ValueError("Chưa cấu hình Cookie ChatGPT Web trong Cài đặt!")
                client = chatgpt_web.ChatGPTWebClient(cookies)
                resp_text = client.send_message(prompt_text, model=cfg.get("chatgpt_model", "auto"))
                if not resp_text:
                    raise RuntimeError("ChatGPT Web trả về kết quả rỗng khi gọi AI.")
                return UnifiedAIResponse(resp_text)

            return UnifiedAIResponse("")

        # 2. Patch google.genai Client & Models.generate_content
        try:
            from google.genai.models import Models
            from google.genai.client import Client

            _orig_client_init = Client.__init__
            def _bridged_client_init(self, *args, **kwargs):
                cfg = _real_load_config()
                engine = cfg.get("translation_engine", "gemini")
                if engine in ("custom_api", "chatgpt_web"):
                    if not kwargs.get("api_key") or str(kwargs.get("api_key", "")).startswith("AQ."):
                        kwargs["api_key"] = "ROUTED_AI_KEY"
                return _orig_client_init(self, *args, **kwargs)
            Client.__init__ = _bridged_client_init

            if not getattr(Models.generate_content, "_unified_ai_wrap", False):
                _orig_generate_content = Models.generate_content

                def _unified_generate_content(self, *, model, contents, config=None, **kwargs):
                    cfg = _real_load_config()
                    engine = cfg.get("translation_engine", "gemini")
                    if engine in ("custom_api", "chatgpt_web"):
                        return _execute_unified_completion(cfg, engine, contents, config=config)
                    return _orig_generate_content(self, model=model, contents=contents, config=config, **kwargs)

                _unified_generate_content._unified_ai_wrap = True
                Models.generate_content = _unified_generate_content
        except Exception as genai_err:
            _voice_log("google.genai hook note: %r" % (genai_err,))

        # 3. Patch google.generativeai (Legacy SDK used by audio sentence shortening & generators)
        try:
            import google.generativeai as genai
            import google.generativeai.generative_models as gm

            if not getattr(gm.GenerativeModel.generate_content, "_unified_ai_wrap", False):
                _orig_gm_gen_content = gm.GenerativeModel.generate_content

                def _unified_gm_generate_content(self, contents, *args, **kwargs):
                    cfg = _real_load_config()
                    engine = cfg.get("translation_engine", "gemini")
                    if engine in ("custom_api", "chatgpt_web"):
                        return _execute_unified_completion(cfg, engine, contents, kwargs.get("generation_config"))
                    return _orig_gm_gen_content(self, contents, *args, **kwargs)

                _unified_gm_generate_content._unified_ai_wrap = True
                gm.GenerativeModel.generate_content = _unified_gm_generate_content

            if hasattr(gm.GenerativeModel, "generate_content_async"):
                _orig_gm_gen_async = gm.GenerativeModel.generate_content_async
                async def _unified_gm_generate_content_async(self, contents, *args, **kwargs):
                    cfg = _real_load_config()
                    engine = cfg.get("translation_engine", "gemini")
                    if engine in ("custom_api", "chatgpt_web"):
                        return _execute_unified_completion(cfg, engine, contents, kwargs.get("generation_config"))
                    return await _orig_gm_gen_async(self, contents, *args, **kwargs)
                gm.GenerativeModel.generate_content_async = _unified_gm_generate_content_async

            if hasattr(gm, "ChatSession"):
                if hasattr(gm.ChatSession, "send_message"):
                    _orig_cs_send = gm.ChatSession.send_message
                    def _unified_cs_send_message(self, content, *args, **kwargs):
                        cfg = _real_load_config()
                        engine = cfg.get("translation_engine", "gemini")
                        if engine in ("custom_api", "chatgpt_web"):
                            return _execute_unified_completion(cfg, engine, content, kwargs.get("generation_config"))
                        return _orig_cs_send(self, content, *args, **kwargs)
                    gm.ChatSession.send_message = _unified_cs_send_message

            _orig_genai_configure = genai.configure
            def _unified_genai_configure(*args, **kwargs):
                cfg = _real_load_config()
                engine = cfg.get("translation_engine", "gemini")
                if engine in ("custom_api", "chatgpt_web"):
                    if not kwargs.get("api_key"):
                        kwargs["api_key"] = "AIzaSy_MOCK_ROUTED_KEY"
                try:
                    return _orig_genai_configure(*args, **kwargs)
                except Exception:
                    pass
            genai.configure = _unified_genai_configure

        except Exception as legacy_genai_err:
            _voice_log("google.generativeai hook note: %r" % (legacy_genai_err,))

        # 4. Patch requests.Session.send to capture any direct REST requests to Gemini API
        try:
            import requests
            _orig_requests_send = requests.Session.send

            def _unified_requests_send(self, request, **kwargs):
                url = getattr(request, "url", "")
                if "generativelanguage.googleapis.com" in url:
                    cfg = _real_load_config()
                    engine = cfg.get("translation_engine", "gemini")
                    if engine in ("custom_api", "chatgpt_web"):
                        import json
                        prompt_text = ""
                        try:
                            body = request.body
                            if isinstance(body, bytes):
                                body = body.decode("utf-8", errors="ignore")
                            if isinstance(body, str):
                                b_json = json.loads(body)
                                contents = b_json.get("contents", [])
                                prompt_text = _extract_prompt_text(contents)
                        except Exception:
                            prompt_text = str(getattr(request, "body", ""))

                        ai_resp = _execute_unified_completion(cfg, engine, prompt_text)
                        resp_content = json.dumps(ai_resp.to_dict()).encode("utf-8")

                        from requests.models import Response
                        import io
                        mock_resp = Response()
                        mock_resp.status_code = 200
                        mock_resp.reason = "OK"
                        mock_resp.url = url
                        mock_resp.headers = {"Content-Type": "application/json; charset=utf-8"}
                        mock_resp.raw = io.BytesIO(resp_content)
                        mock_resp._content = resp_content
                        return mock_resp

                return _orig_requests_send(self, request, **kwargs)

            requests.Session.send = _unified_requests_send
        except Exception as req_err:
            _voice_log("requests hook note: %r" % (req_err,))

        # 5. Patch urllib.request.urlopen to capture any direct urllib requests to Gemini API
        try:
            import urllib.request
            _orig_urlopen = urllib.request.urlopen

            def _unified_urlopen(url_or_req, *args, **kwargs):
                url = url_or_req.full_url if hasattr(url_or_req, "full_url") else str(url_or_req)
                if "generativelanguage.googleapis.com" in url:
                    cfg = _real_load_config()
                    engine = cfg.get("translation_engine", "gemini")
                    if engine in ("custom_api", "chatgpt_web"):
                        import json
                        prompt_text = ""
                        try:
                            data = getattr(url_or_req, "data", None)
                            if isinstance(data, bytes):
                                data = data.decode("utf-8", errors="ignore")
                            if data:
                                b_json = json.loads(data)
                                contents = b_json.get("contents", [])
                                prompt_text = _extract_prompt_text(contents)
                        except Exception:
                            pass

                        ai_resp = _execute_unified_completion(cfg, engine, prompt_text)
                        resp_content = json.dumps(ai_resp.to_dict()).encode("utf-8")
                        import io
                        class MockHTTPResponse(io.BytesIO):
                            def getcode(self): return 200
                            def info(self): return {"Content-Type": "application/json"}
                        return MockHTTPResponse(resp_content)

                return _orig_urlopen(url_or_req, *args, **kwargs)

            urllib.request.urlopen = _unified_urlopen
        except Exception as url_err:
            _voice_log("urllib hook note: %r" % (url_err,))

        UNIFIED_AI_BRIDGE_INSTALLED = True
        _voice_log("Unified AI Bridge installed successfully: all AI tasks (Gemini/Audio Shortening/Custom API) unified")
    except Exception as exc:
        _voice_log("install_unified_ai_bridge failed: %r" % (exc,))


def get_current_app_version(default="2.6"):
    try:
        from updater_runtime import get_app_dir
        app_dir = get_app_dir()
        for p in [app_dir / "_internal" / "update_config.json", app_dir / "update_config.json"]:
            if p.is_file():
                import json
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("version"):
                    return str(data["version"]).strip()
        for p in [app_dir / "_internal" / "installed_version.txt", app_dir / "installed_version.txt"]:
            if p.is_file():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
    except Exception:
        pass
    try:
        import sys
        main_mod = sys.modules.get("__main__")
        if main_mod and hasattr(main_mod, "APP_VERSION"):
            return str(main_mod.APP_VERSION)
    except Exception:
        pass
    return default


def setup_update_settings_ui(setting_interface, app_version=None):
    """Inject modern Software Update Card into SettingInterface."""
    try:
        import updater_runtime
        app_version = get_current_app_version()
        try:
            import sys
            main_mod = sys.modules.get("__main__")
            if main_mod:
                main_mod.APP_VERSION = app_version
        except Exception:
            pass
        updater_runtime.setup_update_settings_ui(setting_interface, app_version)
    except Exception as exc:
        _voice_log("setup_update_settings_ui failed: %r" % (exc,))


def handle_check_update(window, app_version=None):
    """Check for updates at startup and show interactive dialog if new release found."""
    try:
        import updater_runtime
        app_version = get_current_app_version()
        try:
            window.setWindowTitle(f"luaVietsup v{app_version}")
        except Exception:
            pass
        try:
            import sys
            main_mod = sys.modules.get("__main__")
            if main_mod:
                main_mod.APP_VERSION = app_version
        except Exception:
            pass
        updater_runtime.handle_app_start_update_check(window, app_version)
    except Exception as exc:
        _voice_log("handle_check_update failed: %r" % (exc,))


# ============================================================================
# luaVietsup additions: original-voice mode and dual (bilingual) subtitles.
#
# Two optional switches are injected into the Home control panel:
#   * "Kèm phụ đề gốc (song ngữ)"            -> config key `dual_subtitle`
#   * "Dùng giọng gốc (bỏ qua tạo giọng AI)" -> config key `use_original_voice`
#
# The protected render/TTS cores stay untouched; behaviour changes only via the
# same monkey-patch points this file already owns:
#   - HomeInterface._onVoiceClicked / _onRenderClicked and VoiceWorker.run
#     swap the TTS step for a fast original-audio extraction into
#     Data/temp_audio_tong.pcm (the standard voice track the render mixes).
#   - safe_render_logic hands the FFmpeg patch the original-language SRT, and
#     RobustPopen appends a second `subtitles=` filter (top of the frame,
#     smaller font) so the exported video shows both languages.
# ============================================================================

OV_DUAL_PATCH_INSTALLED = False

_LUA_DUAL_PENDING = {'srt': None, 'rel': None, 'keys': None}


def _lua_flag_on(key):
    try:
        from app.common.config_manager import get_config
        return bool(get_config(key, False))
    except Exception:
        return False


def use_original_voice_on():
    return _lua_flag_on('use_original_voice')


def dual_subtitle_on():
    return _lua_flag_on('dual_subtitle')


def _lua_ffmpeg_exe():
    bundle = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(sys.executable), '_internal'))
    ffmpeg = os.environ.get('FFMPEG_BINARY') or os.path.join(bundle, 'ffmpeg', 'ffmpeg.exe')
    if not os.path.isfile(ffmpeg):
        ffmpeg = os.environ.get('IMAGEIO_FFMPEG_EXE') or 'ffmpeg'
    return ffmpeg


def _lua_short_path(path):
    if os.name == 'nt' and path:
        try:
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 512) and buf.value:
                return buf.value
        except Exception:
            pass
    return str(path)


def _lua_workspace_keys(workspace_dir):
    """Accept both the normal and the 8.3-short form of the workspace path."""
    keys = set()
    try:
        keys.add(os.path.normcase(os.path.abspath(str(workspace_dir))))
        short = _lua_short_path(str(workspace_dir))
        if short:
            keys.add(os.path.normcase(os.path.abspath(short)))
    except Exception:
        pass
    return keys or None


def _lua_marker_path(pcm_path):
    return str(pcm_path) + '.ov_info'


def _lua_write_marker(pcm_path, video_path):
    try:
        st = os.stat(video_path)
        Path(_lua_marker_path(pcm_path)).write_text(
            '%s|%d|%d' % (os.path.abspath(str(video_path)), int(st.st_mtime), int(st.st_size)),
            encoding='utf-8')
    except Exception:
        pass


def _lua_clear_marker(pcm_path):
    try:
        os.remove(_lua_marker_path(pcm_path))
    except OSError:
        pass


def _lua_ov_pcm_valid(pcm_path, video_path):
    """True when the PCM is known to be this exact video's original audio."""
    try:
        if not os.path.isfile(pcm_path) or os.path.getsize(pcm_path) <= 44:
            return False
        parts = Path(_lua_marker_path(pcm_path)).read_text(encoding='utf-8').split('|')
        if len(parts) != 3:
            return False
        if parts[0] != os.path.abspath(str(video_path)):
            return False
        st = os.stat(video_path)
        return int(parts[1]) == int(st.st_mtime) and int(parts[2]) == int(st.st_size)
    except Exception:
        return False


def _lua_video_duration(video_path):
    try:
        res = subprocess.run(
            [_lua_ffmpeg_exe(), '-i', str(video_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        m = re.search(r'Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)', res.stderr.decode('utf-8', 'replace'))
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return None


def _lua_srt_end_duration(pcm_path):
    """Fallback duration: the last cue end of the SRTs sitting next to the PCM."""
    best = 0.0
    data_dir = os.path.dirname(str(pcm_path))
    for name in ('temp_original.srt', 'temp_translated.srt'):
        path = os.path.join(data_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            text = Path(path).read_text(encoding='utf-8-sig', errors='replace')
            for m in re.finditer(r'-->\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3})', text):
                end = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0
                best = max(best, end)
        except Exception:
            continue
    return best or None


def _lua_extract_original_pcm(video_path, pcm_path):
    """Write the video's own audio as the voice PCM (s16le / 44100 Hz / stereo)."""
    pcm_path = str(pcm_path)
    try:
        os.makedirs(os.path.dirname(pcm_path), exist_ok=True)
    except Exception:
        pass
    tmp_path = pcm_path + '.ov_tmp'
    ffmpeg = _lua_ffmpeg_exe()
    try:
        res = subprocess.run(
            [ffmpeg, '-y', '-v', 'error', '-i', str(video_path), '-map', '0:a:0?', '-vn',
             '-f', 's16le', '-ar', '44100', '-ac', '2', tmp_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=3600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        ok = res.returncode == 0 and os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 44
    except Exception:
        ok = False
    if not ok:
        # Video has no usable audio stream: fall back to silence so the render
        # pipeline keeps working (its own silent-track fix also kicks in).
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        duration = _lua_video_duration(video_path) or _lua_srt_end_duration(pcm_path) or 30.0
        duration = max(0.5, min(duration, 7200.0))
        res = subprocess.run(
            [ffmpeg, '-y', '-v', 'error',
             '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
             '-t', ('%.3f' % duration), '-f', 's16le', tmp_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=300, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if res.returncode != 0 or not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) <= 44:
            detail = res.stderr.decode('utf-8', 'replace')[-600:]
            raise RuntimeError('Không trích xuất được âm thanh gốc: ' + detail)
    os.replace(tmp_path, pcm_path)
    _lua_write_marker(pcm_path, video_path)
    return pcm_path


def _lua_ensure_original_pcm_for_render(video_path, workspace_dir, status_cb=None, audio_path=None):
    """In original-voice mode, make sure the mixed voice track is the video's audio."""
    pcm_path = os.path.join(str(workspace_dir), 'Data', 'temp_audio_tong.pcm')
    try:
        standard = os.path.normcase(os.path.abspath(str(audio_path or ''))) == os.path.normcase(os.path.abspath(pcm_path))
    except Exception:
        standard = False
    if audio_path and not standard and os.path.isfile(str(audio_path)):
        # Another pipeline supplied its own audio track; never hijack it.
        return audio_path
    if _lua_ov_pcm_valid(pcm_path, video_path):
        return pcm_path
    if callable(status_cb):
        try:
            status_cb('Chế độ Dùng giọng gốc: đang trích xuất âm thanh gốc...', 0.03)
        except Exception:
            pass
    _lua_extract_original_pcm(video_path, pcm_path)
    return pcm_path


def _lua_inject_dual_subtitle(fc_val, output_path, cwd):
    """Append a second `subtitles=` filter burning the original-language SRT."""
    try:
        if not _LUA_DUAL_PENDING.get('srt'):
            return None
        keys = _LUA_DUAL_PENDING.get('keys')
        if not keys:
            return None
        candidates = set()
        for base in (cwd, os.path.dirname(str(output_path)) if output_path else None):
            if base:
                try:
                    candidates.add(os.path.normcase(os.path.abspath(str(base))))
                except Exception:
                    pass
        if not candidates or not (candidates & keys):
            return None
        if "subtitles='" not in fc_val:
            return None
        used = re.search(r"subtitles='([^']+)'", fc_val)
        if not used:
            return None
        used_path = used.group(1).replace('\\\\', '\\').replace('\\', '/')
        if 'temp_original' in used_path:
            # The main track is already the untranslated original subtitles.
            return None
        rel = _LUA_DUAL_PENDING.get('rel') or str(_LUA_DUAL_PENDING['srt']).replace('\\', '/')
        fontsdir_m = re.search(r":fontsdir='([^']+)'", fc_val)
        fontsdir = fontsdir_m.group(1) if fontsdir_m else 'Data/temp_fonts'
        size_m = re.search(r'FontSize=(\d+(?:\.\d+)?)', fc_val)
        base_size = float(size_m.group(1)) if size_m else 0.0
        size = int(round(base_size * 0.75)) if base_size >= 8 else 16
        size = max(10, min(72, size))
        margin = max(18, int(round(size * 1.4)))
        style = ('Alignment=8,MarginV=%d,FontSize=%d,PrimaryColour=&H00FFFFFF,'
                 'OutlineColour=&H00000000,BorderStyle=1,Outline=1.2,Shadow=0,Bold=1' % (margin, size))
        font_m = re.search(r'FontName=([^,\']+)', fc_val)
        if font_m:
            style = 'FontName=' + font_m.group(1) + ',' + style
        second = "subtitles='%s':fontsdir='%s':force_style='%s'" % (rel, fontsdir, style)
        fs_pos = fc_val.find(":force_style='", used.end())
        if fs_pos < 0:
            return None
        close = fc_val.find("'", fs_pos + len(":force_style='"))
        if close < 0:
            return None
        _voice_log('Dual-subtitle filter injected: %s' % second)
        return fc_val[:close + 1] + ',' + second + fc_val[close + 1:]
    except Exception as exc:
        _voice_log('Dual-subtitle injection failed: %r' % (exc,))
        return None


_LUA_FONT_MAP_CACHE = {}


def _lua_get_assets_fonts_dir():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'fonts'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'fonts'),
        os.path.join(os.path.dirname(sys.executable), 'assets', 'fonts'),
        os.path.join(os.path.dirname(sys.executable), '_internal', 'assets', 'fonts'),
        r'C:\Users\pc\Downloads\SirVietsub_Source_Full\SirVietsub_Source_Full\assets\fonts',
        r'C:\Users\pc\Downloads\SirVietsub_Source_Full\SirVietsub_Source_Full\_internal\assets\fonts',
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return os.path.abspath(c)
    return None


def _lua_get_libass_font_map():
    global _LUA_FONT_MAP_CACHE
    if _LUA_FONT_MAP_CACHE:
        return _LUA_FONT_MAP_CACHE
    fmap = {}
    f_dir = _lua_get_assets_fonts_dir()
    if f_dir and os.path.isdir(f_dir):
        import struct
        for fn in os.listdir(f_dir):
            if fn.lower().endswith(('.ttf', '.otf')):
                fp = os.path.join(f_dir, fn)
                base = os.path.splitext(fn)[0]
                try:
                    with open(fp, 'rb') as f:
                        data = f.read()
                    if data[:4] in (b'OTTO', b'\x00\x01\x00\x00', b'true'):
                        num_tables, = struct.unpack('>H', data[4:6])
                        name_offset = None
                        for i in range(num_tables):
                            if data[12+i*16:16+i*16] == b'name':
                                name_offset, = struct.unpack('>I', data[12+i*16+8:12+i*16+12])
                                break
                        if name_offset:
                            count, string_offset = struct.unpack('>HH', data[name_offset+2:name_offset+6])
                            storage = name_offset + string_offset
                            names = {}
                            for i in range(count):
                                rec = data[name_offset+6+i*12:name_offset+6+(i+1)*12]
                                plat, enc, lang, name_id, length, offset = struct.unpack('>HHHHHH', rec)
                                val = data[storage+offset:storage+offset+length]
                                try:
                                    s = val.decode('utf-16-be') if plat in (0, 3) else val.decode('latin1', 'ignore')
                                    names.setdefault(name_id, []).append(s)
                                except Exception:
                                    pass
                            id1 = names.get(1, [None])[0]
                            id4 = names.get(4, [None])[0]
                            libass_name = id1 or id4 or base
                            fmap[base] = libass_name
                            fmap[base.lower()] = libass_name
                            fmap[libass_name.lower()] = libass_name
                            if id4:
                                fmap[id4.lower()] = libass_name
                except Exception:
                    pass
    _LUA_FONT_MAP_CACHE = fmap
    return fmap


def _lua_extract_ttf_identity(font_path):
    try:
        import struct
        with open(font_path, 'rb') as f:
            data = f.read()
        if data[:4] not in (b'OTTO', b'\x00\x01\x00\x00', b'true'):
            return None
        num_tables, = struct.unpack('>H', data[4:6])
        name_offset = None
        for i in range(num_tables):
            if data[12+i*16:16+i*16] == b'name':
                name_offset, = struct.unpack('>I', data[12+i*16+8:12+i*16+12])
                break
        if not name_offset:
            return None
        count, string_offset = struct.unpack('>HH', data[name_offset+2:name_offset+6])
        storage = name_offset + string_offset
        names = {}
        for i in range(count):
            rec = data[name_offset+6+i*12:name_offset+6+(i+1)*12]
            plat, enc, lang, name_id, length, offset = struct.unpack('>HHHHHH', rec)
            val = data[storage+offset:storage+offset+length]
            try:
                s = val.decode('utf-16-be') if plat in (0, 3) else val.decode('latin1', 'ignore')
                names.setdefault(name_id, []).append(s)
            except Exception:
                pass
        id1 = names.get(1, [None])[0]
        id4 = names.get(4, [None])[0]
        return id1 or id4
    except Exception:
        return None


def _lua_get_configured_sub_font():
    try:
        from app.common.config_manager import get_config
        cf = get_config('sub_font_name', '')
        if cf:
            return str(cf).strip()
    except Exception:
        pass
    try:
        import json
        cfg_path = os.path.expanduser(r'~\AppData\Roaming\SirVietsub\config.json')
        if os.path.isfile(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as fh:
                d = json.load(fh)
                cf = d.get('sub_font_name', '')
                if cf:
                    return str(cf).strip()
    except Exception:
        pass
    return ''


def _lua_fix_render_fonts(fc_val, output_path, cwd):
    """Auto-heal subtitle font matching for FFmpeg libass to exactly match GUI preview."""
    try:
        if not fc_val or "subtitles=" not in fc_val:
            return fc_val

        ws_dir = cwd
        if not ws_dir and output_path:
            ws_dir = os.path.dirname(output_path)
        if not ws_dir or not os.path.isdir(ws_dir):
            return fc_val

        data_dir = os.path.join(ws_dir, "Data")
        if not os.path.isdir(data_dir):
            data_dir = ws_dir

        fonts_dir = os.path.join(data_dir, "temp_fonts")
        os.makedirs(fonts_dir, exist_ok=True)

        # Check existing font files in temp_fonts directly to detect what was copied by renderer
        existing_font_id = None
        for fn in os.listdir(fonts_dir):
            if fn.lower().endswith(('.ttf', '.otf')):
                f_id = _lua_extract_ttf_identity(os.path.join(fonts_dir, fn))
                if f_id and 'arial' not in f_id.lower():
                    existing_font_id = f_id
                    break

        # Pre-populate fonts_dir with all custom fonts from assets/fonts
        app_fonts = _lua_get_assets_fonts_dir()
        if app_fonts and os.path.isdir(app_fonts):
            for fn in os.listdir(app_fonts):
                if fn.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                    src_p = os.path.join(app_fonts, fn)
                    dst_p = os.path.join(fonts_dir, fn)
                    if not os.path.isfile(dst_p) or os.path.getsize(dst_p) != os.path.getsize(src_p):
                        try:
                            shutil.copy2(src_p, dst_p)
                        except Exception:
                            pass

        cfg_font = _lua_get_configured_sub_font()
        font_map = _lua_get_libass_font_map()

        target_libass_font = None
        if cfg_font:
            target_libass_font = font_map.get(cfg_font) or font_map.get(cfg_font.lower())

        if not target_libass_font and existing_font_id:
            target_libass_font = existing_font_id

        if not target_libass_font:
            font_m = re.search(r'FontName=([^,\']+)', fc_val)
            if font_m:
                raw_font = font_m.group(1).strip()
                target_libass_font = font_map.get(raw_font) or font_map.get(raw_font.lower())

        if not target_libass_font and cfg_font:
            target_libass_font = cfg_font.replace('-', ' ')

        if not target_libass_font:
            target_libass_font = 'Montserrat Black'

        # Replace FontName in force_style
        fc_val = re.sub(r'FontName=[^,\']+', 'FontName=' + target_libass_font, fc_val)

        # Also patch temp_translated_effect.ass and any ASS file in Data
        for ass_name in ('temp_translated_effect.ass', 'temp_translated.ass'):
            ass_path = os.path.join(data_dir, ass_name)
            if os.path.isfile(ass_path):
                try:
                    with open(ass_path, 'r', encoding='utf-8', errors='ignore') as fh:
                        ass_text = fh.read()
                    new_ass_text = re.sub(r'Style:\s*Default,[^,]+,', 'Style: Default,' + target_libass_font + ',', ass_text)
                    if new_ass_text != ass_text:
                        with open(ass_path, 'w', encoding='utf-8') as fh:
                            fh.write(new_ass_text)
                        _voice_log("Auto-patched ASS font header in %s -> %s" % (ass_name, target_libass_font))
                except Exception as e_ass:
                    _voice_log("Failed to patch ASS file %s: %r" % (ass_name, e_ass))

        _voice_log("FFmpeg subtitle font healed: FontName='%s' (fontsdir='%s')" % (target_libass_font, fonts_dir))
        return fc_val
    except Exception as exc:
        _voice_log("Error in _lua_fix_render_fonts: %r" % (exc,))
        return fc_val


def setup_original_voice_dual_sub_ui(home_interface):
    """Insert the two feature switches into the Home control panel."""
    try:
        if getattr(home_interface, '_lua_ov_ui_ready', False):
            return
        from PyQt6.QtWidgets import QHBoxLayout
        from qfluentwidgets import BodyLabel, SwitchButton
        from app.common.config_manager import get_config, set_config

        col1 = getattr(home_interface, 'col1_layout', None)
        if col1 is None:
            return

        def find_anchor():
            for attr in ('note_separate_bgm', 'switch_separate_bgm', 'switch_flip_video'):
                widget = getattr(home_interface, attr, None)
                if widget is None:
                    continue
                for i in range(col1.count()):
                    item = col1.itemAt(i)
                    if item is None:
                        continue
                    if item.widget() is widget:
                        return i
                    sub = item.layout()
                    if sub is not None:
                        for j in range(sub.count()):
                            if sub.itemAt(j) is not None and sub.itemAt(j).widget() is widget:
                                return i
            return None

        def make_row(label_text, tooltip, config_key):
            row = QHBoxLayout()
            label = BodyLabel(label_text)
            label.setToolTip(tooltip)
            switch = SwitchButton()
            try:
                switch.setOnText('Bật')
                switch.setOffText('Tắt')
            except Exception:
                pass
            switch.setToolTip(tooltip)
            switch.setChecked(bool(get_config(config_key, False)))

            def _on_toggle(checked):
                set_config(config_key, bool(checked))

            switch.checkedChanged.connect(_on_toggle)
            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(switch)
            return row, switch

        row_dual, switch_dual = make_row(
            'Kèm phụ đề gốc (song ngữ):',
            'Khi Bật: video xuất sẽ hiển thị thêm phụ đề ngôn ngữ gốc phía trên phụ đề Việt (cần đã Bóc băng).',
            'dual_subtitle')
        row_voice, switch_voice = make_row(
            'Dùng giọng gốc (bỏ TTS):',
            'Khi Bật: bỏ qua bước tạo giọng đọc AI; video xuất giữ nguyên giọng/âm thanh gốc. Bước "Tạo voice" chỉ trích xuất âm thanh gốc (nhanh).',
            'use_original_voice')

        anchor = find_anchor()
        pos = (anchor + 1) if anchor is not None else col1.count()
        col1.insertLayout(pos, row_dual)
        col1.insertLayout(pos + 1, row_voice)
        home_interface.switch_dual_subtitle = switch_dual
        home_interface.switch_use_original_voice = switch_voice
        home_interface._lua_ov_ui_ready = True
        _voice_log('Original-voice / dual-subtitle switches added to Home panel')
    except Exception as exc:
        _voice_log('setup_original_voice_dual_sub_ui failed: %r' % (exc,))


def install_original_voice_dual_sub_patch():
    global OV_DUAL_PATCH_INSTALLED
    if OV_DUAL_PATCH_INSTALLED:
        return
    try:
        from PyQt6.QtCore import QThread, pyqtSignal
        from app.views.home_interface import HomeInterface, get_safe_basename
        import app.common.workers as workers
        from qfluentwidgets import InfoBar, InfoBarPosition

        class LuaOriginalVoiceWorker(QThread):
            """Drop-in replacement for VoiceWorker in original-voice mode."""
            progress = pyqtSignal(int)
            log = pyqtSignal(str, bool)
            finished = pyqtSignal(str)
            error = pyqtSignal(str)

            def __init__(self, video_path, workspace_dir, parent=None):
                super().__init__(parent)
                self.video_path = str(video_path)
                self.workspace_dir = str(workspace_dir)
                self._cancelled = threading.Event()

            def cancel(self):
                self._cancelled.set()

            def run(self):
                try:
                    if self._cancelled.is_set():
                        return
                    self.log.emit('Chế độ Dùng giọng gốc: bỏ qua tạo giọng AI, trích xuất âm thanh gốc...', False)
                    self.progress.emit(15)
                    pcm_path = os.path.join(self.workspace_dir, 'Data', 'temp_audio_tong.pcm')
                    _lua_extract_original_pcm(self.video_path, pcm_path)
                    if self._cancelled.is_set():
                        return
                    self.progress.emit(95)
                    self.log.emit('Đã dùng lại âm thanh gốc của video.', False)
                    self.progress.emit(100)
                    self.finished.emit(pcm_path)
                except Exception as exc:
                    _voice_log('original-voice worker failed: %r' % (exc,))
                    try:
                        self.error.emit(str(exc))
                    except Exception:
                        pass

        # --- 1. Manual "3. Tạo voice" click in original-voice mode --------------
        orig_on_voice_clicked = HomeInterface._onVoiceClicked

        def lua_on_voice_clicked(self):
            if not use_original_voice_on():
                return orig_on_voice_clicked(self)
            self._verify_license_sync()
            if not getattr(self, 'selected_videos', None):
                InfoBar.warning(title='Cảnh báo', content='Vui lòng chọn video đầu vào trước!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return
            output_dir = self.line_output_path.text()
            if not output_dir:
                InfoBar.warning(title='Cảnh báo', content='Vui lòng chọn Đường dẫn lưu file trước!', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return
            current_idx = self.video_combo.currentIndex()
            if current_idx < 0 or current_idx >= len(self.selected_videos):
                return
            video_path = self.selected_videos[current_idx]
            workspace_dir = os.path.join(output_dir, get_safe_basename(video_path))
            data_dir = os.path.join(workspace_dir, 'Data')
            srt_path = os.path.join(data_dir, 'temp_translated.srt')
            if not os.path.exists(srt_path):
                srt_path = os.path.join(data_dir, 'temp_original.srt')
            if not os.path.exists(srt_path):
                InfoBar.error(title='Lỗi', content='Không tìm thấy file kịch bản (gốc hoặc dịch)! Vui lòng Bóc băng trước.', parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                return
            self.media_player.pause()
            self._setButtonsEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.progress_bar.setValue(0)
            self.voice_worker = LuaOriginalVoiceWorker(video_path, workspace_dir, parent=self)
            self.voice_worker.progress.connect(self.progress_bar.setValue)
            self.voice_worker.log.connect(self._appendLog)
            self.voice_worker.finished.connect(self._onVoiceFinished)
            self.voice_worker.error.connect(self._onTranscribeError)
            self.voice_worker.start()

        HomeInterface._onVoiceClicked = lua_on_voice_clicked

        # --- 2. Auto pipeline: swap VoiceWorker.run ------------------------------
        if not getattr(workers.VoiceWorker.run, '_lua_ov_wrap', False):
            orig_vw_run = workers.VoiceWorker.run

            def lua_vw_run(self):
                if not use_original_voice_on():
                    return orig_vw_run(self)
                video_path = None
                try:
                    parent = self.parent()
                    combo = getattr(parent, 'video_combo', None)
                    videos = getattr(parent, 'selected_videos', None)
                    if combo is not None and videos:
                        idx = combo.currentIndex()
                        if 0 <= idx < len(videos):
                            video_path = videos[idx]
                except Exception:
                    video_path = None
                workspace_dir = str(getattr(self, 'workspace_dir', '') or '')
                try:
                    if not video_path:
                        raise RuntimeError('Không xác định được video nguồn để trích xuất âm thanh gốc.')
                    self.log.emit('Chế độ Dùng giọng gốc: bỏ qua tạo giọng AI, trích xuất âm thanh gốc...', False)
                    self.progress.emit(15)
                    pcm_path = os.path.join(workspace_dir, 'Data', 'temp_audio_tong.pcm')
                    _lua_extract_original_pcm(video_path, pcm_path)
                    self.progress.emit(95)
                    self.log.emit('Đã dùng lại âm thanh gốc của video.', False)
                    self.progress.emit(100)
                    self.finished.emit(pcm_path)
                except Exception as exc:
                    _voice_log('original-voice VoiceWorker swap failed: %r' % (exc,))
                    try:
                        self.error.emit(str(exc))
                    except Exception:
                        pass

            lua_vw_run._lua_ov_wrap = True
            workers.VoiceWorker.run = lua_vw_run

        # --- 3. Render click: robust validation, auto-heal & diagnostics ---
        orig_on_render_clicked = HomeInterface._onRenderClicked

        def lua_on_render_clicked(self, *args, **kwargs):
            _voice_log('=== Nút 4. Render được bấm ===')
            # 0. Dọn dẹp worker cũ nếu còn sót lại và đảm bảo nút bấm được kích hoạt
            try:
                if hasattr(self, 'render_worker') and self.render_worker is not None:
                    if not self.render_worker.isRunning():
                        self.render_worker = None
                    else:
                        _voice_log('Phát hiện render_worker cũ vẫn còn, đang dừng...')
                        try:
                            if hasattr(self.render_worker, 'cancel'):
                                self.render_worker.cancel()
                            self.render_worker.wait(300)
                            if self.render_worker.isRunning():
                                self.render_worker.terminate()
                        except Exception:
                            pass
                        self.render_worker = None
                self._setButtonsEnabled(True)
                if hasattr(self, 'btn_step4') and self.btn_step4:
                    self.btn_step4.setEnabled(True)
            except Exception as e_clean:
                _voice_log('lua_on_render_clicked cleanup error: %r' % (e_clean,))

            try:
                from app.common.config_manager import get_config
                from qfluentwidgets import InfoBar, InfoBarPosition

                # 1. Kiểm tra video đã chọn
                videos = getattr(self, 'selected_videos', None)
                if not videos:
                    msg = 'Vui lòng chọn video đầu vào trước (bấm nút "Chọn video")!'
                    _voice_log('Render bị chặn: chưa chọn video')
                    self._appendLog('[Lỗi] ' + msg)
                    InfoBar.warning(title='Cảnh báo', content=msg, parent=self.window(), position=InfoBarPosition.TOP, duration=6000)
                    return

                # 2. Kiểm tra combo box video & auto-fix nếu currentIndex < 0
                combo = getattr(self, 'video_combo', None)
                if combo is not None:
                    if combo.currentIndex() < 0 and len(videos) > 0:
                        _voice_log('Tự động chọn video đầu tiên (currentIndex=-1 -> 0)')
                        combo.setCurrentIndex(0)

                idx = combo.currentIndex() if combo is not None else 0
                if idx < 0 or idx >= len(videos):
                    idx = 0
                    if combo is not None:
                        combo.setCurrentIndex(0)

                video_path = videos[idx]
                _voice_log('Video đang chọn: %s' % (video_path,))

                # 3. Kiểm tra đường dẫn lưu file
                output_dir = ''
                if hasattr(self, 'line_output_path'):
                    output_dir = self.line_output_path.text().strip()
                if not output_dir:
                    output_dir = get_config('output_dir', '')
                    if not output_dir or not os.path.isdir(output_dir):
                        output_dir = os.path.dirname(os.path.abspath(video_path))
                    if hasattr(self, 'line_output_path'):
                        self.line_output_path.setText(output_dir)
                    _voice_log('Tự động điền output_dir: %s' % (output_dir,))

                # 4. Xác định workspace_dir và tự động đồng bộ Data nếu tên video có đuôi (1), (2)...
                base_name = get_safe_basename(video_path)
                workspace_dir = os.path.join(output_dir, base_name)
                data_dir = os.path.join(workspace_dir, 'Data')
                os.makedirs(data_dir, exist_ok=True)

                srt_trans = os.path.join(data_dir, 'temp_translated.srt')
                srt_orig = os.path.join(data_dir, 'temp_original.srt')
                if not (os.path.isfile(srt_trans) or os.path.isfile(srt_orig)):
                    # Thử tìm folder tương đương (ví dụ bỏ đuôi " (1)")
                    alt_base = re.sub(r'\s*\(\d+\)$', '', base_name)
                    alt_data = os.path.join(output_dir, alt_base, 'Data')
                    if os.path.isdir(alt_data):
                        alt_trans = os.path.join(alt_data, 'temp_translated.srt')
                        alt_orig = os.path.join(alt_data, 'temp_original.srt')
                        if os.path.isfile(alt_trans) or os.path.isfile(alt_orig):
                            _voice_log('Đồng bộ file từ workspace: %s' % (alt_base,))
                            import shutil
                            for fn in os.listdir(alt_data):
                                sf = os.path.join(alt_data, fn)
                                df = os.path.join(data_dir, fn)
                                if os.path.isfile(sf) and not os.path.isfile(df):
                                    try:
                                        shutil.copy2(sf, df)
                                    except Exception:
                                        pass

                # 5. Kiểm tra file phụ đề
                srt_trans = os.path.join(data_dir, 'temp_translated.srt')
                srt_orig = os.path.join(data_dir, 'temp_original.srt')
                if not (os.path.isfile(srt_trans) or os.path.isfile(srt_orig)):
                    msg = 'Không tìm thấy file phụ đề! Vui lòng chạy "1. Bóc băng" (và "2. Dịch") trước.'
                    _voice_log('Render bị chặn: Không tìm thấy phụ đề trong %s' % (data_dir,))
                    self._appendLog('[Lỗi] ' + msg)
                    InfoBar.error(title='Lỗi phụ đề', content=msg, parent=self.window(), position=InfoBarPosition.TOP, duration=7000)
                    return

                # 6. Kiểm tra file audio lồng tiếng (temp_audio_tong.pcm)
                pcm_path = os.path.join(data_dir, 'temp_audio_tong.pcm')
                has_pcm = os.path.isfile(pcm_path) and os.path.getsize(pcm_path) > 44
                if not has_pcm:
                    # Nếu chưa có file voice (người dùng chưa chạy Bước 3 hoặc chỉ muốn xuất video phụ đề):
                    # Tự động trích xuất âm thanh gốc từ video để render không bị lỗi thiếu audio!
                    _voice_log('Chưa có temp_audio_tong.pcm; tự động chuẩn bị audio từ video gốc...')
                    try:
                        _lua_ensure_original_pcm_for_render(video_path, workspace_dir, None, pcm_path)
                        _voice_log('Đã tạo audio track gốc thành công: %s' % (pcm_path,))
                    except Exception as e_pcm:
                        _voice_log('Không thể trích xuất audio gốc (%r); tạo silence...' % (e_pcm,))
                        with open(pcm_path, 'wb') as fh:
                            fh.write(b'\x00' * 88200)

                _voice_log('Toàn bộ điều kiện tiên quyết hợp lệ, chuyển tiếp tới orig_on_render_clicked...')
            except Exception as e_pre:
                _voice_log('lua_on_render_clicked pre-hook gặp lỗi: %r\n%s' % (e_pre, traceback.format_exc()))

            try:
                res = orig_on_render_clicked(self, *args, **kwargs)
                _voice_log('orig_on_render_clicked đã hoàn tất gọi start()')
                return res
            except Exception as exc:
                _voice_log('NGOẠI LỆ NGHIÊM TRỌNG trong orig_on_render_clicked: %r\n%s' % (exc, traceback.format_exc()))
                self._appendLog('[Lỗi Render] %s' % (exc,))
                try:
                    self._setButtonsEnabled(True)
                except Exception:
                    pass
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.error(title='Lỗi khởi động Render', content=str(exc), parent=self.window(), position=InfoBarPosition.TOP, duration=7000)

        HomeInterface._onRenderClicked = lua_on_render_clicked

        # --- 4. Cancel click: immediately kill processes & re-enable all buttons ---
        orig_hi_on_cancel = getattr(HomeInterface, "_onCancelClicked", None)
        def lua_on_cancel_clicked(self, *args, **kwargs):
            _voice_log("=== Nút Hủy / Dừng lại được bấm ===")
            self.is_full_run = False
            if hasattr(self, 'is_batch_rendering'):
                self.is_batch_rendering = False
            self._appendLog("Đang dừng toàn bộ tiến trình...")

            for worker_name in ('transcribe_worker', 'translate_worker', 'voice_worker', 'render_worker', 'preview_worker'):
                worker = getattr(self, worker_name, None)
                if worker is not None:
                    try:
                        if hasattr(worker, 'cancel'):
                            worker.cancel()
                        if hasattr(worker, 'cancel_event'):
                            worker.cancel_event.set()
                        if hasattr(worker, 'isRunning') and worker.isRunning():
                            if hasattr(worker, 'wait'):
                                worker.wait(300)
                            if hasattr(worker, 'terminate') and worker.isRunning():
                                worker.terminate()
                                worker.wait(200)
                    except Exception as e_w:
                        _voice_log(f"Cancel worker {worker_name} error: {e_w}")
                    setattr(self, worker_name, None)

            try:
                subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass

            try:
                self._setButtonsEnabled(True)
            except Exception:
                pass

            for btn_attr in ('btn_step1', 'btn_step2', 'btn_step3', 'btn_step4', 'btn_start_full', 'btn_import_video', 'btn_select_output', 'btn_toggle_ocr'):
                btn = getattr(self, btn_attr, None)
                if btn is not None:
                    try:
                        btn.setEnabled(True)
                    except Exception:
                        pass

            if hasattr(self, 'btn_cancel') and self.btn_cancel:
                self.btn_cancel.setEnabled(False)
                self.btn_cancel.setText('HỦY BỎ')
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setValue(0)

            self._appendLog("Đã dừng tiến trình hoàn tất. Nút Render và tất cả chức năng đã sẵn sàng để tiếp tục!")
            _voice_log("lua_on_cancel_clicked: hoàn tất dọn dẹp và kích hoạt lại toàn bộ nút bấm.")

        HomeInterface._onCancelClicked = lua_on_cancel_clicked

        # --- 5. Render finish hook: ensure clean worker state and button unlock ---
        orig_hi_on_render_finished = getattr(HomeInterface, "_onRenderFinished", None)
        def lua_on_render_finished(self, output_path, *args, **kwargs):
            _voice_log(f"lua_on_render_finished called with output_path={output_path}")
            self.render_worker = None
            if output_path == "CANCELLED" or output_path is None or (isinstance(output_path, str) and not os.path.exists(output_path) and ("dừng" in output_path.lower() or "cancel" in output_path.lower())):
                self.is_full_run = False
                if hasattr(self, 'is_batch_rendering'):
                    self.is_batch_rendering = False
                try:
                    self._setButtonsEnabled(True)
                except Exception:
                    pass
                for btn_attr in ('btn_step1', 'btn_step2', 'btn_step3', 'btn_step4', 'btn_start_full'):
                    btn = getattr(self, btn_attr, None)
                    if btn is not None:
                        try:
                            btn.setEnabled(True)
                        except Exception:
                            pass
                if hasattr(self, 'btn_cancel') and self.btn_cancel:
                    self.btn_cancel.setEnabled(False)
                    self.btn_cancel.setText('HỦY BỎ')
                self._appendLog("Tiến trình render đã dừng.")
                return
            try:
                if orig_hi_on_render_finished:
                    return orig_hi_on_render_finished(self, output_path, *args, **kwargs)
            finally:
                self.render_worker = None
                try:
                    self._setButtonsEnabled(True)
                except Exception:
                    pass
                if hasattr(self, 'btn_cancel') and self.btn_cancel:
                    self.btn_cancel.setEnabled(False)
                    self.btn_cancel.setText('HỦY BỎ')

        HomeInterface._onRenderFinished = lua_on_render_finished

        OV_DUAL_PATCH_INSTALLED = True
        _voice_log('Original-voice / dual-subtitle patch installed')
    except Exception as exc:
        _voice_log('install_original_voice_dual_sub_patch failed: %r' % (exc,))


DOUYIN_PATCH_INSTALLED = False


def install_douyin_downloader_patch():
    global DOUYIN_PATCH_INSTALLED
    if DOUYIN_PATCH_INSTALLED:
        return
    try:
        from app.views.douyin_interface import DouyinInterface
        from qfluentwidgets import InfoBar, InfoBarPosition

        def format_speed_str(text):
            if not text or 'Đang lấy dữ liệu' in text or 'Đang hoàn tất' in text:
                return text
            cleaned = re.sub(r'\]\[download\]/s|\]/s|/s/s|/s', '', text)
            m = re.search(r'Đang tải:\s*(\d+)%\s*•\s*Tốc độ:\s*([^•]+)•\s*Còn lại:\s*(.+)', cleaned)
            if m:
                pct = m.group(1)
                speed = m.group(2).strip()
                eta = m.group(3).strip()
                if speed and speed.lower() != 'unknown':
                    return f'Đang tải: {pct}% • Tốc độ: {speed}/s (16 luồng gộp) • Còn lại: {eta}'
                return f'Đang tải: {pct}% • Tốc độ: Đang tính... • Còn lại: {eta}'
            return cleaned

        orig_start_scan = getattr(DouyinInterface, 'start_scan', None)
        if orig_start_scan:
            def safe_start_scan(self):
                text = self.link_input.toPlainText().strip()
                douyin_cookie = self.douyin_cookie_input.text().strip()
                if ('douyin.com' in text or 'iesdouyin.com' in text) and not douyin_cookie:
                    InfoBar.warning(
                        'Lưu ý Cookie Douyin',
                        'Douyin yêu cầu File Cookie (.txt) để vượt qua lớp bảo mật ArgusSecurity. '
                        'Nếu gặp lỗi bỏ qua link, bạn hãy nạp file Cookie Douyin ở trên (bấm dấu "?" để xem hướng dẫn).',
                        parent=self.window(),
                        position=InfoBarPosition.TOP,
                        duration=8000
                    )
                return orig_start_scan(self)
            DouyinInterface.start_scan = safe_start_scan

        orig_on_scan_error = getattr(DouyinInterface, 'on_scan_error', None)
        if orig_on_scan_error:
            def safe_on_scan_error(self, err):
                text = self.link_input.toPlainText().strip()
                douyin_cookie = self.douyin_cookie_input.text().strip()
                if ('douyin.com' in text or 'iesdouyin.com' in text) and not douyin_cookie:
                    msg = (
                        f'{err}\n'
                        'LƯU Ý: Douyin chặn quét do chưa có Cookie trình duyệt (ArgusSecurityPlugin). '
                        'Vui lòng nạp file Cookie Douyin (.txt) ở ô bên trên (bấm "?" để xem cách lấy).'
                    )
                    self.btn_scan.setEnabled(True)
                    InfoBar.error('Lỗi Douyin: Cần Cookie', msg, parent=self.window(), position=InfoBarPosition.TOP, duration=10000)
                    self.status_label.setText(f'Lỗi: {msg}')
                    return
                return orig_on_scan_error(self, err)
            DouyinInterface.on_scan_error = safe_on_scan_error

        orig_start_download = getattr(DouyinInterface, 'start_download', None)
        if orig_start_download:
            def safe_start_download(self):
                ret = orig_start_download(self)
                if hasattr(self, 'downloader') and self.downloader:
                    try:
                        self.downloader.speed_info.disconnect()
                    except Exception:
                        pass
                    self.downloader.speed_info.connect(lambda s: self.speed_label.setText(format_speed_str(s)))
                return ret
            DouyinInterface.start_download = safe_start_download

        DOUYIN_PATCH_INSTALLED = True
        _voice_log('Douyin downloader 16-thread & cookie patch installed successfully')
    except Exception as exc:
        _voice_log(f'Douyin downloader patch error: {exc!r}')




