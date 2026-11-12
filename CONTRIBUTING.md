# Đóng góp cho CIT Voice Studio

Cảm ơn bạn đã quan tâm. Mọi đóng góp đều được chào đón: báo lỗi, sửa lỗi, cải thiện giao diện, tài liệu, hay thêm tính năng.

## Trước khi bắt đầu

- **Lỗi nhỏ, sửa chữ, tài liệu:** gửi pull request luôn.
- **Tính năng mới hoặc thay đổi lớn:** mở issue trước để thống nhất hướng làm, tránh bạn mất công viết code rồi không được nhận.
- **Lỗ hổng bảo mật:** không mở issue công khai, xem [SECURITY.md](SECURITY.md).

## Cài môi trường phát triển

Cần: Windows, macOS hoặc Linux; [uv](https://docs.astral.sh/uv/); Node.js 20 trở lên.

```bash
# Python 3.12 và thư viện (uv tự cài Python nếu máy chưa có)
uv sync --group desktop --group dev

# Giao diện React
cd app-desktop/cit-voice-app
npm ci
npm run build        # tạo dist/ để backend phục vụ giao diện
cd ../..

# Chạy app
uv run python -m apps.desktop_app
```

Lần chạy đầu, app tải khoảng 312 MB mô hình về `models/hf_cache`. Muốn tải trước: `uv run python scripts/fetch_models.py`.

Khi sửa giao diện, chạy `npm run dev` trong `app-desktop/cit-voice-app` (cổng 1420) song song với backend để thấy thay đổi ngay.

Ghi chú về kiến trúc và các chỗ dễ sai nằm ngay trong chú thích của mã (đầu mỗi module trong `apps/` và `src/`). Nên đọc trước khi sửa phần lõi.

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| `apps/` | Máy chủ FastAPI (`web_stream.py`), cửa sổ desktop (`desktop_app.py`), quản lý mô hình, Supertonic, Kokoro |
| `src/vieneu/` | Engine VieNeu-TTS v3 Turbo / Nano (từ upstream VieNeu-TTS) |
| `src/vieneu_utils/` | Chuẩn hoá văn bản, chia câu, phụ đề, thẻ ngắt, từ điển phát âm |
| `app-desktop/cit-voice-app/` | Giao diện React |
| `scripts/` | Đóng gói và phát hành (PyInstaller, Inno Setup, .deb, .dmg) |
| `packaging/` | File đi kèm bộ cài từng hệ điều hành |
| `tests/` | Test Python (pytest) |

## Kiểm tra trước khi gửi pull request

```bash
uv run pytest                                  # toàn bộ test Python
cd app-desktop/cit-voice-app
npm run check                                  # Biome lint (lỗi chặn, cảnh báo thì nên sửa)
npm run typecheck
npm test
npm run build
```

Test không tải mô hình thật, nên chạy nhanh và không cần mạng.

## Quy ước

- **Ngôn ngữ:** comment, log và mọi chữ hiển thị cho người dùng viết bằng tiếng Việt; tên biến, hàm và API viết bằng tiếng Anh.
- **Lõi không cần PyTorch:** gói `vieneu` phải chạy được trên CPU mà không có torch. Không `import torch`, `transformers`, `librosa`... ở đầu file thuộc đường chạy CPU; đặt chúng bên trong hàm.
- **Giấy phép:** dự án theo Apache-2.0. Không đưa thư viện GPL vào bộ cài. Thư viện GPL (như espeak-ng cho Kokoro) chỉ được cài trên máy người dùng khi họ bấm Tải về. Thêm thư viện mới vào bộ cài thì cập nhật [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
- **Kết nối mạng:** app chạy offline. Mọi kết nối ra ngoài mới phải được ghi vào [PRIVACY.md](PRIVACY.md).
- **Âm thanh xuất ra:** mọi đường xuất file phải gắn nhãn "AI-generated" (xem `apps/ai_label.py`).
- **API:** endpoint chỉ giao diện dùng thì khai báo `include_in_schema=False`. Endpoint công khai thì cập nhật cả `docs/cit-voice-studio.md`.
- **Commit:** theo dạng `feat: ...`, `fix: ...`, `docs: ...`, mô tả ngắn gọn bằng tiếng Việt hoặc tiếng Anh.

## Pull request

- Mỗi pull request giải quyết một việc.
- Mô tả: thay đổi gì, vì sao, đã kiểm tra thế nào. Thay đổi giao diện thì kèm ảnh chụp.
- Thêm hoặc sửa test cho phần logic bạn thay đổi.

Khi gửi đóng góp, bạn đồng ý để phần đóng góp được phát hành theo giấy phép [Apache-2.0](LICENSE) của dự án.
