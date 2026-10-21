# luaVietsup Pro v2.6 - Mã Nguồn Chuẩn (Clean & Optimized)

Bộ mã nguồn hoàn chỉnh của dự án **luaVietsup Pro v2.6** (trước đây là SirVietsub), đã được tối ưu hóa toàn bộ file rác, sửa triệt để các lỗi khởi tạo DLL và tích hợp các tính năng cao cấp.

---

## 📁 Cấu trúc thư mục chuẩn

```text
luaVietsup_Source_Clean/
├── source/                      # Mã nguồn Python hoàn chỉnh
│   ├── main.py                  # Entry point chính của ứng dụng
│   ├── assets/                  # Logo, icons luaVietsup
│   ├── patches/                 # Các module mở rộng (Custom API, ChatGPT Web, Translation Rules)
│   ├── recovered/               # Toàn bộ mã nguồn giao diện (UI) và tính năng core
│   └── protected_wrappers/      # Giao diện kết nối worker
├── tools/                       # Kịch bản build & đóng gói tự động
│   ├── build_recovered.py       # Kịch bản build app chính
│   ├── build_native_stub_dll.py # Compiler tạo native stub setupapx.dll
│   ├── package_installer.py     # Kịch bản đóng gói thành 1 file Setup duy nhất
│   └── admin_app/               # Mã nguồn C# app Quản lý Premium từ xa
├── backup/                      # File exe base gốc để rebuild CArchive
├── bytecode/                    # Bytecode đối chiếu
├── QuanLyPremium_TuXa/          # Ứng dụng quản trị Premium HWID độc lập
│   ├── QUAN_LY_PREMIUM_TU_XA.exe
│   └── HUONG_DAN_SU_DUNG.txt
├── _internal/                   # Môi trường runtime Python 3.10, PyTorch, Paddle, ONNX, Models
├── luaVietsup-ModelFix4.exe     # File thực thi ứng dụng chính
├── setupapx.dll                 # Native stub sửa lỗi WinError 1114 cho Qt & ONNX Runtime
├── build.bat                    # Script 1-click build lại ứng dụng sau khi sửa code
├── CHAY_luaVietsup.bat          # Phím tắt khởi động nhanh ứng dụng
└── README.md                    # Tài liệu hướng dẫn này
```

---

## 🚀 Hướng dẫn sử dụng

### 1. Khởi động ứng dụng
- Chạy trực tiếp: `luaVietsup-ModelFix4.exe` hoặc nhấp đúp `CHAY_luaVietsup.bat`.

### 2. Build lại ứng dụng khi chỉnh sửa mã nguồn
- Sau khi chỉnh sửa file trong thư mục `source/`, chỉ cần nhấp đúp file `build.bat`.
- Hệ thống sẽ tự động biên dịch CPython 3.10, patch IAT và đồng bộ vào file thực thi.

### 3. Đóng gói bộ cài đặt (Installer) gửi cho khách
- Chạy lệnh: `python tools/package_installer.py`.
- Tự động tạo ra 1 file cài đặt duy nhất `Setup_luaVietsup_Pro_v2.6.exe` (3.27 GB) kèm logo thương hiệu luaVietsup.

### 4. Quản lý bản quyền Premium từ xa
- Vào thư mục `QuanLyPremium_TuXa/` và chạy `QUAN_LY_PREMIUM_TU_XA.exe`.
- Dùng để kích hoạt, kiểm tra và thu hồi bản quyền theo mã máy (HWID) từ xa.
