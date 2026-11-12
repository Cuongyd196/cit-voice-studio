# CIT Voice Studio - Hướng Dẫn Kết Nối API & Tích Hợp AI Agent

> **Phiên bản ứng dụng**: `1.0.6` (OpenAPI dùng cùng phiên bản ứng dụng)
> **Địa chỉ mặc định**: `http://127.0.0.1:8001` (hoặc `http://localhost:8001`)  
> **Mục đích tài liệu**: Cung cấp đặc tả API đầy đủ, chính xác, kèm mã nguồn mẫu để **AI Agent** (Cursor, Claude, ChatGPT, LangChain, AutoGen, CrewAI, Open WebUI, Dify...) hoặc lập trình viên có thể đọc hiểu và tích hợp ngay lập tức mà không cần tài liệu bổ sung.

---

## 1. Tổng Quan Hệ Thống

**CIT Voice Studio** là nền tảng AI tổng hợp giọng nói tiếng Việt chất lượng phòng thu (Offline & On-Device), hỗ trợ:
- **Text-to-Speech (TTS)** qua luồng WAV. Độ trễ phụ thuộc mô hình và máy; Supertonic và Kokoro trả audio theo từng đoạn, không phải từng frame như Turbo ONNX.
- **Tần số lấy mẫu (Sample Rate)**: 48 kHz (VieNeu-TTS v3 Turbo), 24 kHz (VieNeu-TTS v3 Nano, Kokoro) hoặc 44,1 kHz (Supertonic 3). Với `/stream`, đọc header WAV hoặc `GET /health`; endpoint này không trả `X-Sample-Rate`. Các endpoint tạo file trả header `X-Sample-Rate`, còn endpoint phụ đề trả `sample_rate` trong JSON. Không gắn cứng tần số.
- **Giọng nước ngoài (từ 1.0.3)**: mô hình tải thêm **Supertonic 3** đọc 31 ngôn ngữ (Anh, Nhật, Hàn, Pháp, Đức…) bằng 10 giọng `F1`-`F5`, `M1`-`M5`. Mô hình tải thêm **Kokoro** đọc 8 ngôn ngữ (Anh, Tây Ban Nha, Pháp, Ý, Bồ Đào Nha, Hindi; Nhật, Trung khi đã thêm gói) bằng giọng bản xứ, **không đọc tiếng Việt**. Chọn ngôn ngữ qua tham số `language` (mục 3).
- **Thẻ cảm xúc (Emotion Tags)**: `[cười]`, `[hắng giọng]`, `[thở dài]`.
- **Dùng giọng nhân bản đã lưu**: trong ứng dụng, thu micro hoặc nhập MP3 của bạn/giọng được cho phép và xác nhận cam kết quyền sử dụng. Sau đó gọi API qua `voice_id`. Không có API nhân bản công khai từ file; giọng và cam kết chỉ lưu trên máy.
- **Hội thoại & Podcast đa nhân vật**: Ghép nối tự động các lượt thoại giữa nhiều nhân vật khác nhau.
- **Thẻ nghỉ `[nghỉ 2s]`**: Chèn khoảng lặng có độ dài chính xác, dùng được với mọi model.
- **Từ điển phát âm**: Cách đọc từ viết tắt / tên riêng người dùng đặt trong ứng dụng (`KTX` → "ký túc xá") được áp dụng tự động cho mọi API đọc văn bản.
- **Phụ đề SRT**: Tạo audio kèm phụ đề có mốc thời gian theo từng câu, dùng để dựng video.
- **CORS**: Cho phép gọi từ trình duyệt khác origin. Header đo thời lượng/tần số chưa được expose qua CORS; JavaScript khác origin nên đọc tần số từ `/health` hoặc header WAV.
- **Gọi từ máy khác (LAN)**: Mặc định chỉ máy chạy ứng dụng gọi được. Bật trong Cài đặt thì máy khác gọi được các API ở mục 4, bắt buộc kèm khoá API (xem mục 4.0).

---

## 2. Giọng Đọc Có Sẵn (Studio Presets)

Danh sách chính xác luôn lấy từ `GET /voices` (gồm cả giọng nhân bản người dùng đã lưu). `voice_id` là **tên giọng**, phân biệt dấu.

### Model VieNeu-TTS v3 Turbo (mặc định, 48 kHz) - 25 giọng

| ID / Tên giọng | Giới tính | Miền | Phong cách |
| :--- | :--- | :--- | :--- |
| `Hải Đăng` *(mặc định)* | Nam | Bắc | Tự nhiên |
| `Adam bựa` | Nam | Bắc | Tự nhiên |
| `Trúc Ly` | Nữ | Bắc | Tự nhiên |
| `Thiện Minh` | Nam | Bắc | Kể chuyện |
| `Mai Anh` | Nữ | Bắc | Tin tức |
| `Thùy Dung` | Nữ | Nam | Tin tức |
| `Thiền Tâm Đức` | Nam | Bắc | Kể chuyện |
| `Ngọc Huyền` | Nữ | Bắc | Tự nhiên |
| `Quang Sơn` | Nam | Trung | Tự nhiên |
| `Ngọc Trân` | Nữ | Trung | Tự nhiên |
| `Minh Đức` | Nam | Bắc | Tin tức |
| `Phạm Tuyên` | Nam | Bắc | Tự nhiên |
| `Thái Sơn` | Nam | Nam | Kể chuyện |
| `Xuân Vĩnh` | Nam | Bắc | Tự nhiên |
| `Thanh Bình` | Nam | Bắc | Kể chuyện |
| `Ngọc Linh` | Nữ | Bắc | Kể chuyện |
| `Đoan Trang` | Nữ | Bắc | Tự nhiên |
| `Thục Đoan` | Nữ | Nam | Kể chuyện |
| `Minh Triết` | Nam | Nam | Tin tức |
| `Mỹ Duyên` | Nữ | Nam | Đọc truyện |
| `Quỳnh Anh` | Nữ | Bắc | Đọc truyện |
| `Đức Trí` | Nam | Nam | Đọc truyện |
| `Kim Thanh` | Nữ | Nam | Đọc truyện |
| `Adam` | Nam | Nam | Tự nhiên |
| `Quốc Tuấn` | Nam | Bắc | Tự nhiên |

Tên cũ vẫn gọi được và tự chuyển sang giọng mới: `Minh Quân`, `Minh Quân Pro` → `Hải Đăng`; `Anh Khôi` → `Thiện Minh`; `Mạnh Dũng` → `Quốc Tuấn`.

### Model VieNeu-TTS v3 Nano (24 kHz) - 11 giọng

`Minh Quân` *(mặc định)*, `Anh Khôi`, `Mạnh Dũng`, `Hữu Quân`, `Đức Trí`, `Adam` (nam) · `Trúc Ly`, `Mai Anh`, `Xuân Tiên`, `Ái Hân`, `Mỹ Duyên` (nữ).

### Model Supertonic 3 (44,1 kHz, giọng nước ngoài) - 10 giọng

`F1` *(mặc định)*, `F2`, `F3`, `F4`, `F5` (nữ) · `M1`, `M2`, `M3`, `M4`, `M5` (nam). Giọng nào cũng đọc được mọi ngôn ngữ của model. Model này **không nhân bản giọng**. Người dùng phải tải nó trong ứng dụng (mục Mô hình) rồi chuyển sang; khi đó các giọng VieNeu ở trên trả lỗi `400`.

### Model Kokoro-82M (24 kHz, giọng nước ngoài) - 41 giọng (54 khi thêm tiếng Nhật, Trung)

Model tải thêm trong ứng dụng (bản CPU, và bản GPU NVIDIA), dành cho văn bản **không phải tiếng Việt**: tiếng Anh (Mỹ, Anh), Tây Ban Nha, Pháp, Ý, Bồ Đào Nha, Hindi, và tiếng Nhật, Trung nếu người dùng đã thêm gói ngôn ngữ. Mỗi giọng được huấn luyện cho một thứ tiếng: trường `language` của từng giọng trong `GET /voices` cho biết tiếng đó (`en`, `es`, `fr`, `it`, `pt`, `hi`, `ja`, `zh`). Giọng mặc định là `Heart` (tiếng Anh Mỹ). `voice_id` nhận tên hiển thị (`Heart`, `Siwis (FR)`, `Alpha (JA)`) hoặc mã gốc của Kokoro (`af_heart`). Model này **không nhân bản giọng** và không có thẻ cảm xúc.

- Mỗi giọng **luôn đọc theo tiếng của chính nó**; Kokoro **bỏ qua** `language` (mã hợp lệ vẫn được nhận, không lỗi). Muốn đọc tiếng nào thì chọn giọng của tiếng đó - nhờ vậy một hội thoại nhiều giọng nhiều thứ tiếng gửi chung một `language` vẫn đọc đúng từng lượt. Ngoại lệ: văn bản viết bằng chữ mà tiếng của giọng không đọc được (kana → tiếng Nhật, chữ Hán → tiếng Trung, Devanagari → Hindi) được đọc theo chữ nếu máy đã có thứ tiếng đó; giọng Nhật đọc chữ Hán như tiếng Nhật.
- Văn bản tiếng Việt bị từ chối với lỗi `400` (Kokoro không đọc được tiếng Việt, nếu không chặn sẽ ra audio đọc sai). Máy chủ xét theo tỉ lệ: từ 1/4 số từ viết thường trở lên có chữ chỉ tiếng Việt mới có (ă, đ, ơ, ư, ạ, ố…) thì coi là tiếng Việt. Tên riêng tiếng Việt trong câu tiếng nước ngoài ("We flew from Hà Nội to Đà Nẵng.") vẫn được.
- Thẻ nghỉ (`[nghỉ 1s]`, `[pause 1s]`) vẫn dùng được; thẻ cảm xúc bị bỏ qua; từ điển phát âm không áp dụng (xem mục 3).

Bỏ trống `voice_id` thì máy chủ dùng giọng mặc định của model đang chạy - cũng là giọng **đứng đầu** danh sách `GET /voices`. `voice_id` không có trong model đang chạy → lỗi `400` (báo ngay, trước khi đọc; ở `/api/tts/conversation` lỗi nêu tên người nói của lượt sai).

---

## 3. Quy Ước Văn Bản Đầu Vào

### Ngôn ngữ (`language`) - chỉ với model đọc nhiều ngôn ngữ

Các endpoint đọc văn bản (`/stream`, `/api/tts/generate`, `/api/tts/generate-with-subtitles`, `/api/tts/conversation`) nhận thêm `language` *(string, tuỳ chọn)*: mã ngôn ngữ như `"en"`, `"ja"`, `"ko"`, `"fr"`, `"de"`, `"vi"`… Danh sách mã của model đang chạy nằm trong `languages` của `GET /health` (rỗng với VieNeu).

- Bỏ trống: Supertonic tự nhận theo chữ - có dấu tiếng Việt → `vi`, chữ Nhật → `ja`, chữ Hàn → `ko`, còn lại `en`.
- Kokoro **luôn** đọc theo tiếng của giọng và bỏ qua `language` (mục 2); mã gửi lên vẫn phải có trong `/health`.
- Model VieNeu (chỉ tiếng Việt xen tiếng Anh) **bỏ qua** tham số này, nên phần mềm luôn gửi `language` vẫn chạy bình thường khi người dùng đổi model.
- Mã không có trong danh sách của model đang chạy → lỗi `400`.
- Tiếng Việt cho chất lượng tốt nhất trên VieNeu; Supertonic và Kokoro dùng cho văn bản tiếng nước ngoài. Kokoro không có mã `vi`: gửi văn bản tiếng Việt khi đang chạy Kokoro → lỗi `400`.

### Thẻ cảm xúc

Hỗ trợ trên model **VieNeu-TTS-v3-Turbo**. Supertonic 3 dùng thẻ riêng `<laugh>` (cười), `<breath>` (lấy hơi), `<sigh>` (thở dài); nó cũng nhận `[cười]`, `[thở dài]`, `[lấy hơi]` và bỏ qua `[hắng giọng]`. Kokoro không có thẻ cảm xúc: mọi thẻ bị bỏ qua (không đọc thành tiếng). Thẻ cảm xúc không hiện trong phụ đề SRT:
- `[cười]`: Thêm biểu cảm vui tươi, tiếng cười tự nhiên.
- `[hắng giọng]`: Thêm động tác hắng giọng, chuẩn bị nói hoặc ngắt nhịp trịnh trọng.
- `[thở dài]`: Thêm hơi thở dài, trầm ngâm hoặc thất vọng nhẹ.

*Ví dụ văn bản*: `"Xin chào cả nhà! Hôm nay tôi có tin rất vui. [cười] Dự án đã hoàn thành! [thở dài] Nhưng thật sự cũng khá vất vả."`

### Thẻ nghỉ `[nghỉ 2s]` - khoảng lặng có độ dài chính xác

Dùng được với **mọi model** và mọi endpoint đọc văn bản (`/stream`, `/api/tts/generate`, `/api/tts/generate-with-subtitles`, `/api/tts/conversation` - trong từng lượt thoại). Máy chủ tách văn bản tại thẻ, đọc từng đoạn rồi chèn đúng số giây im lặng; thẻ không bao giờ bị đọc thành tiếng.

- Cú pháp: `[nghỉ 2s]`, `[nghỉ 1.5s]`, `[nghỉ 1,5 giây]`, `[nghỉ 500ms]`, `[pause 2s]`, `[nghi 2]` (không ghi đơn vị = giây), `[nghỉ]` = 1 giây.
- Tối đa **10 giây** mỗi thẻ; hai thẻ liền nhau được cộng dồn. Thẻ viết sai (`[nghỉ abc]`) bị bỏ qua.
- Tham số `speed` chỉ đổi tốc độ giọng nói, không kéo giãn khoảng nghỉ.
- Văn bản chỉ có thẻ nghỉ mà không có chữ → lỗi `400`.
- Đoạn đứng trước thẻ được đọc như một câu riêng - đoạn quá ngắn (1–2 từ) có thể nghe hơi cụt.

*Ví dụ*: `"AI tạo sinh [nghỉ 2s] đang thay đổi mọi ngành."`

### Từ điển phát âm

Người dùng đặt cách đọc từ viết tắt / tên riêng ngay trong ứng dụng (nút **Từ điển** ở khung soạn thảo), ví dụ `KTX` → "ký túc xá". Máy chủ tự áp dụng cho `/stream`, `/api/tts/generate`, `/api/tts/generate-with-subtitles`, `/api/tts/conversation` - phần mềm gọi API không cần gửi thêm gì. Chỉ thay nguyên từ, mặc định phân biệt hoa/thường. Từ điển áp dụng cho mọi model đọc được tiếng Việt, kể cả Supertonic 3 (ví dụ `CIT` → `C I T`, `Nguyễn` → `Nwin` khi đọc tiếng Anh); dùng chung một bộ cho mọi ngôn ngữ. Kokoro không đọc tiếng Việt nên từ điển (viết theo cách đọc tiếng Việt) **không áp dụng** khi đang chạy Kokoro.

### Ghi nhãn nội dung do AI tạo ra

Mọi audio API trả về là giọng do AI tạo ra (Luật Trí tuệ nhân tạo 134/2025, Điều 11). Máy chủ đánh dấu sẵn ở dạng máy đọc được:

- Mọi phản hồi audio có header **`X-AI-Generated: true`**.
- File WAV/MP3 từ `/api/tts/*` mang thẻ `AI-generated` trong metadata (WAV: LIST/INFO, MP3: ID3). **Không xoá thẻ này** khi xử lý tiếp.
- Luồng `/stream` **không** có thẻ trong file (header WAV 44 byte giữ nguyên để client cũ không hỏng). Nếu lưu luồng thành file, phần mềm của bạn tự gắn thẻ hoặc ghi nhãn.

Khi phát hoặc đăng tải công khai cho người khác nghe, phần mềm gọi API (bên triển khai) phải cho người nghe biết đây là giọng AI, ví dụ một dòng **"Giọng đọc được tạo bằng AI"** trong giao diện, tiêu đề hoặc mô tả. Với chatbot hay trợ lý thoại, cho người dùng biết họ đang nghe giọng AI.

---

## 4. Chi Tiết Các Endpoint API

### 4.0. Xác Thực - Chỉ Khi Gọi Từ Máy Khác

- **Cùng máy** với ứng dụng (`127.0.0.1` / `localhost`): **không cần khoá**, gọi thẳng như các ví dụ bên dưới.
- **Máy khác trong mạng LAN**: trên máy chạy ứng dụng, mở **Cài đặt → Cho máy khác truy cập API**, bật lên rồi **đóng và mở lại ứng dụng** (lần đầu Windows hỏi quyền tường lửa: chọn *Cho phép* với mạng *Riêng tư*). Cài đặt hiện địa chỉ (`http://192.168.x.x:8001`) và khoá API.
- Gửi khoá qua header `X-API-Key: <khoá>` hoặc `Authorization: Bearer <khoá>`. Riêng thẻ `<audio src="...">` không gửi được header thì thêm `&api_key=<khoá>` vào URL `GET /stream`.
- Qua proxy / đường hầm (ngrok, Cloudflare Tunnel, nginx...) cũng bị coi là máy khác và cần khoá, kể cả khi proxy chạy trên cùng máy.
- Máy khác **chỉ** gọi được các API trong mục 4 và tài liệu (`/docs`, `/openapi.json`, `/cit-voice-studio.md`). Mọi đường dẫn khác trả `404`.
- Thử API trên trang `/docs` (Swagger) từ máy khác: bấm nút **Authorize**, dán khoá vào ô `ApiKey`.
- Khoá đi qua HTTP không mã hoá: chỉ dùng trong mạng tin cậy. Muốn đưa ra Internet, dùng đường hầm HTTPS thay vì mở cổng router.

```bash
curl.exe -H "X-API-Key: cit_xxxxxxxx" http://192.168.1.5:8001/health
```

Tài liệu này chỉ liệt kê các API dành cho **phần mềm khác gọi vào để tạo giọng nói**. Các API còn lại (lịch sử, quản lý mô hình, cài đặt, từ điển phát âm, lưu giọng nhân bản, đọc file...) phục vụ riêng giao diện của CIT Voice Studio, có thể thay đổi giữa các phiên bản và không nên dùng từ bên ngoài.

### 4.1. Kiểm Tra Trạng Thái Máy Chủ - `GET /health`
Kiểm tra kết nối, trạng thái tải mô hình, thiết bị phần cứng (CPU/GPU) và tần số lấy mẫu.

- **URL**: `http://127.0.0.1:8001/health`
- **Method**: `GET`
- **Response `200 OK` (JSON)**:
```json
{
  "status": "ok",
  "engine": "VieNeu-TTS-v3-Turbo (int8)",
  "sample_rate": 48000,
  "precision": "int8",
  "device": "cpu",
  "backend": "onnx",
  "message": "Sẵn sàng",
  "languages": [],
  "supports_cloning": true,
  "supports_emotions": true
}
```

`languages`: các mã dùng được cho tham số `language` (vd. `[{"code": "en", "name": "Tiếng Anh"}, …]` khi đang chạy Supertonic 3 hoặc Kokoro), rỗng với VieNeu. Danh sách có `vi` thì model đọc được tiếng Việt; Kokoro không có. `supports_emotions`: model có hiểu thẻ cảm xúc không (Kokoro: `false`). `supports_cloning`: mô hình có khả năng tạo giọng trong ứng dụng; **không có nghĩa là có API nhận file mẫu**. Chỉ sử dụng thông tin mô hình khi `status` là `ok`; trong lúc tải, thông tin có thể chưa phản ánh mô hình mới.

---

### 4.2. Danh Sách Giọng Đọc - `GET /voices`
Trả về toàn bộ giọng có sẵn (bao gồm giọng mặc định và giọng tuỳ chỉnh đã clone).

- **URL**: `http://127.0.0.1:8001/voices`
- **Method**: `GET`
- **Response `200 OK` (JSON Array)**:
```json
[
  {
    "id": "Minh Đức",
    "name": "Minh Đức",
    "gender": "male",
    "region": "North",
    "description": "Nam · Bắc · Phong cách tin tức · 48 kHz",
    "isCloned": false
  }
]
```

Giọng Kokoro có thêm `"language"` (vd. `"en"`, `"fr"`): tiếng mà giọng được huấn luyện; `region` là `null`.

---

### 4.3. Streaming TTS Thời Gian Thực - `GET /stream` hoặc `POST /stream`
Phương thức tối ưu nhất cho chatbot, trợ lý ảo và ứng dụng tương tác thoại.
Trả về luồng âm thanh dạng **WAV chunked**: 44 bytes đầu tiên là WAV header, các chunk tiếp theo là dữ liệu PCM16 phát ra tức thì khi GPU/CPU vừa tính toán xong.

#### A. Gọi qua `GET`:
- **URL**: `http://127.0.0.1:8001/stream?text=Xin+chào&voice_id=Minh+Đức`
- **Query Parameters**:
  - `text` *(string, bắt buộc)*: Nội dung cần đọc.
  - `voice_id` *(string, tuỳ chọn)*: Tên giọng (bỏ trống = giọng mặc định của model, xem mục 2).
  - `language` *(string, tuỳ chọn)*: Mã từ `/health` cho Supertonic, ví dụ `en`, `ja`; Kokoro đọc theo tiếng của giọng, VieNeu bỏ qua.
- **Response**: `audio/wav` (Streaming chunks)

#### B. Gọi qua `POST`:
- **URL**: `http://127.0.0.1:8001/stream`
- **Headers**: `Content-Type: application/json`
- **Request Body (JSON)**:
```json
{
  "text": "Xin chào các bạn, đây là luồng âm thanh thời gian thực.",
  "voice_id": "Minh Đức"
}
```

GET và POST `/stream` chỉ nhận `text`, `voice_id`, `language`; không nhận `speed`, `temperature`, `seed` hoặc `use_pronunciation_dict`. Từ điển phát âm luôn được áp dụng. Độ dài WAV trong header là giá trị dành cho streaming, không dùng để tính thời lượng cuối cùng. Phản hồi có header `X-AI-Generated: true`; luồng không mang thẻ AI trong file (xem mục "Ghi nhãn nội dung do AI tạo ra").

---

### 4.4. Tạo Audio Hoàn Chỉnh - `POST /api/tts/generate`
Tạo file âm thanh hoàn chỉnh với các thông số tuỳ biến chuyên sâu (tốc độ, độ dừng nghỉ, ngẫu nhiên hóa).

- **URL**: `http://127.0.0.1:8001/api/tts/generate`
- **Headers**: `Content-Type: application/json`
- **Request Body (JSON)**:
```json
{
  "text": "CIT Voice Studio mang đến giọng nói nhân tạo đỉnh cao.",
  "voice_id": "Mai Anh",
  "speed": 1.0,
  "temperature": 0.8,
  "silence_duration": 0.2,
  "format": "wav",
  "use_pronunciation_dict": true
}
```
*Ghi chú tham số*:
- `speed` *(float, mặc định 1.0)*: Hệ số tốc độ phải lớn hơn 0, khuyến nghị `0.75`–`1.5`. Chỉ đổi tốc độ giọng nói, không kéo giãn thẻ `[nghỉ Ns]`. API hiện không giới hạn sẵn khoảng giá trị này.
- `temperature` *(float, mặc định 0.8)*: Độ ngẫu nhiên của VieNeu v3 Turbo; giao diện cho chọn `0.1`–`1.5`. Nano, Supertonic và Kokoro bỏ qua tham số này.
- `silence_duration` *(float, mặc định 0.2)*: Được nhận nhưng **hiện chưa có tác dụng** ở endpoint này. Muốn chèn khoảng nghỉ, dùng thẻ `[nghỉ 2s]` trong `text`.
- `format` *(string, mặc định "wav")*: `"wav"` hoặc `"mp3"`. Nếu không mã hoá được MP3, `/generate` trả WAV; luôn kiểm tra `Content-Type` trước khi đặt đuôi file.
- `use_pronunciation_dict` *(bool, mặc định true)*: Áp dụng từ điển phát âm người dùng đặt trong ứng dụng (xem mục 3). Đặt `false` nếu phần mềm của bạn đã tự thay từ viết tắt trước khi gửi - thay hai lần có thể đọc sai.
- `seed` *(int, tuỳ chọn)*: Cố định độ ngẫu nhiên để tái tạo cách đọc với cùng văn bản, giọng, mô hình, thiết lập và môi trường. Có tác dụng với Supertonic; không tự làm giọng hay hơn. Không bảo đảm file giống từng byte giữa các phiên bản hoặc thiết bị. Cũng nhận ở `/api/tts/generate-with-subtitles` và `/api/tts/conversation`; `/stream` không nhận.
- `language` *(string, tuỳ chọn)*: Mã ngôn ngữ như mục 3, ví dụ `en` cho Supertonic đọc tiếng Anh.

> **Tạo hàng loạt**: không có endpoint riêng. Gọi `/api/tts/generate` lần lượt cho từng mục (máy chủ xử lý một yêu cầu một lúc, gọi song song không nhanh hơn). Tab "Tạo hàng loạt" trong ứng dụng làm đúng như vậy.

- **Response Headers**:
  - `X-Duration-Seconds`: Thời lượng audio (giây).
  - `X-Elapsed-Seconds`: Thời gian AI tạo audio (giây).
  - `X-RTF`: Real-Time Factor (nhỏ hơn 1 nghĩa là nhanh hơn thời gian thực).
  - `X-Sample-Rate`: Tần số âm thanh (48000, 24000 hoặc 44100 tuỳ mô hình).
- **Response Body**: Dữ liệu binary của file audio (`audio/wav` hoặc `audio/mpeg`).

---

### 4.5. Tạo Audio Kèm Phụ Đề SRT - `POST /api/tts/generate-with-subtitles`
Giống `/api/tts/generate` (cùng request body), nhưng trả **JSON** gồm audio + phụ đề `.srt` để dựng video.

Máy chủ đọc theo **từng câu** (gộp câu quá ngắn) và đo độ dài audio thật của mỗi câu, nên mốc thời gian chính xác tới mức câu. Phụ đề hiện **văn bản gốc** (chữ `KTX` chứ không phải cách đọc "ký túc xá" của từ điển), bỏ thẻ cảm xúc và thẻ nghỉ; câu dài được chia thành nhiều dòng phụ đề (tối đa 2 dòng × ~42 ký tự).

- **Response `200 OK` (JSON)**:
```json
{
  "audio_base64": "UklGRi...",
  "format": "wav",
  "sample_rate": 48000,
  "duration_seconds": 4.21,
  "elapsed_seconds": 2.05,
  "rtf": 0.487,
  "srt": "1\n00:00:00,000 --> 00:00:02,180\nHọc sinh nhận SGK tại KTX.\n",
  "cues": [{ "start": 0.0, "end": 2.18, "text": "Học sinh nhận SGK tại KTX." }]
}
```
*Ghi chú*: `audio_base64` là nội dung file WAV/MP3 mã hoá base64. Lưu `srt` thành file `.srt` **cùng tên** với file audio để phần mềm dựng video tự ghép. Chậm hơn `/api/tts/generate` một chút vì đọc từng câu riêng.

---

### 4.6. Dùng giọng nhân bản
API công khai **không nhận file giọng mẫu** (`POST /api/tts/clone` đã bỏ từ 1.0.2).
Tạo giọng trong ứng dụng, tab **Nhân bản giọng**, bằng micro (đọc nội dung bất kỳ,
khuyến nghị 3–8 giây) hoặc nhập MP3. Cả hai không cần ASR. Trước khi lưu, người
dùng xác nhận đây là giọng của mình hoặc đã được chủ giọng cho phép nhân bản và sử dụng.
Cam kết, thời điểm, nguồn mẫu và phiên bản điều khoản lưu cùng giọng trên máy; xoá
giọng xoá cả cam kết. Đây không phải xác minh danh tính. Sau đó các endpoint đọc văn
bản dùng giọng đã lưu qua `voice_id` (tên giọng, xem `GET /voices`).

Giọng đã lưu thuộc mô hình hỗ trợ giọng đó; sau khi đổi mô hình phải gọi lại `/voices`.
Supertonic 3 và Kokoro không tạo hoặc dùng giọng nhân bản VieNeu. Các route tạo giọng trong ứng dụng là API nội bộ, không dành cho tích hợp bên ngoài; `/api/tts/clone` và `/api/tts/clone-to-history` không còn hoạt động.

---

### 4.7. Tạo Podcast & Hội Thoại Đa Nhân Vật - `POST /api/tts/conversation`
Tự động phối hợp nhiều người nói khác nhau theo từng câu thoại và ghép thành một file podcast duy nhất.

- **URL**: `http://127.0.0.1:8001/api/tts/conversation`
- **Headers**: `Content-Type: application/json`
- **Request Body (JSON)**:
```json
{
  "turns": [
    {
      "speaker": "MC",
      "text": "Chào mừng quý vị đến với CIT Voice Studio Podcast!",
      "voice_id": "Minh Đức"
    },
    {
      "speaker": "Khách mời",
      "text": "Rất vui được có mặt trong chương trình ngày hôm nay.",
      "voice_id": "Trúc Ly"
    }
  ],
  "silence_duration": 0.4,
  "speed": 1.0,
  "format": "wav"
}
```
- `seed` *(int, tuỳ chọn)*: Như ở mục 4.4.
- Có thể dùng `script` thay `turns`: mỗi dòng dạng `[MC]: Xin chào`, kèm `speaker_mapping` như `{"MC": "Mai Anh"}`. Nếu `script` có nội dung thì được ưu tiên hơn `turns`.
- Thứ tự chọn giọng: `turns[].voice_id` → `speaker_mapping` → giọng mặc định của mô hình.
- `silence_duration`: khoảng nghỉ giữa lượt, mặc định 0.4 giây, thực tế tối thiểu 0.05 giây. Khác với tham số cùng tên không có tác dụng ở `/generate`.
- `temperature`, `speed`, `format`, `language`: như mục 4.4; `language` áp dụng chung cho mọi lượt. Từ điển phát âm luôn bật, không có cờ `use_pronunciation_dict` ở endpoint này.
- Header kết quả: `X-Duration-Seconds`, `X-Elapsed-Seconds`, `X-Turns-Count`, `X-Sample-Rate`; không có `X-RTF`.
- Nếu máy không mã hoá được MP3 thì trả WAV; kiểm tra `Content-Type` thực tế như ở `/generate`.
- **Response**: File âm thanh hoàn chỉnh ghép nối toàn bộ buổi hội thoại.

---

## 5. Hướng Dẫn Tích Hợp Cho Lập Trình Viên & AI Agent

### 5.1. Ví Dụ cURL Cơ Bản

#### Tạo giọng nói và lưu ra file `speech.wav`:
```bash
curl -X POST "http://127.0.0.1:8001/api/tts/generate" \
     -H "Content-Type: application/json" \
     -d '{"text": "Xin chào! Đây là giọng đọc từ CIT Voice Studio.", "voice_id": "Minh Đức"}' \
     --output speech.wav
```

#### Nghe stream trực tiếp:
```bash
curl "http://127.0.0.1:8001/stream?text=Xin+chào&voice_id=Mai+Anh" | ffplay -nodisp -autoexit -
```

#### Gọi từ máy khác trong mạng LAN (cần khoá - xem mục 4.0):
Thay IP và khoá bằng giá trị hiện trong **Cài đặt → Cho máy khác truy cập API**.

*cmd* của Windows (chạy `chcp 65001` trước để gửi đúng chữ có dấu; Linux/macOS dùng `curl` thay cho `curl.exe`):
```bash
curl.exe -X POST "http://192.168.1.5:8001/api/tts/generate" -H "X-API-Key: cit_xxxxxxxx" -H "Content-Type: application/json" -d "{\"text\": \"Xin chào từ máy khác\", \"voice_id\": \"Minh Đức\"}" --output speech.wav
```

*PowerShell* (gửi nội dung dạng UTF-8 để giữ dấu tiếng Việt):
```powershell
Invoke-WebRequest -Uri "http://192.168.1.5:8001/api/tts/generate" -Method Post -Headers @{ "X-API-Key" = "cit_xxxxxxxx" } -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes('{"text": "Xin chào từ máy khác", "voice_id": "Minh Đức"}')) -OutFile speech.wav
```

---

### 5.2. Mã Nguồn Mẫu Python Client Đầy Đủ

```python
import requests
from pathlib import Path

class CitVoiceStudio:
    def __init__(self, base_url: str = "http://127.0.0.1:8001", api_key: str | None = None):
        """api_key: chỉ cần khi gọi từ máy khác (lấy trong Cài đặt của ứng dụng)."""
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()
        if api_key:
            self.http.headers["X-API-Key"] = api_key

    def check_health(self) -> dict:
        """Kiểm tra máy chủ và model hiện hành."""
        res = self.http.get(f"{self.base_url}/health", timeout=5)
        res.raise_for_status()
        return res.json()

    def get_voices(self) -> list:
        """Lấy danh sách tất cả các giọng đọc."""
        res = self.http.get(f"{self.base_url}/voices", timeout=5)
        res.raise_for_status()
        return res.json()

    def speak(self, text: str, voice_id: str | None = None, speed: float = 1.0, out_path: str = "output.wav", language: str | None = None) -> str:
        """Tạo file giọng nói hoàn chỉnh."""
        payload = {
            "text": text,
            "voice_id": voice_id,
            "speed": speed,
            "format": "wav",
            "language": language,
        }
        res = self.http.post(f"{self.base_url}/api/tts/generate", json=payload, timeout=(5, 1800))
        res.raise_for_status()
        Path(out_path).write_bytes(res.content)
        print(f"✅ Đã lưu: {out_path} (RTF: {res.headers.get('X-RTF')})")
        return out_path

# --- Sử dụng ---
if __name__ == "__main__":
    client = CitVoiceStudio()  # cùng máy: không cần khoá
    # Máy khác: client = CitVoiceStudio("http://192.168.1.5:8001", api_key="cit_xxxxxxxx")
    health = client.check_health()
    if health["status"] != "ok":
        raise SystemExit(f"Mô hình chưa sẵn sàng: {health.get('message', '')}")
    print("Giọng của mô hình đang chạy:", client.get_voices())
    client.speak("Xin chào các bạn, CIT Voice Studio đã sẵn sàng phục vụ!")
```

---

### 5.3. Mã Nguồn Mẫu JavaScript / TypeScript (Node.js hoặc Browser)

```typescript
export class CitVoiceStudioClient {
  /** apiKey: chỉ cần khi gọi từ máy khác (lấy trong Cài đặt của ứng dụng). */
  constructor(
    private baseUrl: string = "http://127.0.0.1:8001",
    private apiKey?: string
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return this.apiKey ? { ...extra, "X-API-Key": this.apiKey } : extra;
  }

  async getVoices() {
    const res = await fetch(`${this.baseUrl}/voices`, { headers: this.headers() });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  }

  async generateSpeech(text: string, voiceId?: string, speed: number = 1.0, language?: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/api/tts/generate`, {
      method: "POST",
      headers: this.headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        text,
        voice_id: voiceId,
        speed,
        format: "wav",
        language,
      }),
    });
    if (!res.ok) throw new Error(`Tạo giọng thất bại: ${res.statusText}`);
    return await res.blob();
  }

  /** Dùng cho <audio src>: thẻ này không gửi được header nên khoá đi qua URL. */
  getStreamUrl(text: string, voiceId?: string, language?: string): string {
    const params = new URLSearchParams({ text });
    if (voiceId) params.set("voice_id", voiceId);
    if (language) params.set("language", language);
    if (this.apiKey) params.set("api_key", this.apiKey);
    return `${this.baseUrl}/stream?${params.toString()}`;
  }
}
```

---

### 5.4. Tích Hợp Vào Các Framework AI Agent (LangChain / Dify / Function Calling)

Định dạng JSON Schema chuẩn cho các mô hình ngôn ngữ lớn (OpenAI / Gemini / Anthropic Tool Calling):

```json
{
  "name": "generate_vietnamese_speech",
  "description": "Chuyển đổi văn bản tiếng Việt thành giọng nói tự nhiên thông qua CIT Voice Studio local API.",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "description": "Đoạn văn bản tiếng Việt cần đọc. Có thể chèn tag cảm xúc như [cười], [hắng giọng], [thở dài]."
      },
      "voice_id": {
        "type": "string",
        "description": "id từ GET /voices của mô hình đang chạy. Bỏ trống dùng giọng mặc định; không gắn cứng giọng VieNeu khi đang chạy Supertonic."
      },
      "speed": {
        "type": "number",
        "description": "Tốc độ nói từ 0.75 đến 1.5, mặc định 1.0."
      }
    },
    "required": ["text"]
  }
}
```

---

## 6. Xử Lý Lỗi Thường Gặp (Troubleshooting)

1. **Lỗi `503 Model not loaded`**:
   - *Nguyên nhân*: Server vừa bật hoặc đang tải model.
   - *Cách khắc phục*: Gọi `GET /health` đợi cho tới khi `"status": "ok"` rồi tiếp tục gửi request TTS.

2. **Lỗi `400 Voice '...' not found`**:
   - *Nguyên nhân*: Tên giọng đọc truyền vào không khớp với danh sách trả về từ `GET /voices`.
   - *Cách khắc phục*: Gọi `GET /voices` để lấy đúng danh sách tên chuẩn (hỗ trợ Unicode tiếng Việt có dấu).

3. **Lỗi kết nối `Failed to fetch` hoặc `Connection Refused`**:
   - *Nguyên nhân*: Ứng dụng CIT Voice Studio chưa mở hoặc backend đang chạy ở cổng khác.
   - *Cách khắc phục*: Kiểm tra ứng dụng đang mở, mở `http://127.0.0.1:8001/health` để xác minh cổng hoạt động. Gọi từ máy khác mà bị từ chối kết nối: kiểm tra đã bật truy cập từ máy khác, đã mở lại ứng dụng, và tường lửa Windows cho phép ứng dụng.

4. **Lỗi `401` / `403` / `404` khi gọi từ máy khác** (xem mục 4.0):
   - `401`: thiếu hoặc sai khoá API - lấy lại khoá trong Cài đặt (khoá đổi khi bấm *Khoá mới*).
   - `403`: tính năng cho máy khác truy cập đang tắt.
   - `404`: đường dẫn không nằm trong danh sách API công khai.

5. **Lỗi `400` "Mô hình đang dùng (Kokoro) không đọc được tiếng Việt"**:
   - *Nguyên nhân*: Ứng dụng đang để model Kokoro (giọng nước ngoài) mà văn bản gửi lên là tiếng Việt.
   - *Cách khắc phục*: Trong ứng dụng, vào **Cài đặt → Quản lý & Chọn Mô hình AI**, chọn lại VieNeu-TTS v3 Turbo. Phần mềm gọi vào có thể kiểm tra trước bằng `GET /health`: `languages` rỗng hoặc có `vi` thì đọc được tiếng Việt.

---

*Tài liệu dành cho CIT Voice Studio 1.0.6. Kiểm tra `/openapi.json` của ứng dụng đang chạy để đối chiếu phiên bản và các tham số.*
