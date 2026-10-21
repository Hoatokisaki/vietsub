# -*- coding: utf-8 -*-
"""Owner-issued, HWID-bound Premium grants for luaVietsup.

The private signing key stays on the owner's Windows profile. The app only
needs the public key embedded in main.py to verify a grant.
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

PRODUCT_ID = "luaVietsup"
LICENSE_SCHEMA = 1
_ACTIVE_PUBLIC_KEY_PEM = None


def _owner_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return root / "luaVietsupOwner"


def _private_key_path() -> Path:
    return _owner_dir() / "license_signing_key.pem"


def local_license_path() -> Path:
    root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return root / "SirVietsub" / "premium_license.json"


def load_bundled_public_key() -> bytes:
    """Read the helper copy; runtime validation uses the key compiled into main.py."""
    return (Path(__file__).resolve().with_name("license_public_key.pem")).read_bytes()


def service_config_path() -> Path:
    return Path(__file__).resolve().with_name("license_service_config.json")


def _service_config_candidates():
    user_root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    yield user_root / "luaVietsup" / "license_service_config.json"
    yield service_config_path()


def load_service_config() -> dict:
    """Load only public Supabase connection details; never store server secrets here."""
    for path in _service_config_candidates():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                continue
            url = str(value.get("url", "")).strip().rstrip("/")
            key = str(value.get("publishable_key", "")).strip()
            if url.startswith("https://") and key:
                return {"url": url, "publishable_key": key}
        except Exception:
            continue
    return {}


def remote_service_configured() -> bool:
    return bool(load_service_config())


def check_remote_license(hwid: str, config: dict | None = None, timeout: float = 6.0):
    """Return (reachable, premium, message); HWIDs are hashed before transmission."""
    config = config or load_service_config()
    url = str(config.get("url", "")).strip().rstrip("/")
    key = str(config.get("publishable_key", "")).strip()
    if not (url.startswith("https://") and key):
        return (False, False, "Remote license service is not configured.")
    payload = json.dumps({"product": PRODUCT_ID, "hwid_sha256": hwid_digest(hwid)}).encode("utf-8")
    request = urllib.request.Request(
        url + "/functions/v1/license-check",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": key,
            "Authorization": "Bearer " + key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, min(float(timeout), 15.0))) as response:
            result = json.loads(response.read(65536).decode("utf-8"))
        if not isinstance(result, dict) or not isinstance(result.get("premium"), bool):
            raise ValueError("Remote license service returned an invalid response.")
        return (True, result["premium"], str(result.get("message", "")))
    except Exception as exc:
        return (False, False, str(exc) or "Could not reach the remote license service.")


def active_public_key() -> bytes:
    """Return the verifier key supplied by the running main module."""
    return _ACTIVE_PUBLIC_KEY_PEM or load_bundled_public_key()


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _normalize_hwid(hwid: str) -> str:
    return str(hwid or "").strip().casefold()


def hwid_digest(hwid: str) -> str:
    normalized = _normalize_hwid(hwid)
    if not normalized:
        raise ValueError("HWID không được để trống.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_utc(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Thiếu thời điểm trong giấy phép.")
    parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Thời điểm giấy phép không có múi giờ.")
    return parsed.astimezone(_dt.timezone.utc)


def verify_license_document(document, hwid: str, public_key_pem: bytes):
    """Return (valid, message) after checking signature, product, HWID and dates."""
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        if not isinstance(document, dict):
            raise ValueError("Tệp giấy phép không đúng định dạng.")
        payload = document.get("payload")
        signature_text = document.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature_text, str):
            raise ValueError("Tệp giấy phép thiếu dữ liệu chữ ký.")
        if payload.get("schema") != LICENSE_SCHEMA or payload.get("product") != PRODUCT_ID:
            raise ValueError("Giấy phép không dành cho luaVietsup.")
        actual = hwid_digest(hwid)
        expected = str(payload.get("hwid_sha256", ""))
        if not expected or not __import__("hmac").compare_digest(actual, expected):
            raise ValueError("Giấy phép được cấp cho HWID khác.")
        issued = _parse_utc(payload.get("issued_at"))
        now = _dt.datetime.now(_dt.timezone.utc)
        if issued > now + _dt.timedelta(minutes=10):
            raise ValueError("Thời điểm cấp giấy phép nằm trong tương lai.")
        expires = payload.get("expires_at")
        if expires is not None and now >= _parse_utc(expires):
            raise ValueError("Giấy phép Premium đã hết hạn.")
        signature = base64.b64decode(signature_text, validate=True)
        load_pem_public_key(public_key_pem).verify(signature, _canonical_payload(payload))
        label = str(payload.get("label", "")).strip()
        suffix = (" cho " + label) if label else ""
        return (True, "Đã xác thực quyền Premium" + suffix + ".")
    except Exception as exc:
        return (False, str(exc) or "Không xác thực được giấy phép.")


def check_local_license(hwid: str, public_key_pem: bytes):
    path = local_license_path()
    try:
        if not path.is_file() or path.stat().st_size > 65536:
            return (False, "Chưa có gói Premium hợp lệ trên thiết bị.")
        document = json.loads(path.read_text(encoding="utf-8"))
        return verify_license_document(document, hwid, public_key_pem)
    except Exception as exc:
        return (False, "Không đọc được gói Premium: " + str(exc))


def install_license_file(source_path: str, hwid: str, public_key_pem: bytes):
    source = Path(source_path)
    if not source.is_file() or source.stat().st_size > 65536:
        return (False, "Tệp giấy phép không tồn tại hoặc vượt quá kích thước cho phép.")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        return (False, "Tệp giấy phép không đọc được: " + str(exc))
    valid, message = verify_license_document(document, hwid, public_key_pem)
    if not valid:
        return (False, message)
    destination = local_license_path()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_suffix(destination.suffix + ".tmp")
        temp.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, destination)
        return (True, message + " Khởi động lại app để áp dụng.")
    except Exception as exc:
        return (False, "Không lưu được giấy phép: " + str(exc))


def _load_owner_private_key():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    path = _private_key_path()
    if not path.is_file():
        raise FileNotFoundError("Không tìm thấy khóa cấp phép của chủ app.")
    return load_pem_private_key(path.read_bytes(), password=None)


def owner_key_available() -> bool:
    try:
        from cryptography.hazmat.primitives import serialization

        private = _load_owner_private_key()
        bundled = load_bundled_public_key()
        derived = private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return __import__("hmac").compare_digest(derived, bundled)
    except Exception:
        return False


def issue_license(hwid: str, label: str = "", expires_in_days: int = 0) -> dict:
    """Create a signed grant. A zero day count means no expiry."""
    from cryptography.hazmat.primitives import serialization

    hwid_value = str(hwid or "").strip()
    if not hwid_value:
        raise ValueError("HWID không được để trống.")
    label = str(label or "").strip()
    if len(label) > 120 or any(ord(ch) < 32 for ch in label):
        raise ValueError("Tên người nhận không hợp lệ (tối đa 120 ký tự).")
    days = int(expires_in_days or 0)
    if days < 0 or days > 36500:
        raise ValueError("Số ngày hết hạn phải từ 0 đến 36500.")
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    expires = None if days == 0 else now + _dt.timedelta(days=days)
    payload = {
        "schema": LICENSE_SCHEMA,
        "product": PRODUCT_ID,
        "hwid_sha256": hwid_digest(hwid_value),
        "label": label,
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z") if expires else None,
    }
    private = _load_owner_private_key()
    derived = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if not __import__("hmac").compare_digest(derived, load_bundled_public_key()):
        raise ValueError("Khóa riêng không khớp khóa công khai của bản app này.")
    signature = private.sign(_canonical_payload(payload))
    return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}


def install_license_override(security_module, public_key_pem: bytes) -> bool:
    """Use remote entitlements when configured; otherwise retain local and legacy checks."""
    if getattr(security_module, "_luavietsup_license_override", False):
        return True
    global _ACTIVE_PUBLIC_KEY_PEM
    _ACTIVE_PUBLIC_KEY_PEM = bytes(public_key_pem or b"")
    if not _ACTIVE_PUBLIC_KEY_PEM:
        return False
    original = getattr(security_module, "check_license_online", None)
    if not callable(original):
        return False

    def check_license_online(hwid, app_version):
        config = load_service_config()
        if config:
            reachable, premium, message = check_remote_license(hwid, config)
            if reachable:
                return ("premium" if premium else "free", message)
            # A remote project is authoritative. Do not accept a stale offline
            # grant when its status cannot be refreshed; preserve the app's
            # existing online check as a fallback for a temporary outage.
            return original(hwid, app_version)
        valid, message = check_local_license(hwid, public_key_pem)
        if valid:
            return ("premium", message)
        return original(hwid, app_version)

    security_module.check_license_online = check_license_online
    security_module._luavietsup_license_override = True
    return True
