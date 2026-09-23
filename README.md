# CIT Voice Studio

Chuyển văn bản tiếng Việt thành giọng nói, chạy hoàn toàn trên máy bạn.

Không cần tài khoản. Không cần Internet sau khi cài. Không có dữ liệu nào gửi đi khỏi máy.

<p align="center">
  <img src="assets/tts-studio.png" alt="Giao diện CIT Voice Studio — chọn giọng, gắn tag cảm xúc, tạo giọng nói" width="900">
</p>

---

## Tải về

**[⬇ Tải CIT-Voice-Studio-Setup.exe](../../releases/latest)** — một file, bấm đúp là cài.

| | |
|---|---|
| Dung lượng tải | ~350 MB |
| Sau khi cài | ~763 MB |
| Yêu cầu | Windows 10/11 64-bit |
| Internet | chỉ cần để tải file này |

Mô hình giọng nói đã nằm sẵn trong bộ cài. Cài xong dùng được ngay, không phải tải thêm, cấu hình mô hình khác tại cài đặt.

### Cách cài

1. Tải file `CIT-Voice-Studio-Setup.exe`
2. Bấm đúp, làm theo hướng dẫn và cài đặt


Cài xong sẽ có biểu tượng ngoài Desktop và trong Start Menu.

**Gỡ ra:** Settings → Apps → CIT Voice Studio → Uninstall.

---

## Tính năng

- **20 giọng mẫu** — nam và nữ, giọng Bắc, Trung, Nam, nhiều phong cách: tin tức, kể chuyện, đọc truyện, tự nhiên
- **Nhân bản giọng nói** từ một đoạn mẫu 3–8 giây
- **Hội thoại / Podcast** nhiều người nói trong cùng một kịch bản
- **Đọc file PDF và TXT**
- **Chèn cảm xúc** ngay trong câu: `[cười]`, `[thở dài]`, `[hắng giọng]`
- **Đọc tiếng Anh xen tiếng Việt** — tự nhận ra và đọc đúng
- Chỉnh tốc độ đọc 0.75x – 1.50x
- Xuất **WAV** hoặc **MP3**, chất lượng 48 kHz
---

## Máy yếu có chạy được không?

Được. Phần mềm chạy bằng CPU, không cần card đồ hoạ.

Đo trên laptop Intel i7-8650U đời 2017: đọc một đoạn dài 1 phút mất khoảng 30 giây. Máy mới hơn nhanh hơn.
---

## Kết nối từ phần mềm khác

Khi ứng dụng đang chạy, nó mở sẵn một máy chủ API ở `http://127.0.0.1:8001`. Phần mềm khác **trên cùng máy** gọi vào được để tạo giọng nói tự động.

Các đường dẫn chính:

| Method | Đường dẫn | Việc |
|---|---|---|
| `GET` | `/health` | Trạng thái máy chủ |
| `GET` | `/voices` | Danh sách 20 giọng |
| `POST` | `/api/tts/generate` | Văn bản thành WAV/MP3 |
| `POST` | `/api/tts/clone` | Nhân bản giọng từ mẫu |
| `POST` | `/api/tts/conversation` | Hội thoại nhiều người |
| `POST` | `/stream` | Đọc theo thời gian thực |
| `POST` | `/api/pdf/extract` | Rút văn bản từ PDF |

Tài liệu đầy đủ, bấm thử được ngay: mở `http://127.0.0.1:8001/docs` trong trình duyệt khi ứng dụng đang chạy. Nhập cả bộ vào Postman bằng link `http://127.0.0.1:8001/openapi.json`.

Xem thêm trong **Cài đặt → Kết nối từ ứng dụng khác (API)** ngay trong ứng dụng.

Máy chủ chỉ lắng nghe ở `127.0.0.1` nên máy khác trong mạng LAN không gọi vào được. Đây là chủ ý: API không có lớp xác thực.

---

## Lỗi thường gặp

**Windows chặn không cho mở**
Chuột phải file `.exe` → Properties → tích **Unblock** → OK.

**Ứng dụng mở bằng trình duyệt thay vì cửa sổ riêng**
Không phải lỗi, mọi tính năng vẫn dùng được. Máy thiếu **Microsoft Edge WebView2 Runtime** nên ứng dụng tự chuyển sang trình duyệt.

Muốn có cửa sổ riêng thì cài WebView2 Runtime — miễn phí, của Microsoft:
<https://go.microsoft.com/fwlink/p/?LinkId=2124703>

Windows 11 có sẵn. Windows 10 thường có nếu đã cài Edge mới; bản LTSC hay máy mới cài lại hay thiếu.

**Chọn mô hình FP32 thì báo lỗi**
Bộ cài chỉ kèm mô hình INT8. FP32 phải tải thêm khoảng 453 MB nên cần Internet ở lần chọn đầu.

**Mục chọn mô hình bị làm mờ**
Máy không chạy được mô hình đó. Di chuột vào sẽ thấy lý do.

**Báo lỗi cổng 8001 đang bị chiếm**
Đóng hẳn ứng dụng rồi mở lại. Vẫn lỗi thì khởi động lại máy.

---

## Xem các mẫu tạo video có thể tích hợp TTS tại:

- Link repo tạo video so sánh 2 khái niệm: 🔗 [github.com/Cuongyd196/auto-compare-video](https://github.com/Cuongyd196/auto-compare-video)
- Link repo tạo video từ 1 đường Link/Bài viết: 🔗 [github.com/Cuongyd196/auto-video-gen](https://github.com/Cuongyd196/auto-video-gen)
- Link repo tạo video từ 1 chủ đề sử dụng Remotion: 🔗 [github.com/Cuongyd196/remotion-cuongit-template](https://github.com/Cuongyd196/remotion-cuongit-template)
- Link các video mẫu mình đã làm, các bạn có thể xem trong Reels hoặc TikTok:
  - 📹 Facebook: [www.facebook.com/cuongit96/reels/](https://www.facebook.com/cuongit96/reels/)
  - 📹 TikTok: [www.tiktok.com/@cuongit96](https://www.tiktok.com/@cuongit96)

Nếu hữu ích với các bạn thì cho mình 1 star GitHub nhé 🌟

Nếu muốn ủng hộ mình 1 ly cà phê: [buymeacoffee.com/cuongit96/gallery/4959449](https://buymeacoffee.com/cuongit96/gallery/4959449)

---

## Nguồn gốc

CIT Voice Studio do **Cường IT** phát triển, dựa trên **VieNeu-TTS** của tác giả **Phạm Nguyễn Ngọc Bảo**.

Phần cập nhật của Cường IT là giao diện người dùng và đóng gói thành app cit-voice-studio.

| | |
|---|---|
| Mô hình gốc | [pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) |
| Mô hình trên Hugging Face | [pnnbao-ump/VieNeu-TTS](https://huggingface.co/pnnbao-ump/VieNeu-TTS) |
| Tác giả bản này | [me.cuongit.net](https://me.cuongit.net) |

---

## Giấy phép

Apache License 2.0