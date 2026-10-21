# -*- coding: utf-8 -*-
"""Owner console for remotely granting and revoking luaVietsup Premium."""
from pathlib import Path
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import messagebox

try:
    from tkinter import ttk
except ImportError:
    ttk = None


class _ClassicStyle:
    """No-op styling API used when the frozen runtime omits tkinter.ttk."""

    def __init__(self, master=None):
        self.master = master

    def theme_use(self, *_args, **_kwargs):
        return None

    def configure(self, *_args, **_kwargs):
        return None


class _ClassicTreeview(tk.Frame):
    """Small Treeview-compatible table built from Tk's always-available Listbox."""

    def __init__(self, master, columns=(), height=10, selectmode="browse", **_kwargs):
        super().__init__(master, bg="#101827", bd=0)
        self._columns = tuple(columns)
        self._headings = {column: str(column) for column in self._columns}
        self._widths = {column: 14 for column in self._columns}
        self._items = []

        self._header = tk.Label(
            self, text="", anchor="w", bg="#243247", fg="#e5edf7",
            font=("Consolas", 9, "bold"), padx=5, pady=5,
        )
        self._header.pack(fill="x")

        body = tk.Frame(self, bg="#101827")
        body.pack(fill="both", expand=True)
        mode = tk.BROWSE if selectmode == "browse" else tk.EXTENDED
        self._listbox = tk.Listbox(
            body, height=height, selectmode=mode, font=("Consolas", 9),
            bg="#0b1220", fg="#e5edf7", selectbackground="#2563eb",
            selectforeground="#ffffff", activestyle="none", exportselection=False,
        )
        vertical = tk.Scrollbar(body, orient="vertical", command=self._listbox.yview)
        horizontal = tk.Scrollbar(body, orient="horizontal", command=self._listbox.xview)
        self._listbox.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self._listbox.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self._update_header()

    def heading(self, column, text=None, **_kwargs):
        if text is not None:
            self._headings[column] = str(text)
            self._update_header()

    def column(self, column, width=None, **_kwargs):
        if width is not None:
            self._widths[column] = max(8, min(40, int(width / 8)))
            self._update_header()

    def _update_header(self):
        parts = []
        for column in self._columns:
            width = self._widths.get(column, 14)
            parts.append(self._headings.get(column, str(column))[:width].ljust(width))
        self._header.configure(text=" | ".join(parts))

    def _format_values(self, values):
        parts = []
        for column, value in zip(self._columns, values):
            width = self._widths.get(column, 14)
            parts.append(str(value or "")[:width].ljust(width))
        return " | ".join(parts)

    def _render_items(self, preserve_selection=()):
        self._listbox.delete(0, tk.END)
        selected_indices = []
        for index, (item_id, values) in enumerate(self._items):
            self._listbox.insert(tk.END, self._format_values(values))
            if item_id in preserve_selection:
                selected_indices.append(index)
        for index in selected_indices:
            self._listbox.selection_set(index)

    def get_children(self, *_args):
        return tuple(item_id for item_id, _values in self._items)

    def delete(self, *item_ids):
        remove = set(item_ids)
        if not remove:
            return
        self._items = [(item_id, values) for item_id, values in self._items if item_id not in remove]
        self._render_items()

    def insert(self, _parent, _index, iid=None, values=(), **_kwargs):
        item_id = str(iid if iid is not None else "row-" + str(len(self._items)))
        self._items.append((item_id, tuple(values)))
        self._render_items()
        return item_id

    def selection(self):
        return tuple(
            self._items[index][0]
            for index in self._listbox.curselection()
            if 0 <= index < len(self._items)
        )


class _ClassicTtk:
    """Compatibility surface for the subset of ttk used by this utility."""

    Style = _ClassicStyle
    Treeview = _ClassicTreeview

    @staticmethod
    def _padding(value):
        if isinstance(value, (tuple, list)):
            if len(value) >= 2:
                return value[0], value[1]
            if value:
                return value[0], value[0]
        return value, value

    @classmethod
    def Frame(cls, master, padding=0, **kwargs):
        padx, pady = cls._padding(padding)
        kwargs.setdefault("bg", "#101827")
        return tk.Frame(master, padx=padx, pady=pady, **kwargs)

    @classmethod
    def LabelFrame(cls, master, padding=0, **kwargs):
        padx, pady = cls._padding(padding)
        kwargs.setdefault("bg", "#172337")
        kwargs.setdefault("fg", "#60a5fa")
        kwargs.setdefault("font", ("Segoe UI", 10, "bold"))
        return tk.LabelFrame(master, padx=padx, pady=pady, **kwargs)

    @staticmethod
    def Label(master, **kwargs):
        style = kwargs.pop("style", "")
        kwargs.setdefault("bg", "#172337" if isinstance(master, tk.LabelFrame) else "#101827")
        kwargs.setdefault("fg", "#e5edf7")
        kwargs.setdefault("font", ("Segoe UI", 10))
        if style == "Header.TLabel":
            kwargs["bg"] = "#101827"
            kwargs["fg"] = "#60a5fa"
            kwargs["font"] = ("Segoe UI", 17, "bold")
        return tk.Label(master, **kwargs)

    @staticmethod
    def Entry(master, **kwargs):
        kwargs.setdefault("bg", "#0b1220")
        kwargs.setdefault("fg", "#e5edf7")
        kwargs.setdefault("insertbackground", "#e5edf7")
        kwargs.setdefault("relief", "flat")
        return tk.Entry(master, **kwargs)

    @staticmethod
    def Button(master, **kwargs):
        kwargs.setdefault("bg", "#2563eb")
        kwargs.setdefault("fg", "#ffffff")
        kwargs.setdefault("activebackground", "#1d4ed8")
        kwargs.setdefault("activeforeground", "#ffffff")
        kwargs.setdefault("font", ("Segoe UI", 9, "bold"))
        kwargs.setdefault("padx", 10)
        kwargs.setdefault("pady", 5)
        kwargs.setdefault("relief", "flat")
        return tk.Button(master, **kwargs)


if ttk is None:
    ttk = _ClassicTtk

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = ROOT / "_internal"
sys.path.insert(0, str(INTERNAL))
import license_runtime

APPDATA_CONFIG = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "luaVietsup" / "license_service_config.json"


def http_json(url, payload=None, headers=None, timeout=12):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024)
        return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read(65536).decode("utf-8"))
            detail = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error")
        except Exception:
            detail = "HTTP " + str(exc.code)
        raise RuntimeError(str(detail or "HTTP " + str(exc.code))) from exc


def read_config():
    return license_runtime.load_service_config()


def write_config(url, key):
    config = {"url": url.strip().rstrip("/"), "publishable_key": key.strip()}
    if not config["url"].startswith("https://") or not config["publishable_key"]:
        raise ValueError("Cần URL HTTPS của Supabase và publishable key.")
    targets = [APPDATA_CONFIG, INTERNAL / "license_service_config.json", ROOT / "source" / "patches" / "license_service_config.json"]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, target)


def run():
    app = tk.Tk()
    app.title("luaVietsup - Quản lý Premium từ xa")
    app.geometry("940x680")
    app.minsize(800, 570)
    app.configure(bg="#101827")

    style = ttk.Style(app)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TFrame", background="#101827")
    style.configure("TLabel", background="#101827", foreground="#e5edf7", font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 17, "bold"), foreground="#60a5fa")
    style.configure("TButton", font=("Segoe UI", 10), padding=7)
    style.configure("Treeview", rowheight=25)

    outer = ttk.Frame(app, padding=18)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="Quản lý HWID Premium từ xa", style="Header.TLabel").pack(anchor="w")
    ttk.Label(outer, text="Cấp hoặc thu hồi quyền qua máy chủ Supabase. Tài khoản quản trị được xác thực ở máy chủ.", wraplength=880).pack(anchor="w", pady=(4, 12))

    config_box = ttk.LabelFrame(outer, text="Kết nối Supabase", padding=10)
    config_box.pack(fill="x", pady=(0, 10))
    ttk.Label(config_box, text="Project URL").grid(row=0, column=0, sticky="w", pady=4)
    url_var = tk.StringVar()
    ttk.Entry(config_box, textvariable=url_var, width=76).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
    ttk.Label(config_box, text="Publishable key").grid(row=1, column=0, sticky="w", pady=4)
    key_var = tk.StringVar()
    ttk.Entry(config_box, textvariable=key_var, width=76, show="•").grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=4)
    config_box.columnconfigure(1, weight=1)

    login_box = ttk.LabelFrame(outer, text="Đăng nhập chủ ứng dụng", padding=10)
    login_box.pack(fill="x", pady=(0, 10))
    ttk.Label(login_box, text="Email").grid(row=0, column=0, sticky="w", pady=4)
    email_var = tk.StringVar()
    ttk.Entry(login_box, textvariable=email_var, width=34).grid(row=0, column=1, sticky="ew", padx=(10, 18), pady=4)
    ttk.Label(login_box, text="Mật khẩu").grid(row=0, column=2, sticky="w", pady=4)
    password_var = tk.StringVar()
    ttk.Entry(login_box, textvariable=password_var, width=30, show="•").grid(row=0, column=3, sticky="ew", padx=(10, 0), pady=4)
    login_box.columnconfigure(1, weight=1)
    login_box.columnconfigure(3, weight=1)

    state_var = tk.StringVar(value="Nhập cấu hình Supabase và đăng nhập bằng tài khoản quản trị đã được cho phép.")
    ttk.Label(outer, textvariable=state_var, wraplength=880).pack(anchor="w", pady=(0, 8))

    form = ttk.LabelFrame(outer, text="Cấp / gia hạn Premium", padding=10)
    form.pack(fill="x")
    ttk.Label(form, text="HWID").grid(row=0, column=0, sticky="w", pady=4)
    hwid_var = tk.StringVar()
    ttk.Entry(form, textvariable=hwid_var, width=70).grid(row=0, column=1, sticky="ew", padx=(10, 14), pady=4)
    ttk.Label(form, text="Tên / ghi chú").grid(row=1, column=0, sticky="w", pady=4)
    label_var = tk.StringVar()
    ttk.Entry(form, textvariable=label_var).grid(row=1, column=1, sticky="ew", padx=(10, 14), pady=4)
    ttk.Label(form, text="Số ngày (0 = vĩnh viễn)").grid(row=0, column=2, sticky="w", pady=4)
    days_var = tk.StringVar(value="0")
    ttk.Entry(form, textvariable=days_var, width=12).grid(row=0, column=3, sticky="w", padx=(10, 0), pady=4)
    form.columnconfigure(1, weight=1)

    # Keep the actions immediately below the grant form so they remain visible
    # on smaller screens and at higher Windows display scaling.
    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(8, 2))

    columns = ("hint", "holder", "status", "expires", "hash")
    table = ttk.Treeview(outer, columns=columns, show="headings", height=8, selectmode="browse")
    for key, title, width in (
        ("hint", "HWID cuối", 100), ("holder", "Người dùng / ghi chú", 240),
        ("status", "Trạng thái", 110), ("expires", "Hết hạn", 150), ("hash", "Mã nhận diện", 210),
    ):
        table.heading(key, text=title)
        table.column(key, width=width, anchor="w")
    table.pack(fill="both", expand=True, pady=(4, 8))

    session = {"url": "", "key": "", "token": ""}

    def connect_values(save=True):
        url = url_var.get().strip().rstrip("/")
        key = key_var.get().strip()
        if not url.startswith("https://") or not key:
            raise ValueError("Nhập Project URL và publishable key trước.")
        if save:
            write_config(url, key)
        session["url"], session["key"] = url, key

    def admin_call(payload):
        if not session["token"]:
            raise RuntimeError("Hãy đăng nhập lại trước.")
        return http_json(
            session["url"] + "/functions/v1/license-admin",
            payload,
            {"apikey": session["key"], "Authorization": "Bearer " + session["token"]},
        )

    def refresh(show_errors=True):
        if not session["token"]:
            return
        try:
            result = admin_call({"action": "list"})
            for item in table.get_children():
                table.delete(item)
            for row in result.get("licenses", []):
                expires = row.get("expires_at")
                if expires:
                    expires = str(expires).replace("T", " ")[:16]
                else:
                    expires = "Vĩnh viễn"
                status = "Đang hoạt động" if row.get("active") else "Đã thu hồi"
                digest = str(row.get("hwid_sha256", ""))
                table.insert("", "end", iid=digest, values=(row.get("hwid_hint", ""), row.get("holder_name", ""), status, expires, digest[:18]))
            state_var.set("Đã tải " + str(len(result.get("licenses", []))) + " bản ghi từ máy chủ.")
        except Exception as exc:
            state_var.set("Lỗi tải danh sách: " + str(exc))
            if show_errors:
                messagebox.showerror("Không tải được", str(exc), parent=app)

    def login():
        try:
            connect_values(save=True)
            email = email_var.get().strip()
            password = password_var.get()
            if not email or not password:
                raise ValueError("Nhập email và mật khẩu Supabase Auth.")
            endpoint = session["url"] + "/auth/v1/token?grant_type=password"
            result = http_json(endpoint, {"email": email, "password": password}, {"apikey": session["key"]})
            token = str(result.get("access_token", ""))
            if not token:
                raise RuntimeError("Supabase không trả về access token.")
            session["token"] = token
            password_var.set("")
            state_var.set("Đã đăng nhập. Đang kiểm tra quyền quản trị...")
            refresh()
        except Exception as exc:
            session["token"] = ""
            state_var.set("Đăng nhập thất bại: " + str(exc))
            messagebox.showerror("Đăng nhập thất bại", str(exc), parent=app)

    def grant():
        try:
            connect_values(save=True)
            raw_hwid = hwid_var.get().strip()
            if not raw_hwid:
                raise ValueError("Nhập HWID lấy từ trang Tài khoản của thiết bị.")
            days = int(days_var.get().strip() or "0")
            result = admin_call({"action": "grant", "hwid": raw_hwid, "label": label_var.get().strip(), "expiry_days": days})
            state_var.set("Đã cấp quyền cho HWID " + str(result.get("hwid_sha256", ""))[:18] + "…")
            hwid_var.set("")
            refresh(show_errors=False)
        except Exception as exc:
            messagebox.showerror("Không cấp được Premium", str(exc), parent=app)

    def revoke():
        selected = table.selection()
        if not selected:
            messagebox.showinfo("Chọn thiết bị", "Chọn một dòng trong danh sách rồi bấm Thu hồi.", parent=app)
            return
        if not messagebox.askyesno("Thu hồi quyền", "Thu hồi Premium cho HWID đang chọn? App sẽ cập nhật khi thiết bị kết nối máy chủ.", parent=app):
            return
        try:
            admin_call({"action": "revoke", "hwid_sha256": selected[0]})
            state_var.set("Đã thu hồi quyền trên máy chủ.")
            refresh(show_errors=False)
        except Exception as exc:
            messagebox.showerror("Không thu hồi được", str(exc), parent=app)

    ttk.Button(actions, text="Lưu cấu hình và đăng nhập", command=login).pack(side="left")
    ttk.Button(actions, text="Cấp / gia hạn Premium", command=grant).pack(side="left", padx=8)
    ttk.Button(actions, text="Làm mới", command=refresh).pack(side="left")
    ttk.Button(actions, text="Thu hồi HWID đã chọn", command=revoke).pack(side="right")

    config = read_config()
    if config:
        url_var.set(config.get("url", ""))
        key_var.set(config.get("publishable_key", ""))
    app.mainloop()


if __name__ == "__main__":
    run()
