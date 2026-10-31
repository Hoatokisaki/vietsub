"""Custom OpenAI-compatible API Client and Subtitle Translation.

Supports any OpenAI-compatible provider:
- OpenAI (default if Base URL is empty)
- DeepSeek (https://api.deepseek.com)
- Groq (https://api.groq.com/openai/v1)
- OpenRouter (https://openrouter.ai/api/v1)
- Together AI, Mistral, Moonshot / Kimi, Qwen / Dashscope
- Ollama (http://localhost:11434/v1), LM Studio (http://localhost:1234/v1)
"""
import concurrent.futures
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    class QThread:
        def __init__(self, parent=None):
            self.parent = parent
        def start(self):
            self.run()
    def pyqtSignal(*args, **kwargs):
        class _Signal:
            def connect(self, fn):
                self.fn = fn
            def emit(self, *a, **k):
                if hasattr(self, "fn") and callable(self.fn):
                    self.fn(*a, **k)
        return _Signal()


# ==============================================================================
# Helper Functions: URL Normalization and Model Auto-Detection
# ==============================================================================

def normalize_base_url(url: str) -> str:
    """Normalizes an OpenAI-compatible Base URL."""
    url = (url or "").strip()
    if not url:
        return "https://api.openai.com/v1"
    url = url.rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[:-17].rstrip("/")

    lower = url.lower()
    # Handle known providers
    if lower.endswith(":11434") or ("ollama" in lower and not lower.endswith("/v1")):
        url = f"{url}/v1"
    elif "openai.com" in lower and not lower.endswith("/v1"):
        url = f"{url}/v1"
    elif "deepseek.com" in lower and not lower.endswith("/v1"):
        url = f"{url}/v1"
    elif "groq.com" in lower:
        if not lower.endswith("/v1"):
            if "openai" not in lower:
                url = f"{url}/openai/v1"
            else:
                url = f"{url}/v1"
    elif "openrouter.ai" in lower:
        if not lower.endswith("/v1"):
            if not lower.endswith("/api"):
                url = f"{url}/api/v1"
            else:
                url = f"{url}/v1"
    elif not re.search(r"/v\d+$", url):
        if "api" in lower or "localhost" in lower or "127.0.0.1" in lower:
            url = f"{url}/v1"
    return url


def auto_detect_model(base_url: str, custom_model: str = "") -> str:
    """Detects appropriate default model from Base URL if custom_model is not specified."""
    if custom_model and custom_model.strip() and custom_model.strip().lower() != "auto":
        return custom_model.strip()

    u = (base_url or "").lower()
    if "xkiro" in u:
        return "qwen/qwen3.7-flash:free"
    if "deepseek" in u:
        return "deepseek-chat"
    if "groq" in u:
        return "llama-3.3-70b-versatile"
    if "openrouter" in u:
        return "google/gemini-2.0-flash-001"
    if "together" in u:
        return "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    if "mistral" in u:
        return "mistral-small-latest"
    if "ollama" in u or "11434" in u:
        return "llama3.2"
    if "1234" in u or "lmstudio" in u:
        return "local-model"
    if "moonshot" in u or "kimi" in u:
        return "moonshot-v1-8k"
    if "qwen" in u or "dashscope" in u or "aliyun" in u:
        return "qwen-plus"
    if "siliconflow" in u:
        return "deepseek-ai/DeepSeek-V3"
    if "novita" in u:
        return "meta-llama/llama-3.1-70b-instruct"
    return "gpt-4o-mini"


def extract_api_keys(raw) -> list:
    """Extracts a clean list of API keys from string or list input."""
    if isinstance(raw, list):
        keys = []
        for item in raw:
            for k in str(item).splitlines():
                k = k.strip()
                if k and not k.startswith("#"):
                    keys.append(k)
        return keys
    if not raw:
        return []
    lines = [k.strip() for k in str(raw).splitlines() if k.strip() and not k.strip().startswith("#")]
    return lines


# ==============================================================================
# Custom API Client
# ==============================================================================

class CustomAPIClient:
    def __init__(self, base_url: str = "", api_keys=None, model: str = ""):
        self.base_url = normalize_base_url(base_url)
        self.api_keys = extract_api_keys(api_keys)
        self.model = auto_detect_model(self.base_url, model)
        self._key_index = 0
        try:
            self._ssl_ctx = ssl.create_default_context()
        except Exception:
            self._ssl_ctx = ssl._create_unverified_context()

    def _get_next_key(self) -> str:
        if not self.api_keys:
            return ""
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key

    def send_completion(self, messages: list, temperature: float = 0.3, max_tokens: int = 4096, cancel_event=None) -> str:
        endpoint = f"{self.base_url}/chat/completions"
        max_retries = max(8, len(self.api_keys) * 4)

        for attempt in range(max_retries):
            if cancel_event and cancel_event.is_set():
                return "CANCELLED"

            current_key = self._get_next_key()
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            if current_key:
                headers["Authorization"] = f"Bearer {current_key}"

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=45) as resp:
                    resp_data = resp.read().decode("utf-8")
                    parsed = json.loads(resp_data)
                    choices = parsed.get("choices", [])
                    if not choices:
                        raise ValueError(f"Không có trường 'choices' trong phản hồi API: {resp_data[:200]}")
                    msg_obj = choices[0].get("message", {})
                    content = msg_obj.get("content", "")
                    if content is None:
                        content = ""
                    return content
            except urllib.error.HTTPError as he:
                error_body = ""
                try:
                    error_body = he.read().decode("utf-8")
                    err_json = json.loads(error_body)
                    err_msg = err_json.get("error", {}).get("message", error_body)
                except Exception:
                    err_msg = error_body or str(he)

                if he.code == 401:
                    raise PermissionError(f"401 Unauthorized: API Key không chính xác hoặc đã hết hạn! Chi tiết: {err_msg}")
                elif he.code == 403:
                    if "premium model" in err_msg.lower() or "deposited" in err_msg.lower():
                        raise PermissionError(f"403 Forbidden: Model '{self.model}' yêu cầu tài khoản có số dư nạp thật (không hỗ trợ credits tặng/thử nghiệm). Vui lòng đổi Model sang model miễn phí (ví dụ: qwen/qwen3.7-flash:free) hoặc nạp tiền tài khoản.")
                    raise PermissionError(f"403 Forbidden (Bị từ chối truy cập): {err_msg}")
                elif he.code == 404:
                    raise FileNotFoundError(f"404 Not Found: Model '{self.model}' không tồn tại hoặc sai Base URL ({endpoint})! Chi tiết: {err_msg}")
                elif he.code == 402:
                    raise PermissionError(f"402 Payment Required: Tài khoản API hết số dư (Quota/Balance)! Chi tiết: {err_msg}")
                elif he.code == 429:
                    if attempt < max_retries - 1:
                        retry_after = he.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            sleep_time = min(float(retry_after) + 1.0, 30.0)
                        else:
                            sleep_time = min(2.5 * (attempt + 1) + random.uniform(0.5, 2.0), 20.0)
                        time.sleep(sleep_time)
                        continue
                    raise RuntimeError(f"Lỗi máy chủ API (429): {err_msg}")
                elif he.code in (500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        sleep_time = min(1.5 * (attempt + 1) + random.uniform(0.5, 1.5), 12.0)
                        time.sleep(sleep_time)
                        continue
                    raise RuntimeError(f"Lỗi máy chủ API ({he.code}): {err_msg}")
                else:
                    raise RuntimeError(f"Lỗi HTTP {he.code}: {err_msg}")
            except (urllib.error.URLError, TimeoutError) as ue:
                if attempt < max_retries - 1:
                    time.sleep(1.5)
                    continue
                raise ConnectionError(f"Không thể kết nối tới {endpoint}: {ue}")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1.0)
                    continue
                raise e

        raise RuntimeError("Đã hết số lần thử lại nhưng API vẫn không phản hồi.")


# ==============================================================================
# Custom API Connection Check Worker (QThread)
# ==============================================================================

class CustomAPICheckWorker(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, base_url: str, api_keys, model: str = "", parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.api_keys = api_keys
        self.model = model

    def run(self):
        try:
            norm_url = normalize_base_url(self.base_url)
            model_name = auto_detect_model(norm_url, self.model)
            keys = extract_api_keys(self.api_keys)

            # Local servers (Ollama / LM Studio) may not require an API key
            is_local = any(loc in norm_url.lower() for loc in ("localhost", "127.0.0.1", "11434", "1234"))
            if not keys and not is_local:
                self.result.emit(False, "Chưa nhập API Key! Vui lòng nhập API Key trước khi kiểm tra.")
                return

            client = CustomAPIClient(base_url=norm_url, api_keys=keys, model=model_name)
            reply = client.send_completion(
                messages=[{"role": "user", "content": "Hello, respond with OK"}],
                max_tokens=10,
                temperature=0.0
            )

            if reply and reply != "CANCELLED":
                clean_reply = reply.strip().replace("\n", " ")
                if len(clean_reply) > 30:
                    clean_reply = clean_reply[:30] + "..."
                self.result.emit(
                    True,
                    f"Kết nối thành công!\nBase URL: {norm_url}\nModel: {model_name}\nPhản hồi: \"{clean_reply}\""
                )
            else:
                self.result.emit(False, f"API kết nối được nhưng không trả về nội dung (Model: {model_name})")
        except Exception as exc:
            self.result.emit(False, str(exc))


# ==============================================================================
# SRT Subtitle Parsing & Formatting
# ==============================================================================

def parse_srt_subtitles(content: str) -> list:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", content.strip()) if b.strip()]
    stamp_re = re.compile(
        r"(\d{1,3}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,3}:\d{2}:\d{2}[,\.]\d{3})"
    )

    def parse_ms(stamp_str):
        stamp_str = stamp_str.replace(",", ".")
        h, m, s = stamp_str.split(":")
        return int(float(h) * 3600000 + float(m) * 60000 + float(s) * 1000)

    subs = []
    idx = 1
    for block in blocks:
        lines = block.splitlines()
        stamp_line_idx = -1
        for i, l in enumerate(lines):
            if stamp_re.search(l):
                stamp_line_idx = i
                break
        if stamp_line_idx == -1:
            continue
        m = stamp_re.search(lines[stamp_line_idx])
        start_ms = parse_ms(m.group(1))
        end_ms = parse_ms(m.group(2))
        text_lines = lines[stamp_line_idx + 1:]
        text = " ".join([t.strip() for t in text_lines if t.strip()])
        duration_s = max(0.1, (end_ms - start_ms) / 1000.0)

        subs.append({
            "index": idx,
            "start": m.group(1).replace(".", ","),
            "end": m.group(2).replace(".", ","),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration": duration_s,
            "text": text,
        })
        idx += 1
    return subs


def format_srt_content(subs: list) -> str:
    out = []
    for i, s in enumerate(subs, 1):
        out.append(f"{i}\n{s['start']} --> {s['end']}\n{s['text']}\n")
    return "\n".join(out)


def clean_translated_line(line: str) -> str:
    line = line.strip()
    # Strip timing prefix like [1.2s]
    line = re.sub(r"^\[\d+\.?\d*s\]\s*", "", line)
    # Strip line numbering like 1., 1 -, Câu 1:
    line = re.sub(r"^(?:Câu\s*)?\d+[\.|\:\-\)]+\s*", "", line)
    return line.strip()


# ==============================================================================
# Translation Logic
# ==============================================================================

def custom_api_translate_logic(
    srt_path: str,
    base_url: str,
    api_keys,
    model: str,
    status_cb: callable,
    cancel_event,
    workspace_dir: str,
    prompt_style: str = "Mặc định",
    custom_prompt_text: str = "",
    target_lang: str = "Tiếng Việt",
    **kwargs
) -> str:
    """Translates an SRT subtitle file using an OpenAI-compatible Custom API with high concurrency and error resume."""
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Không tìm thấy file kịch bản gốc: {srt_path}")

    norm_url = normalize_base_url(base_url)
    model_name = auto_detect_model(norm_url, model)
    keys = extract_api_keys(api_keys)

    is_local = any(loc in norm_url.lower() for loc in ("localhost", "127.0.0.1", "11434", "1234"))
    if not keys and not is_local:
        raise ValueError("Chưa cấu hình API Key! Vui lòng nhập API Key trong phần Cài đặt -> Custom API.")

    client = CustomAPIClient(base_url=norm_url, api_keys=keys, model=model_name)

    # Read SRT
    with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f:
        content = f.read()

    subtitles = parse_srt_subtitles(content)
    if not subtitles:
        raise ValueError("File SRT không có nội dung phụ đề hợp lệ để dịch!")

    total_subs = len(subtitles)

    from translation_checkpoint import TranslationProgressManager
    pm = TranslationProgressManager(workspace_dir, target_lang)
    translated_map, missing_indices = pm.load_progress(subtitles)

    if len(missing_indices) == 0:
        status_cb(f"Tất cả {total_subs} câu đã được dịch hoàn tất từ trước. Đang hoàn thiện file phụ đề...", 1.0)
        pm.mark_completed(subtitles)
        return pm.out_srt_file

    if len(translated_map) > 0:
        status_cb(
            f"[TIẾP TỤC DỊCH] Đã có {len(translated_map)}/{total_subs} câu. "
            f"Đang tiếp tục dịch {len(missing_indices)} câu còn lại bằng {model_name}...",
            0.05 + 0.90 * (len(translated_map) / total_subs)
        )
    else:
        status_cb(f"Khởi động dịch {total_subs} câu với {model_name}...", 0.05)

    rules_template = (
        "Bạn là chuyên gia dịch thuật phụ đề video phim ảnh chuyên nghiệp sang {target_lang}.\n"
        "Quy tắc bắt buộc:\n"
        "1. Dịch chính xác {num_lines} dòng phụ đề được cung cấp.\n"
        "2. Bản dịch phải tự nhiên, mượt mà, đúng ngữ cảnh văn phong điện ảnh.\n"
        "3. Kết quả đầu ra PHẢI gồm đúng {num_lines} dòng, mỗi dòng tương ứng với 1 dòng gốc.\n"
        "4. KHÔNG in lại mốc thời gian [..s].\n"
        "5. KHÔNG đánh số thứ tự đầu dòng, KHÔNG thêm lời giải thích hay markdown code fence."
    )

    style_prompt = ""
    if prompt_style == "Tùy chỉnh" and custom_prompt_text.strip():
        style_prompt = f"Yêu cầu phong cách bổ sung:\n{custom_prompt_text.strip()}\n"

    try:
        from translation_rules import rules_for_target_lang
        novel_translation_rules = rules_for_target_lang(target_lang)
    except Exception:
        novel_translation_rules = ""

    chunk_size = 35  # Optimized chunk size for custom APIs
    chunks = []
    curr_indices = []
    for idx in missing_indices:
        curr_indices.append(idx)
        if len(curr_indices) >= chunk_size:
            chunks.append(list(curr_indices))
            curr_indices = []
    if curr_indices:
        chunks.append(list(curr_indices))

    total_chunks = len(chunks)
    completed_subs = [len(translated_map)]
    last_error = [None]

    def _process_chunk(chunk_idx, chunk_indices):
        if cancel_event and cancel_event.is_set():
            return "CANCELLED"

        chunk = [subtitles[i] for i in chunk_indices]
        chunk_num_lines = len(chunk)
        chunk_lines = [f"[{s['duration']:.1f}s] {s['text']}" for s in chunk]
        chunk_input = "\n".join(chunk_lines)

        system_msg = rules_template.format(num_lines=chunk_num_lines, target_lang=target_lang)
        if style_prompt:
            system_msg += f"\n{style_prompt}"
        if novel_translation_rules:
            system_msg += f"\n\n{novel_translation_rules}"

        user_msg = (
            f"Hãy dịch đúng {chunk_num_lines} dòng dưới đây sang {target_lang}:\n"
            f"{chunk_input}"
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]

        try:
            resp = client.send_completion(messages, temperature=0.3, max_tokens=4096, cancel_event=cancel_event)
            if resp == "CANCELLED":
                return "CANCELLED"

            # Clean markdown code blocks if any
            resp = resp.strip()
            if resp.startswith("```"):
                resp = re.sub(r"^```[a-zA-Z]*\n", "", resp)
                resp = re.sub(r"\n```$", "", resp).strip()

            raw_lines = [clean_translated_line(l) for l in resp.splitlines() if l.strip()]

            # Align chunk lines to expected count
            aligned = []
            if len(raw_lines) == chunk_num_lines:
                aligned = raw_lines
            elif len(raw_lines) > chunk_num_lines:
                aligned = raw_lines[:chunk_num_lines - 1]
                aligned.append(" ".join(raw_lines[chunk_num_lines - 1:]))
            else:
                for k in range(chunk_num_lines):
                    if k < len(raw_lines):
                        aligned.append(raw_lines[k])
                    else:
                        aligned.append(chunk[k]["text"])

            # Save completed chunk immediately to progress file and SRT!
            pm.save_chunk(chunk_indices, aligned, subtitles)

            completed_subs[0] += chunk_num_lines
            pct = 0.05 + 0.90 * min(1.0, completed_subs[0] / max(1, total_subs))
            status_cb(f"Đang dịch bằng {model_name} ({completed_subs[0]}/{total_subs} câu)...", pct)
            return aligned
        except Exception as exc:
            last_error[0] = exc
            raise exc

    # Execute with ThreadPoolExecutor
    max_workers = 3 if total_chunks >= 3 else max(1, total_chunks)
    has_err = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_chunk, idx, c_indices): idx
            for idx, c_indices in enumerate(chunks)
        }
        for future in concurrent.futures.as_completed(futures):
            if cancel_event and cancel_event.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                return "CANCELLED"
            try:
                res = future.result()
                if res == "CANCELLED":
                    executor.shutdown(wait=False, cancel_futures=True)
                    return "CANCELLED"
            except Exception as exc:
                has_err = True
                executor.shutdown(wait=False, cancel_futures=True)
                break

    if has_err and last_error[0]:
        saved_count = len(pm.translations)
        err_msg = (
            f"[TẠM DỪNG DO LỖI] Đã lưu tiến trình dịch ({saved_count}/{total_subs} câu). "
            f"Lỗi: {last_error[0]}. "
            f"Khi khắc phục xong, bạn chỉ cần nhấn nút 'Tiếp tục dịch' để tiếp tục!"
        )
        status_cb(err_msg, 0.05 + 0.90 * (saved_count / max(1, total_subs)))
        raise RuntimeError(err_msg)

    # Finalize
    pm.mark_completed(subtitles)
    out_srt_path = pm.out_srt_file

    # Apply timing optimization if available
    try:
        from app.core.ai_translator import optimize_srt_timing
        optimize_srt_timing(out_srt_path)
    except Exception:
        pass

    # Clean any watermark from srt
    try:
        if os.path.exists(out_srt_path):
            from pathlib import Path
            raw = Path(out_srt_path).read_text(encoding="utf-8-sig")
            cleaned = re.sub(r'\[(sirvietsub|luavietsup)\]\s*', '', raw, flags=re.IGNORECASE)
            if cleaned != raw:
                Path(out_srt_path).write_text(cleaned, encoding="utf-8")
    except Exception:
        pass

    status_cb(f"Hoàn tất dịch bằng Custom API ({model_name})!", 1.0)
    return out_srt_path
