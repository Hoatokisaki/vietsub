"""ChatGPT Web Client and Subtitle Translation using browser session cookies.

Uses curl_cffi for browser TLS impersonation (bypassing Cloudflare/WAF)
and pure Python SHA3-512 Proof-of-Work solver for Sentinel challenges.
"""
import base64
import hashlib
import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    import requests as cffi_requests

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    QThread = object
    def pyqtSignal(*args, **kwargs):
        return None

# ==============================================================================
# Sentinel Proof-of-Work Solver
# ==============================================================================

CORES = [8, 16, 24, 32]
TIME_LAYOUT = "%a %b %d %Y %H:%M:%S"

NAVIGATOR_KEYS = [
    "registerProtocolHandler−function registerProtocolHandler() { [native code] }",
    "storage−[object StorageManager]",
    "locks−[object LockManager]",
    "appCodeName−Mozilla",
    "permissions−[object Permissions]",
    "vendor−Google Inc.",
    "cookieEnabled−true",
    "hardwareConcurrency−32",
    "webdriver−false",
    "pdfViewerEnabled−true",
]
DOCUMENT_KEYS = ['_reactListeningo743lnnpvdg', 'location']
WINDOW_KEYS = ["0", "window", "self", "document", "name", "location", "history", "navigator"]


def _get_parse_time():
    now = datetime.now(timezone(timedelta(hours=-5)))
    return now.strftime(TIME_LAYOUT) + " GMT-0500 (Eastern Standard Time)"


def _get_pow_config(user_agent):
    return [
        random.choice([1920 + 1080, 2560 + 1440, 1920 + 1200, 2560 + 1600]),
        _get_parse_time(),
        4294705152,
        0,
        user_agent,
        "",
        "",
        "en-US",
        "en-US,vi-VN,vi,en",
        0,
        random.choice(NAVIGATOR_KEYS),
        random.choice(DOCUMENT_KEYS),
        random.choice(WINDOW_KEYS),
        time.perf_counter() * 1000,
        str(uuid.uuid4()),
        "",
        random.choice(CORES),
        time.time() * 1000 - (time.perf_counter() * 1000),
    ]


def _generate_pow_answer(seed, diff, config):
    try:
        diff_len = len(diff)
        seed_encoded = seed.encode()
        static_p1 = (json.dumps(config[:3], separators=(',', ':'), ensure_ascii=False)[:-1] + ',').encode()
        static_p2 = (',' + json.dumps(config[4:9], separators=(',', ':'), ensure_ascii=False)[1:-1] + ',').encode()
        static_p3 = (',' + json.dumps(config[10:], separators=(',', ':'), ensure_ascii=False)[1:]).encode()
        target_diff = bytes.fromhex(diff)

        for i in range(250000):
            d_i = str(i).encode()
            d_j = str(i >> 1).encode()
            final_bytes = static_p1 + d_i + static_p2 + d_j + static_p3
            b64_enc = base64.b64encode(final_bytes)
            h = hashlib.sha3_512(seed_encoded + b64_enc).digest()
            if h[:diff_len] <= target_diff:
                return b64_enc.decode(), True
    except Exception:
        pass
    fallback = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + base64.b64encode(f'"{seed}"'.encode()).decode()
    return fallback, False


def get_answer_token(seed, diff, user_agent):
    config = _get_pow_config(user_agent)
    answer, _ = _generate_pow_answer(seed, diff, config)
    return "gAAAAAB" + answer


# ==============================================================================
# Cookie & Token Extraction & Parsing
# ==============================================================================

def extract_cookie_entries(text: str) -> list[str]:
    """Split user input text into discrete cookie / token entries.
    
    Handles:
    - Multi-line pretty-printed JSON (treated as 1 entry)
    - Multi-line cookie header blocks (treated as 1 entry)
    - Multi-account list (one account per line or block)
    """
    text = (text or "").strip()
    if not text:
        return []

    # If it's a JSON string (e.g. from /api/auth/session or Cookie-Editor export)
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            json.loads(text)
            return [text]
        except Exception:
            pass

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return []

    # If lines are part of a single multi-cookie header
    is_cookie_header_split = (
        len(lines) > 1
        and all("=" in l and len(l.split("=", 1)[0].strip()) < 50 for l in lines)
        and any("__Secure-next-auth" in l or "session-token" in l or "cf_clearance" in l for l in lines)
    )
    if is_cookie_header_split:
        joined = "; ".join(l.rstrip(";") for l in lines)
        return [joined]

    return lines


def _build_cookie_dict_result(cookie_dict: dict) -> dict:
    session_token = cookie_dict.get("__Secure-next-auth.session-token")
    has_chunk0 = "__Secure-next-auth.session-token.0" in cookie_dict
    has_chunk1 = "__Secure-next-auth.session-token.1" in cookie_dict
    has_chunks = has_chunk0 or has_chunk1

    cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
    return {
        "is_jwt": False,
        "access_token": None,
        "user": {},
        "cookie_str": cookie_str,
        "cookie_dict": cookie_dict,
        "session_token": session_token or cookie_dict.get("__Secure-next-auth.session-token.0"),
        "has_chunks": has_chunks,
        "missing_chunk1": has_chunk0 and not has_chunk1,
    }


def parse_cookie_input(raw: str) -> dict:
    """Normalize user input into session token, cookie header string, and cookie dict.

    Accepts:
    1. Raw JWT Access Token (starts with ey... with 2 dots, from /api/auth/session)
    2. Direct JSON copied from https://chatgpt.com/api/auth/session
    3. Cookie-Editor JSON export array
    4. Raw session token value (from __Secure-next-auth.session-token, with/without padding '=')
    5. Full cookie header string from browser Network tab (e.g. 'Cookie: ...')
    6. Chunked session tokens (__Secure-next-auth.session-token.0 / .1)
    """
    raw = (raw or "").strip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()

    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()
    if raw.startswith("Bearer "):
        raw = raw[7:].strip()

    # 1. JSON input
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                if "accessToken" in data:
                    user_info = data.get("user") or {}
                    return {
                        "is_jwt": True,
                        "access_token": data["accessToken"],
                        "user": user_info,
                        "cookie_str": "",
                        "cookie_dict": {},
                        "session_token": None,
                        "has_chunks": False,
                        "missing_chunk1": False,
                    }
                for k in ("token", "session_token", "access_token"):
                    if k in data and isinstance(data[k], str):
                        return parse_cookie_input(data[k])
            elif isinstance(data, list):
                cookie_dict = {}
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        cookie_dict[item["name"]] = item["value"]
                if cookie_dict:
                    return _build_cookie_dict_result(cookie_dict)
        except Exception:
            pass

    # 2. Check if raw input is an Access Token (JWT - 3 dot-separated parts starting with ey)
    jwt_parts = raw.split(".")
    if len(jwt_parts) == 3 and raw.startswith("ey"):
        user_info = {}
        try:
            padded = jwt_parts[1] + "=" * ((4 - len(jwt_parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
            if isinstance(payload, dict):
                email = payload.get("email") or payload.get("https://api.openai.com/profile", {}).get("email")
                name = payload.get("name")
                user_info = {"email": email, "name": name}
        except Exception:
            pass
        return {
            "is_jwt": True,
            "access_token": raw,
            "user": user_info,
            "cookie_str": "",
            "cookie_dict": {},
            "session_token": None,
            "has_chunks": False,
            "missing_chunk1": False,
        }

    # 3. Multi-cookie string (contains ';' or newline)
    if ";" in raw or "\n" in raw:
        cookie_dict = {}
        items = [i.strip() for i in re.split(r"[;\n]+", raw) if i.strip()]
        for item in items:
            if "=" in item:
                k, v = item.split("=", 1)
                k = k.strip()
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                cookie_dict[k] = v
        if cookie_dict:
            return _build_cookie_dict_result(cookie_dict)

    # 4. Single-line input
    cookie_dict = {}
    if "=" in raw:
        parts = raw.split("=", 1)
        k, v = parts[0].strip(), parts[1].strip()
        is_valid_cookie_key = (
            len(k) < 50
            and re.match(r"^[A-Za-z0-9_\.\-]+$", k)
            and not (k.startswith("ey") and len(k) > 20)
            and len(v) > 0
        )
        if is_valid_cookie_key:
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            cookie_dict[k] = v
            return _build_cookie_dict_result(cookie_dict)
        else:
            cookie_dict["__Secure-next-auth.session-token"] = raw
            return _build_cookie_dict_result(cookie_dict)
    else:
        cookie_dict["__Secure-next-auth.session-token"] = raw
        return _build_cookie_dict_result(cookie_dict)


# ==============================================================================
# ChatGPT Web Client
# ==============================================================================

class ChatGPTWebClient:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, cookies=None, model="auto"):
        if isinstance(cookies, str):
            cookies = extract_cookie_entries(cookies)
        elif isinstance(cookies, list):
            flattened = []
            for item in cookies:
                if isinstance(item, str):
                    flattened.extend(extract_cookie_entries(item))
            cookies = flattened
        self.cookies_list = cookies or []
        self.current_idx = 0
        self.model = model or "auto"
        self.device_id = str(uuid.uuid4())
        self._session_cache = {}  # idx -> {'access_token': ..., 'cookie_str': ..., 'expires': ...}

    def _create_http_session(self):
        try:
            return cffi_requests.Session(impersonate="chrome120")
        except Exception:
            return cffi_requests.Session()

    def _get_active_session_data(self, idx=None):
        if idx is None:
            idx = self.current_idx
        if not self.cookies_list:
            raise ValueError("Không có Cookie ChatGPT nào được cấu hình trong Cài đặt!")

        raw_cookie = self.cookies_list[idx % len(self.cookies_list)]
        cached = self._session_cache.get(idx)
        if cached and cached.get("expires", 0) > time.time() + 60:
            return cached

        parsed = parse_cookie_input(raw_cookie)
        if parsed["is_jwt"]:
            data = {
                "access_token": parsed["access_token"],
                "cookie_str": "",
                "cookie_dict": {},
                "user": parsed.get("user") or {"email": "ChatGPT Account"},
                "expires": time.time() + 3600,
            }
            self._session_cache[idx] = data
            return data

        s = self._create_http_session()
        headers = {
            "Host": "chatgpt.com",
            "User-Agent": self.USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://chatgpt.com/",
        }
        if parsed["cookie_str"]:
            headers["Cookie"] = parsed["cookie_str"]

        endpoints = [
            "https://chatgpt.com/api/auth/session",
            "https://chat.openai.com/api/auth/session",
        ]
        resp_data = None
        last_error = ""

        for url in endpoints:
            try:
                r = s.get(url, headers=headers, timeout=15)
                if r.status_code == 200:
                    try:
                        j = r.json()
                        if "accessToken" in j:
                            resp_data = j
                            break
                    except Exception:
                        pass
                elif r.status_code in (401, 403):
                    last_error = f"Trạng thái {r.status_code}: Cookie đã hết hạn hoặc bị từ chối."
            except Exception as e:
                last_error = f"Lỗi kết nối ({url}): {e}"

        if not resp_data or "accessToken" not in resp_data:
            if parsed.get("missing_chunk1"):
                raise RuntimeError(
                    "Cookie bị thiếu phần .1 (ChatGPT chia nhỏ session token thành .0 và .1). "
                    "Khuyên dùng: Mở tab https://chatgpt.com/api/auth/session rồi copy AccessToken (hoặc toàn bộ JSON) dán vào Cài đặt!"
                )
            raise RuntimeError(
                last_error or (
                    "Không thể lấy AccessToken từ ChatGPT Web. Cookie thiếu dữ liệu xác thực hoặc đã hết hạn. "
                    "Khuyên dùng: Mở tab https://chatgpt.com/api/auth/session trên trình duyệt rồi copy AccessToken (hoặc toàn bộ JSON) dán vào Cài đặt!"
                )
            )

        expires_at = time.time() + 1800
        try:
            exp_str = resp_data.get("expires")
            if exp_str:
                exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                expires_at = exp_dt.timestamp()
        except Exception:
            pass

        data = {
            "access_token": resp_data["accessToken"],
            "cookie_str": parsed["cookie_str"],
            "cookie_dict": parsed["cookie_dict"],
            "user": resp_data.get("user", {}),
            "expires": expires_at,
        }
        self._session_cache[idx] = data
        return data

    def _get_sentinel_tokens(self, s, access_token, cookie_str):
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Origin": "https://chatgpt.com",
            "Referer": "https://chatgpt.com/",
            "oai-device-id": self.device_id,
            "oai-language": "en-US",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        sentinel_headers = {}
        try:
            r = s.post(
                "https://chatgpt.com/backend-api/sentinel/chat-requirements",
                headers=headers,
                json={"conversation_mode_kind": "primary_assistant"},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                token = data.get("token")
                if token:
                    sentinel_headers["openai-sentinel-chat-requirements-token"] = token
                pow_data = data.get("proofofwork", {})
                if pow_data and pow_data.get("required"):
                    seed = pow_data.get("seed")
                    diff = pow_data.get("difficulty")
                    if seed and diff:
                        proof_token = get_answer_token(seed, diff, self.USER_AGENT)
                        sentinel_headers["openai-sentinel-proof-token"] = proof_token
        except Exception:
            pass
        return sentinel_headers

    def send_message(self, prompt: str, cancel_event=None, retry_count=3) -> str:
        if not self.cookies_list:
            raise ValueError("Không có Cookie ChatGPT nào được cấu hình trong Cài đặt!")

        attempts = 0
        total_slots = len(self.cookies_list)

        while attempts < retry_count * max(1, total_slots):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("CANCELLED")

            attempts += 1
            try:
                session_data = self._get_active_session_data(self.current_idx)
            except Exception as exc:
                if total_slots > 1 and attempts < total_slots:
                    self.current_idx = (self.current_idx + 1) % total_slots
                    continue
                raise exc

            access_token = session_data["access_token"]
            cookie_str = session_data["cookie_str"]

            s = self._create_http_session()
            sentinel_hdrs = self._get_sentinel_tokens(s, access_token, cookie_str)

            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Origin": "https://chatgpt.com",
                "Referer": "https://chatgpt.com/",
                "oai-device-id": self.device_id,
                "oai-language": "en-US",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }
            if cookie_str:
                headers["Cookie"] = cookie_str
            headers.update(sentinel_hdrs)

            payload = {
                "action": "next",
                "messages": [
                    {
                        "id": str(uuid.uuid4()),
                        "author": {"role": "user"},
                        "content": {
                            "content_type": "text",
                            "parts": [prompt],
                        },
                        "metadata": {},
                    }
                ],
                "parent_message_id": str(uuid.uuid4()),
                "model": self.model or "auto",
                "timezone_offset_min": -420,
                "history_and_training_disabled": True,
                "conversation_mode": {"kind": "primary_assistant"},
                "force_parallel_switch": "auto",
            }

            try:
                r = s.post(
                    "https://chatgpt.com/backend-api/conversation",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=90,
                )

                if r.status_code == 200:
                    response_text = ""
                    for line in r.iter_lines():
                        if cancel_event and cancel_event.is_set():
                            raise RuntimeError("CANCELLED")
                        if not line:
                            continue
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="replace")
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                event = json.loads(data_str)
                                msg = event.get("message")
                                if msg:
                                    parts = msg.get("content", {}).get("parts", [])
                                    if parts and isinstance(parts[0], str):
                                        response_text = parts[0]
                                    if msg.get("status") == "finished_successfully":
                                        break
                                err = event.get("error")
                                if err:
                                    raise RuntimeError(f"ChatGPT error: {err}")
                            except json.JSONDecodeError:
                                pass

                    if response_text.strip():
                        return response_text.strip()
                    else:
                        raise RuntimeError("ChatGPT không trả về văn bản.")

                elif r.status_code in (401, 403):
                    # Invalidate session cache and rotate
                    self._session_cache.pop(self.current_idx, None)
                    if total_slots > 1:
                        self.current_idx = (self.current_idx + 1) % total_slots
                        time.sleep(1)
                        continue
                    raise RuntimeError(f"ChatGPT từ chối truy cập (HTTP {r.status_code}). Cookie có thể đã hết hạn.")

                elif r.status_code == 429:
                    # Rate limit -> rotate cookie or wait
                    if total_slots > 1:
                        self.current_idx = (self.current_idx + 1) % total_slots
                        time.sleep(2)
                        continue
                    time.sleep(5)
                    continue

                else:
                    detail = r.text[:300] if hasattr(r, 'text') else ''
                    raise RuntimeError(f"Lỗi máy chủ ChatGPT (HTTP {r.status_code}): {detail}")

            except RuntimeError:
                raise
            except Exception as ex:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("CANCELLED")
                if attempts >= retry_count * max(1, total_slots):
                    raise RuntimeError(f"Lỗi khi gửi yêu cầu tới ChatGPT: {ex}")
                time.sleep(2)

        raise RuntimeError("Không thể nhận phản hồi từ ChatGPT sau nhiều lần thử.")

    @classmethod
    def test_cookie(cls, cookie_str: str) -> tuple[bool, str]:
        """Test a cookie string or token and return (success, message)."""
        entries = extract_cookie_entries(cookie_str)
        if not entries:
            return False, "Chưa nhập Cookie. Vui lòng dán Cookie hoặc AccessToken vào ô bên dưới."

        first_entry = entries[0]
        parsed = parse_cookie_input(first_entry)

        s = None
        try:
            s = cffi_requests.Session(impersonate="chrome120")
        except Exception:
            s = cffi_requests.Session()

        # If it is an Access Token (JWT)
        if parsed["is_jwt"]:
            token = parsed["access_token"]
            try:
                r = s.post(
                    "https://chatgpt.com/backend-api/sentinel/chat-requirements",
                    headers={
                        "User-Agent": cls.USER_AGENT,
                        "Accept": "*/*",
                        "Authorization": f"Bearer {token}",
                        "Referer": "https://chatgpt.com/",
                    },
                    json={},
                    timeout=15,
                )
                if r.status_code == 200:
                    u = parsed.get("user") or {}
                    info = u.get("email") or u.get("name") or "Token hoạt động tốt"
                    suffix = f" ({len(entries)} tài khoản đã nhập)" if len(entries) > 1 else ""
                    return True, f"AccessToken ChatGPT hoạt động rất tốt! ({info}){suffix}"
                elif r.status_code == 401:
                    return False, "AccessToken đã hết hạn. Vui lòng vào https://chatgpt.com/api/auth/session để lấy token mới."
                else:
                    return False, f"Kiểm tra AccessToken trả về HTTP {r.status_code}."
            except Exception as e:
                return False, f"Lỗi kiểm tra AccessToken: {e}"

        # If it is a Cookie
        if parsed.get("missing_chunk1"):
            return False, (
                "Cookie bị thiếu phần .1 (ChatGPT chia nhỏ session token thành .0 và .1). "
                "Khuyên dùng: Mở tab https://chatgpt.com/api/auth/session rồi copy AccessToken dán vào đây!"
            )

        headers = {
            "Host": "chatgpt.com",
            "User-Agent": cls.USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://chatgpt.com/",
        }
        if parsed["cookie_str"]:
            headers["Cookie"] = parsed["cookie_str"]

        endpoints = [
            "https://chatgpt.com/api/auth/session",
            "https://chat.openai.com/api/auth/session",
        ]
        for url in endpoints:
            try:
                r = s.get(url, headers=headers, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    if "accessToken" in data:
                        u = data.get("user") or {}
                        info = u.get("email") or u.get("name") or "Đăng nhập thành công"
                        suffix = f" ({len(entries)} tài khoản đã nhập)" if len(entries) > 1 else ""
                        return True, f"Cookie hoạt động tốt! ({info}){suffix}"
                    else:
                        return False, (
                            "Phản hồi rỗng: Cookie thiếu dữ liệu xác thực hoặc đã hết hạn. "
                            "Cách dễ nhất: Mở https://chatgpt.com/api/auth/session trên trình duyệt và copy toàn bộ nội dung JSON (hoặc AccessToken) dán vào đây!"
                        )
                elif r.status_code in (401, 403):
                    return False, f"Cookie không hợp lệ hoặc đã hết hạn (Mã lỗi {r.status_code})."
            except Exception as e:
                return False, f"Lỗi kết nối tới ChatGPT: {e}"

        return False, "Không thể xác thực với máy chủ ChatGPT."


# ==============================================================================
# Asynchronous Cookie Checker for Qt UI
# ==============================================================================

class ChatGPTCookieCheckWorker(QThread):
    result = pyqtSignal(bool, str) if callable(pyqtSignal) else None

    def __init__(self, cookie_input: str, parent=None):
        if QThread is not object:
            super().__init__(parent)
        self.cookie_input = cookie_input

    def run(self):
        success, message = ChatGPTWebClient.test_cookie(self.cookie_input)
        if hasattr(self, 'result') and self.result is not None:
            self.result.emit(success, message)


# ==============================================================================
# SRT Subtitle Translation with ChatGPT Web
# ==============================================================================

def parse_srt_subtitles(content: str) -> list[dict]:
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
        text = "\n".join(lines[stamp_line_idx + 1:]).strip()
        duration = max(0.1, (end_ms - start_ms) / 1000.0)
        subs.append({
            "index": idx,
            "start": m.group(1),
            "end": m.group(2),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration": duration,
            "text": text,
        })
        idx += 1
    return subs


def format_srt_content(subs: list[dict]) -> str:
    out = []
    for i, s in enumerate(subs, 1):
        out.append(f"{i}\n{s['start']} --> {s['end']}\n{s['text']}\n")
    return "\n".join(out)


def clean_translated_line(line: str) -> str:
    line = line.strip()
    # Strip timing prefix like [1.2s]
    line = re.sub(r"^\[\d+\.?\d*s\]\s*", "", line)
    # Strip line numbers like 1., 1 -, Câu 1:
    line = re.sub(r"^(?:Câu\s*)?\d+[\.|\:\-\)]+\s*", "", line)
    return line.strip()


def chatgpt_translate_logic(
    srt_path: str,
    cookies: list[str],
    status_cb: callable,
    cancel_event,
    workspace_dir: str,
    prompt_style: str = 'Mặc định',
    custom_prompt_text: str = '',
    target_lang: str = 'Tiếng Việt',
    model: str = 'auto',
) -> str:
    """Translates an SRT subtitle file using ChatGPT Web cookies with error resume."""
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Không tìm thấy file kịch bản gốc: {srt_path}")

    # Read SRT
    with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f:
        content = f.read()

    subtitles = parse_srt_subtitles(content)
    if not subtitles:
        raise ValueError("File SRT không có phụ đề hợp lệ để dịch.")

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
            f"Đang tiếp tục dịch {len(missing_indices)} câu còn lại bằng ChatGPT Web...",
            0.05 + 0.90 * (len(translated_map) / total_subs)
        )
    else:
        status_cb(f"Khởi động ChatGPT Web dịch {total_subs} câu sang {target_lang}...", 0.05)

    client = ChatGPTWebClient(cookies=cookies, model=model)

    # Get prompt template
    try:
        from app.common.prompts import PROMPTS_DATA, GENERIC_PROMPT
        if target_lang in PROMPTS_DATA:
            rules_template = PROMPTS_DATA[target_lang].get("system_rules", "")
            styles = PROMPTS_DATA[target_lang].get("styles", {})
        else:
            rules_template = GENERIC_PROMPT.get("system_rules", "")
            styles = GENERIC_PROMPT.get("styles", {})
        style_prompt = styles.get(prompt_style, styles.get("Mặc định", ""))
    except Exception:
        rules_template = (
            f"Bạn là một Biên kịch lồng tiếng Video chuyên nghiệp. Nhiệm vụ: Dịch sang {target_lang} các phụ đề sau.\n"
            f"LỆNH BẮT BUỘC: Đưa vào {{num_lines}} dòng -> BẮT BUỘC trả ra đúng {{num_lines}} dòng. "
            f"Mỗi câu dịch nằm trên 1 dòng duy nhất. KHÔNG in lại thời gian [..s]."
        )
        style_prompt = ""

    if prompt_style == "Tùy chỉnh" and custom_prompt_text.strip():
        style_prompt = f"YÊU CẦU ĐẶC BIỆT:\n{custom_prompt_text.strip()}"

    try:
        from translation_rules import rules_for_target_lang
        novel_translation_rules = rules_for_target_lang(target_lang)
    except Exception:
        novel_translation_rules = ""

    chunk_size = 45  # Optimized chunk size
    chunks = []
    curr_indices = []
    for idx in missing_indices:
        curr_indices.append(idx)
        if len(curr_indices) >= chunk_size:
            chunks.append(list(curr_indices))
            curr_indices = []
    if curr_indices:
        chunks.append(list(curr_indices))

    for chunk_indices in chunks:
        if cancel_event and cancel_event.is_set():
            return "CANCELLED"

        chunk = [subtitles[i] for i in chunk_indices]
        chunk_num_lines = len(chunk)

        pct = 0.05 + 0.90 * (len(pm.translations) / max(1, total_subs))
        status_cb(f"Đang dịch sang {target_lang} ({len(pm.translations) + 1}-{min(len(pm.translations) + chunk_num_lines, total_subs)}/{total_subs} câu)...", pct)

        chunk_lines = [f"[{s['duration']:.1f}s] {s['text']}" for s in chunk]
        chunk_input = "\n".join(chunk_lines)

        system_part = rules_template.format(num_lines=chunk_num_lines, target_lang=target_lang)
        prompt = (
            f"{system_part}\n\n"
            f"{style_prompt}\n\n"
            f"{novel_translation_rules}\n\n"
            f"Dữ liệu gốc (Gồm đúng {chunk_num_lines} dòng):\n"
            f"{chunk_input}\n\n"
            f"Bản dịch ({chunk_num_lines} dòng tương ứng):"
        )

        try:
            resp = client.send_message(prompt, cancel_event=cancel_event)
            if resp == "CANCELLED":
                return "CANCELLED"

            if resp.startswith("```"):
                resp = re.sub(r"^```[a-zA-Z]*\n", "", resp)
                resp = re.sub(r"\n```$", "", resp)

            raw_lines = [clean_translated_line(l) for l in resp.splitlines() if l.strip()]

            # Align chunk lines
            aligned = []
            if len(raw_lines) == chunk_num_lines:
                aligned = raw_lines
            elif len(raw_lines) > chunk_num_lines:
                matched = raw_lines[:chunk_num_lines - 1]
                matched.append(" ".join(raw_lines[chunk_num_lines - 1:]))
                aligned = matched
            else:
                for k in range(chunk_num_lines):
                    if k < len(raw_lines):
                        aligned.append(raw_lines[k])
                    else:
                        aligned.append(chunk[k]["text"])

            # Save completed chunk immediately
            pm.save_chunk(chunk_indices, aligned, subtitles)
        except Exception as exc:
            saved_count = len(pm.translations)
            err_msg = (
                f"[TẠM DỪNG DO LỖI] Đã lưu tiến trình dịch ({saved_count}/{total_subs} câu). "
                f"Lỗi: {exc}. "
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
            import re
            from pathlib import Path
            raw = Path(out_srt_path).read_text(encoding="utf-8-sig")
            cleaned = re.sub(r'\[(sirvietsub|luavietsup)\]\s*', '', raw, flags=re.IGNORECASE)
            if cleaned != raw:
                Path(out_srt_path).write_text(cleaned, encoding="utf-8")
    except Exception:
        pass

    status_cb("Hoàn tất dịch bằng ChatGPT Web!", 1.0)
    return out_srt_path
