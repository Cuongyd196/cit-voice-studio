# CIT Voice Studio

Chuyển văn bản tiếng Việt thành giọng nói, chạy hoàn toàn trên máy bạn.

Không cần tài khoản. Không cần Internet sau khi cài. Không có dữ liệu nào rời khỏi máy.

---

## Tải về

**[⬇ Tải CIT-Voice-Studio-Setup.exe](../../releases/latest)** — một file, bấm đúp là cài.

| | |
|---|---|
| Dung lượng tải | ~347 MB |
| Sau khi cài | ~763 MB |
| Yêu cầu | Windows 10/11 64-bit |
| Internet | chỉ cần để tải file này |

Mô hình giọng nói đã nằm sẵn trong bộ cài. Cài xong dùng được ngay, không phải tải thêm.

### Cách cài

1. Tải file `CIT-Voice-Studio-Setup.exe`
2. Bấm đúp, làm theo hướng dẫn


Cài vào thư mục riêng của tài khoản bạn nên **không hiện cảnh báo đòi quyền quản trị**. Xong sẽ có biểu tượng ngoài Desktop và trong Start Menu.

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
- Nghe ngay trong lúc đang tạo, không phải chờ xong mới nghe được

---

## Máy yếu có chạy được không?

Được. Phần mềm chạy bằng CPU, không cần card đồ hoạ.

Đo trên laptop Intel i7-8650U đời 2017: đọc một đoạn dài 1 phút mất khoảng 30 giây. Máy mới hơn nhanh hơn.

Máy có card NVIDIA cũng không cần làm gì thêm — bản CPU đã đủ nhanh cho hầu hết nhu cầu.

---

## Kết nối từ phần mềm khác

Khi ứng dụng đang chạy, nó mở sẵn một máy chủ API ở `http://127.0.0.1:8001`. Phần mềm khác **trên cùng máy** gọi vào được để tạo giọng nói tự động.

```python
import json, urllib.request

body = json.dumps({
    "text": "Xin chào từ ứng dụng khác",
    "voice_id": "Minh Đức",
    "speed": 1.0,
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8001/api/tts/generate",
    data=body,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as r:
    open("giong-noi.wav", "wb").write(r.read())
```

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

**Gặp lỗi khác**
Trong thư mục cài đặt có sẵn `chan-doan.bat`. Bấm đúp vào đó, nó tạo file `chan-doan.txt` ghi lại cấu hình máy và nhật ký lần chạy gần nhất. Gửi file đó kèm mô tả lỗi.

---

## Nguồn gốc

CIT Voice Studio do **Cường IT** phát triển, dựa trên **VieNeu-TTS** của tác giả **Phạm Nguyễn Ngọc Bảo**.

Toàn bộ mô hình trí tuệ nhân tạo và thuật toán tổng hợp giọng nói là công trình nghiên cứu của tác giả VieNeu-TTS. Phần đóng góp của Cường IT là giao diện người dùng, đóng gói và phân phối.

| | |
|---|---|
| Mô hình gốc | [pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) |
| Mô hình trên Hugging Face | [pnnbao-ump/VieNeu-TTS](https://huggingface.co/pnnbao-ump/VieNeu-TTS) |
| Tác giả bản này | [me.cuongit.net](https://me.cuongit.net) |

---

## Giấy phép

Apache License 2.0. Xem toàn văn trong file [LICENSE](LICENSE) và phần ghi công trong [NOTICE](NOTICE).

Bạn được tự do sử dụng cho mục đích cá nhân, học tập, nghiên cứu và thương mại; được sửa đổi và phân phối lại. Điều kiện là giữ nguyên thông báo bản quyền của tác giả.

Phần mềm được cung cấp theo nguyên trạng, không kèm bảo đảm dưới bất kỳ hình thức nào.
