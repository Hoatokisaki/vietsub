import sys
import os
os.environ['OMP_NUM_THREADS'] = '1'
import cv2
import json
import difflib
import datetime
import re
import gc
import numpy as np
import traceback
try:
    import paddle
except ImportError:
    paddle = None
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.common.config_manager import get_config, get_cpu_threads

def is_valid_text_for_lang(text, lang_var):
    text = text.strip()
    if not text:
        return False
    if re.fullmatch('[\\d\\W_]+', text):
        return False
    if lang_var == 'ch':
        if not re.search('[\\u4e00-\\u9fff]', text):
            return False
        return True
    if lang_var == 'japan':
        if not re.search('[\\u3040-\\u309f\\u30a0-\\u30ff\\u4e00-\\u9fff]', text):
            return False
        return True
    if lang_var == 'korean':
        if not re.search('[\\uac00-\\ud7a3]', text):
            return False
        return True
    if lang_var in ('vi', 'en'):
        if not re.search('[a-zA-Z\\u00C0-\\u024F\\u1E00-\\u1EFF]', text):
            return False
        if re.search('[\\u4e00-\\u9fff\\u3040-\\u309f\\u30a0-\\u30ff\\uac00-\\ud7a3]', text):
            return False
    return True

def is_same_subtitle(text_a, text_b, overlap_threshold=0.5):
    a = text_a.replace(' ', '')
    b = text_b.replace(' ', '')
    if not a or not b:
        return False
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer:
        return True
    matcher = difflib.SequenceMatcher(None, a, b)
    return matcher.ratio() >= overlap_threshold

def extract_white_outline_text(roi_img):
    if len(roi_img.shape) == 3:
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = roi_img
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return processed

def sort_ocr_boxes_reading_order(results):
    '''Sắp xếp box OCR theo thứ tự đọc: trên→dưới (theo dòng), trái→phải (trong dòng)'''

    if not results or len(results) <= 1:
        return results
    items = []
    for res in results:
        bbox = res[0]
        ys = [p[1] for p in bbox]
        min_y, max_y = min(ys), max(ys)
        center_y = (min_y + max_y) / 2.0
        h = max(1.0, max_y - min_y)
        items.append({'res': res, 'min_y': min_y, 'max_y': max_y, 'center_y': center_y, 'h': h})
    items.sort(key=(lambda it: it['center_y']))
    lines = []
    for it in items:
        matched_line = None
        for line in lines:
            line_min_y = min((b['min_y'] for b in line))
            line_max_y = max((b['max_y'] for b in line))
            overlap_y = max(0.0, min(it['max_y'], line_max_y) - max(it['min_y'], line_min_y))
            if overlap_y >= 0.4 * min(it['h'], max(1.0, line_max_y - line_min_y)):
                matched_line = line
                break
        if matched_line is not None:
            matched_line.append(it)
        else:
            lines.append([it])
    lines.sort(key=(lambda line: sum((b['center_y'] for b in line)) / len(line)))
    ordered = []
    for line in lines:
        line_results = [b['res'] for b in line]
        line_results.sort(key=(lambda item: min((p[0] for p in item[0]))))
        ordered.extend(line_results)
    return ordered

def write_json(subs, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(subs, f, ensure_ascii=False)

class FFmpegCapture:
    '''Drop-in thay cv2.VideoCapture, dung FFmpeg pipe de doc moi codec'''

    def __init__(self, video_path):
        ffmpeg_path = ''
        dev_ffmpeg = 'D:\\APP\\FFmpeg\\ffmpeg\\bin\\ffmpeg.exe'
        if os.path.exists(dev_ffmpeg):
            ffmpeg_path = dev_ffmpeg
        elif hasattr(sys, '_MEIPASS'):
            packaged_ffmpeg = os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg.exe')
            if os.path.exists(packaged_ffmpeg):
                ffmpeg_path = packaged_ffmpeg
        if ffmpeg_path:
            os.environ['IMAGEIO_FFMPEG_EXE'] = ffmpeg_path
        import imageio_ffmpeg
        self._path = video_path
        temp_cap = cv2.VideoCapture(video_path)
        self._fps = temp_cap.get(cv2.CAP_PROP_FPS)
        self._width = int(temp_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(temp_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._total_frames = int(temp_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        temp_cap.release()
        if self._fps <= 0:
            self._fps = 30.0
        self._gen = imageio_ffmpeg.read_frames(video_path, pix_fmt='bgr24')
        self._meta = next(self._gen)
        if self._width <= 0 or self._height <= 0:
            self._width, self._height = self._meta['size']
        if self._total_frames <= 0:
            duration = self._meta.get('duration', 0)
            if duration > 0:
                self._total_frames = int(duration * self._fps)

    def isOpened(self):
        return True

    def read(self):
        try:
            raw = next(self._gen)
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((self._height, self._width, 3))
            return True, frame
        except StopIteration:
            return (False, None)

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self._fps
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self._width
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self._height
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            return self._total_frames
        return 0

    def set(self, prop, val):
        pass

    def release(self):
        if hasattr(self._gen, 'close'):
            self._gen.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
    config_path = sys.argv[1]
    with open(config_path, 'r', encoding='utf-8') as f:
        params = json.load(f)
    video_path = params['video_path']
    lang_var = params['lang_var']
    arg_ocr_bbox = params.get('arg_ocr_bbox')
    output_srt = params['output_srt']
    ocr_engine_type = params.get('ocr_engine', 'paddle')
    try:
        import site
        search_paths = []
        if hasattr(sys, '_MEIPASS'):
            search_paths.append(sys._MEIPASS)
        if hasattr(site, 'getsitepackages'):
            search_paths.extend(site.getsitepackages())
        for p in search_paths:
            cublas_path = os.path.join(p, 'nvidia', 'cublas', 'bin')
            cudnn_path = os.path.join(p, 'nvidia', 'cudnn', 'bin')
            torch_lib_path = os.path.join(p, 'torch', 'lib')
            for dll_path in cublas_path, cudnn_path, torch_lib_path:
                if os.path.exists(dll_path):
                    if hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(dll_path)
                    os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')
    except:
        pass
    use_rapid = ocr_engine_type == 'rapid'
    current_use_gpu = False
    if use_rapid:
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()
        except BaseException as e:
            print(f'ERROR: Loi khoi tao loi doc chu on dinh: {e}', flush=True)
            sys.exit(1)
    else:
        try:
            from app.common.config_manager import get_paddleocr_cache_dir
            paddle_cache_dir = get_paddleocr_cache_dir()
            os.environ['USERPROFILE'] = paddle_cache_dir
            os.environ['HOME'] = paddle_cache_dir
            from paddleocr import PaddleOCR
        except BaseException as e:
            print('ERROR: Loi khoi tao loi boc chu', flush=True)
            sys.exit(1)
        import subprocess
        has_gpu = False
        try:
            out = subprocess.check_output(['nvidia-smi'], creationflags=subprocess.CREATE_NO_WINDOW)
            has_gpu = True
        except:
            pass
        optimal_threads = get_cpu_threads()
        current_use_gpu = has_gpu
        try:
            ocr = PaddleOCR(lang=lang_var, use_gpu=has_gpu, show_log=False, cpu_threads=optimal_threads)
        except Exception as e:
            err_msg = str(e).lower()
            if 'cudnn' in err_msg or 'cublas' in err_msg or 'cuda' in err_msg or 'memory' in err_msg:
                print('ERROR: Tran VRAM hoac Card khong ho tro. Dang chay bang CPU (cham hon GPU)...', flush=True)
                ocr = PaddleOCR(lang=lang_var, use_gpu=False, show_log=False, cpu_threads=optimal_threads)
                current_use_gpu = False
            else:
                print(f'ERROR: {str(e)}', flush=True)
                sys.exit(1)
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'hwaccel;none'
    os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
    params = []
    if hasattr(cv2, 'CAP_PROP_HW_ACCELERATION') and hasattr(cv2, 'VIDEO_ACCELERATION_NONE'):
        params.extend([cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE])
    def _get_safe_path(p):
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(p, buf, 1024):
                if buf.value:
                    return buf.value
                return p
        except:
            pass
        return p

    safe_video_path = _get_safe_path(video_path)
    if params:
        cap = cv2.VideoCapture(safe_video_path, cv2.CAP_FFMPEG, params)
    else:
        cap = cv2.VideoCapture(safe_video_path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap = cv2.VideoCapture(safe_video_path)
    _test_ok = False
    if cap.isOpened():
        _test_ok, _ = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    if not cap.isOpened() or not _test_ok:
        cap.release()
        print('AV1_FIX: OpenCV that bai. Chuyen sang FFmpeg stream...', flush=True)
        cap = FFmpegCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration_sec = total_frames / fps
    ocr_fps = get_config('ocr_fps', 10)
    if ocr_fps <= 0:
        ocr_fps = 10
    skip_frames = max(1, int(fps / ocr_fps))
    if arg_ocr_bbox:
        if len(arg_ocr_bbox) == 4 and (isinstance(arg_ocr_bbox[0], int) or arg_ocr_bbox[0] > 1.0):
            x, y, w_roi, h_roi = arg_ocr_bbox
        else:
            x_rel, y_rel, w_rel, h_rel = arg_ocr_bbox
            frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            x = int(x_rel * frame_w)
            y = int(y_rel * frame_h)
            w_roi = int(w_rel * frame_w)
            h_roi = int(h_rel * frame_h)
    else:
        glob_bbox = get_config('abs_ocr_bbox')
        if glob_bbox and len(glob_bbox) == 4:
            x, y, w_roi, h_roi = glob_bbox
        else:
            print('ERROR: Chua khoanh vung chu.', flush=True)
            sys.exit(1)
    ocr_preprocess = get_config('ocr_preprocess', False)
    conf_thresh = get_config('ocr_conf_thresh', 0) / 100.0
    subs = []
    frame_count = 0
    current_sub = ''
    start_time = None
    end_time = None
    debug_frame_saved = False
    diag_frames_processed = 0
    diag_ocr_has_result = 0
    diag_ocr_exception = 0
    diag_first_ocr_err = ''
    diag_pass_conf = 0
    diag_pass_lang = 0
    diag_lang_fallback = 0
    diag_pass_angle = 0
    diag_pass_height = 0
    diag_has_text = 0
    def commit_sub(sub_start, sub_end, sub_txt):
        if not sub_txt:
            return
        if len(subs) > 0:
            last_start, last_end, last_txt = subs[-1]
            clean_sub = sub_txt.replace(' ', '')
            clean_last = last_txt.replace(' ', '')
            is_same = is_same_subtitle(clean_sub, clean_last, overlap_threshold=0.8)
            if is_same and sub_start - last_end <= 1.5:
                new_text = last_txt if len(clean_last) > len(clean_sub) else sub_txt
                subs[-1] = last_start, max(last_end, sub_end), new_text
                return
        subs.append((sub_start, sub_end, sub_txt))

    if hasattr(cap, '_gen'):
        all_black = False
    else:
        sample_positions = [0.1, 0.25, 0.5, 0.75, 0.9]
        all_black = True
        for pos in sample_positions:
            target_frame = int(total_frames * pos)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret_check, frame_check = cap.read()
            if ret_check and frame_check is not None and np.mean(frame_check) > 1.0:
                all_black = False
                break
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    if all_black and total_frames > 0:
        print('WARNING: Tat ca khung hinh deu bi den. Neu ket qua boc chu ra 0, vui long cap nhat Driver VGA.', flush=True)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % skip_frames != 0:
            frame_count += 1
            continue
        time_sec = frame_count / fps
        progress = time_sec / max(1, video_duration_sec)
        if diag_frames_processed > 0 and diag_frames_processed % 200 == 0:
            gc.collect()
            if current_use_gpu and not use_rapid:
                try:
                    paddle.device.cuda.empty_cache()
                except:
                    pass
        if frame_count % (skip_frames * 5) == 0:
            print(f'PROGRESS:{int(progress * 100)}', flush=True)
        safe_x = max(0, x)
        safe_y = max(0, y)
        safe_w = min(frame.shape[1] - safe_x, w_roi)
        safe_h = min(frame.shape[0] - safe_y, h_roi)
        if not safe_w <= 0:
            if safe_h <= 0:
                frame_count += 1
                continue
        roi_img = frame[safe_y:safe_y + safe_h, safe_x:safe_x + safe_w]
        diag_frames_processed += 1
        if not debug_frame_saved:
            debug_full = frame.copy()
            cv2.rectangle(debug_full, (safe_x, safe_y), (safe_x + safe_w, safe_y + safe_h), (0, 255, 0), 3)
            cv2.putText(debug_full, f'OCR ROI ({safe_w}x{safe_h})', (safe_x, max(safe_y - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            debug_img_path = os.path.join(os.path.dirname(output_srt), 'debug_khung_cat.jpg')
            cv2.imwrite(debug_img_path, debug_full)
            debug_frame_saved = True
        ocr_input = extract_white_outline_text(roi_img) if ocr_preprocess else roi_img
        h_in, w_in = ocr_input.shape[:2]
        scale_factor = 1.0
        if h_in < 300 and current_use_gpu and not use_rapid:
            scale_factor = 2.0
            ocr_input = cv2.resize(ocr_input, (int(w_in * scale_factor), int(h_in * scale_factor)), interpolation=cv2.INTER_CUBIC)
        try:
            if use_rapid:
                results_raw, _ = ocr(ocr_input)
            else:
                results_raw = ocr.ocr(ocr_input, cls=False)
        except Exception as e:
            if not use_rapid:
                if current_use_gpu:
                    ocr = PaddleOCR(lang=lang_var, use_gpu=False, show_log=False, cpu_threads=get_cpu_threads())
                    current_use_gpu = False
                    ocr_input = extract_white_outline_text(roi_img) if ocr_preprocess else roi_img
                    scale_factor = 1.0
                    try:
                        results_raw = ocr.ocr(ocr_input, cls=False)
                    except Exception as e_cpu:
                        diag_ocr_exception += 1
                        if not diag_first_ocr_err:
                            diag_first_ocr_err = str(e_cpu)[:200]
                        frame_count += 1
                        e = None
                        del e
                else:
                    diag_ocr_exception += 1
                    if not diag_first_ocr_err:
                        diag_first_ocr_err = str(e)[:200]
                    frame_count += 1
            else:
                diag_ocr_exception += 1
                if not diag_first_ocr_err:
                    diag_first_ocr_err = str(e)[:200]
                frame_count += 1
        valid_results = []
        raw_boxes = []
        has_data = False
        if use_rapid:
            if results_raw:
                has_data = True
                diag_ocr_has_result += 1
                for line in results_raw:
                    box = line[0]
                    text_str = line[1]
                    conf = float(line[2])
                    if scale_factor > 1.0:
                        box = [[p[0] / scale_factor, p[1] / scale_factor] for p in box]
                    if conf >= conf_thresh:
                        raw_boxes.append((box, text_str))
                        diag_pass_conf += 1
        elif results_raw and results_raw[0]:
            has_data = True
            diag_ocr_has_result += 1
            for line in results_raw[0]:
                box = line[0]
                text_str = line[1][0]
                conf = line[1][1]
                if scale_factor > 1.0:
                    box = [[p[0] / scale_factor, p[1] / scale_factor] for p in box]
                if conf >= conf_thresh:
                    raw_boxes.append((box, text_str))
                    diag_pass_conf += 1
        lang_filtered = []
        for i, (box, text_str) in enumerate(raw_boxes):
            if is_valid_text_for_lang(text_str, lang_var):
                lang_filtered.append((box, text_str))
                diag_pass_lang += 1
            else:
                ys = [p[1] for p in box]
                min_y1, max_y1 = min(ys), max(ys)
                is_same_line = False
                for other_box, other_text in raw_boxes:
                    if id(box) != id(other_box) and is_valid_text_for_lang(other_text, lang_var):
                        other_ys = [p[1] for p in other_box]
                        min_y2, max_y2 = min(other_ys), max(other_ys)
                        if max(min_y1, min_y2) < min(max_y1, max_y2):
                            is_same_line = True
                            break
                if is_same_line:
                    lang_filtered.append((box, text_str))
        if lang_filtered:
            valid_results = lang_filtered
        elif raw_boxes:
            valid_results = raw_boxes
            diag_lang_fallback += 1
        if valid_results:
            filtered_by_angle = []
            for res in valid_results:
                bbox = res[0]
                dy = abs(bbox[1][1] - bbox[0][1])
                dx = max(1, abs(bbox[1][0] - bbox[0][0]))
                if dy / dx <= 0.2:
                    filtered_by_angle.append(res)
                    diag_pass_angle += 1
            if filtered_by_angle:
                valid_results = filtered_by_angle
        if valid_results:
            final_valid = []
            for res in valid_results:
                bbox = res[0]
                ys = [p[1] for p in bbox]
                box_h = max(ys) - min(ys)
                if box_h >= h_roi * 0.2:
                    final_valid.append(res)
                    diag_pass_height += 1
            if final_valid:
                valid_results = final_valid
        if valid_results:
            valid_results = sort_ocr_boxes_reading_order(valid_results)
        text_parts = []
        for res in valid_results:
            text_parts.append(res[1])
        combined_text = ' '.join(text_parts).strip()
        if combined_text:
            diag_has_text += 1
            if start_time is None:
                start_time = time_sec
                current_sub = combined_text
                end_time = time_sec
            else:
                is_same = is_same_subtitle(combined_text, current_sub)
                if is_same:
                    end_time = time_sec
                    if len(combined_text) > len(current_sub):
                        current_sub = combined_text
                else:
                    commit_sub(start_time, end_time, current_sub)
                    start_time = time_sec
                    current_sub = combined_text
                    end_time = time_sec
        elif start_time is not None and time_sec - end_time > 1.0:
            commit_sub(start_time, end_time, current_sub)
            start_time = None
            current_sub = ''
            end_time = None
        frame_count += 1
    if current_sub:
        commit_sub(start_time, end_time + skip_frames / fps, current_sub)
    cap.release()
    if len(subs) == 0:
        diag_msg = f'DIAG:lang={lang_var}|bbox=({x},{y},{w_roi},{h_roi})|frames={diag_frames_processed}|ocr_result={diag_ocr_has_result}|ocr_err={diag_ocr_exception}|pass_conf={diag_pass_conf}|pass_lang={diag_pass_lang}|lang_fallback={diag_lang_fallback}|pass_angle={diag_pass_angle}|pass_height={diag_pass_height}|has_text={diag_has_text}'
        if diag_first_ocr_err:
            diag_msg += f'|first_err={diag_first_ocr_err}'
        print(diag_msg, flush=True)
        print(f'ERROR: Khong tim thay phu de. {diag_msg}', flush=True)
        write_json([], output_srt)
        sys.exit(0)
    write_json(subs, output_srt)
    print('PROGRESS:100', flush=True)
    sys.exit(0)
