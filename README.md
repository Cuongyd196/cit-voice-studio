<div align="center">

<img src="assets/brand/cit-logo.png" width="104" alt="Logo CIT Voice Studio">

# CIT Voice Studio

**Chuyển văn bản tiếng Việt thành giọng nói tự nhiên, ngay trên máy tính của bạn.**

Không cần tài khoản · Không cần Internet sau khi cài · Văn bản và giọng nói không rời khỏi máy

[![Phiên bản mới nhất](https://img.shields.io/github/v/release/Cuongyd196/cit-voice-studio?label=phi%C3%AAn%20b%E1%BA%A3n&color=0f766e)](../../releases/latest)
[![Lượt tải](https://img.shields.io/github/downloads/Cuongyd196/cit-voice-studio/total?label=l%C6%B0%E1%BB%A3t%20t%E1%BA%A3i&color=0f766e)](../../releases)
![Windows · Linux · macOS](https://img.shields.io/badge/Windows%20%C2%B7%20Linux%20%C2%B7%20macOS-334155)
![Chạy offline](https://img.shields.io/badge/ch%E1%BA%A1y-offline-16a34a)
![Giấy phép Apache 2.0](https://img.shields.io/badge/gi%E1%BA%A5y%20ph%C3%A9p-Apache%202.0-64748b)

**[⬇ Tải về](#tải-về)** &nbsp;·&nbsp; **[Tính năng](#tính-năng)** &nbsp;·&nbsp; **[API](#kết-nối-từ-phần-mềm-khác-api)** &nbsp;·&nbsp; **[Lỗi thường gặp](#lỗi-thường-gặp)** &nbsp;·&nbsp; **[☕ Ủng hộ](#ủng-hộ)**

💖 Muốn ủng hộ để Cường phát triển thêm, xem thông tin tại **[cuongit.net/donate](https://cuongit.net/donate)**.

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/giao-dien-toi.png">
  <img src="assets/giao-dien-sang.png" alt="Giao diện CIT Voice Studio 1.0.4: soạn văn bản, gắn thẻ cảm xúc, chọn giọng đọc và tạo giọng nói" width="920">
</picture>

</div>

<br>

| 🎙️ **25 giọng tiếng Việt** | 🧬 **Nhân bản giọng** | 🌍 **Giọng nước ngoài** |
|---|---|---|
| Nam, nữ, ba miền Bắc - Trung - Nam; tin tức, kể chuyện, đọc truyện… Âm thanh 48 kHz. | Thu micro 3–8 giây hoặc nhập file MP3/WAV/M4A để tạo giọng của riêng bạn. | Tải thêm Supertonic 3 (31 ngôn ngữ, 10 giọng) hoặc Kokoro (41 giọng bản xứ: Anh, Pháp, Nhật, Trung…). |
| 🎧 **Podcast, hội thoại** | 🎬 **Lồng tiếng theo phụ đề** | 🔌 **API cho phần mềm khác** |
| Mỗi nhân vật một giọng, ghép thành một file audio. | Thả file `.srt`, giọng đọc khớp đúng mốc thời gian của video. | Gọi từ script, phần mềm khác hay AI Agent qua `http://127.0.0.1:8001`. |

### Có gì mới ở 1.0.6

- **Mã nguồn mở** theo giấy phép Apache-2.0. Ai cũng xem, góp ý và đóng góp được: xem [CONTRIBUTING.md](CONTRIBUTING.md).
- **Giọng bản xứ với Kokoro**: 41 giọng tiếng Anh, Tây Ban Nha, Pháp, Ý, Bồ Đào Nha, Hindi, thêm tiếng Nhật và tiếng Trung. Tải trong **Cài đặt → Mô hình**.
- **Chọn giọng mở sẵn** khi mở ứng dụng (**Cài đặt → Giọng đọc**).
- **Chạy làm máy chủ** trên Linux, kể cả bằng Docker: xem [Chạy trên máy chủ](#chạy-trên-máy-chủ-không-màn-hình).
- Sửa lỗi: cài đè lên bản cũ không còn làm ứng dụng báo "Không mở được server nội bộ"; tuỳ chọn "Ổn định" ẩn với mô hình không dùng đến.

Chi tiết từng phiên bản: [trang Releases](../../releases).

---

## Tải về

**[⬇ Trang tải về (Releases)](../../releases/latest)** - chọn đúng file cho máy của bạn:

| Máy của bạn | File tải | Dung lượng |
|---|---|---|
| Windows 10/11 64-bit | `CIT-Voice-Studio-v1.0.6-win-x86_64.exe` | ~367 MB |
| Linux 64-bit: Ubuntu, Debian, Linux Mint… | `CIT-Voice-Studio-v1.0.6-amd64.deb` | ~460 MB |
| Mac chip Apple (M1, M2, M3…, arm64), macOS 14 trở lên | `CIT-Voice-Studio-v1.0.6-macos-arm64.dmg` | ~428 MB |
| Mac chip Intel (x86_64), macOS 13 trở lên | `CIT-Voice-Studio-v1.0.6-macos-x86_64.dmg` | ~443 MB |

Mọi bản đều kèm sẵn mô hình giọng nói: cài xong dùng được ngay, không cần Internet, dữ liệu lưu trực tiếp trên máy bạn.

### Cấu hình máy

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| Hệ điều hành | Windows 10/11 64-bit, Ubuntu/Debian 64-bit, macOS 14 (chip Apple) hoặc macOS 13 (chip Intel) | như bên trái |
| CPU | 4 nhân | 6 nhân trở lên |
| RAM | 8 GB | 16 GB trở lên |
| Ổ đĩa trống | 3 GB | 5 GB |
| Card đồ hoạ | Không cần | Card NVIDIA nếu hay tạo bài dài (xem [Chọn mô hình theo máy](#chọn-mô-hình-theo-máy)) |

Tốc độ thử nghiệm: máy Intel Core i7 thế hệ 8 (4 nhân) - 10 phút audio mất khoảng 5 phút.

**Mỗi lần tạo nên bao nhiêu ký tự?**

- **Bản 1.0.1 trở lên (Windows, Linux, macOS):** không giới hạn. Ứng dụng ghi audio dần ra ổ đĩa nên bài dài không tốn thêm RAM - đã thử văn bản ~84.000 ký tự (~2 giờ audio), ứng dụng chỉ dùng khoảng 1 GB RAM. Chỉ cần đủ thời gian và ổ đĩa trống: mỗi giờ audio WAV khoảng 330 MB. Bài vài giờ nên chia theo chương, tạo từng chương hoặc sử dụng tab **Tạo hàng loạt**, để lỡ gián đoạn không phải làm lại từ đầu, và dễ sửa từng phần.
- **Bản 1.0.0:** văn bản quá dài có thể làm ứng dụng báo lỗi bộ nhớ hoặc trắng màn hình. Tuỳ cấu hình máy, có thể tham khảo:

| RAM | Mỗi lần tạo, khoảng | Tương đương audio |
|---|---|---|
| 8 GB | 15.000 ký tự | ~20 phút |
| 16 GB | 40.000 ký tự | ~1 giờ |
| 32 GB trở lên | 60.000 ký tự | ~1 giờ 30 phút |

Đây là mức ước tính an toàn, nên thấp hơn nữa nếu đang mở nhiều ứng dụng khác. Bài dài hơn thì chia thành nhiều phần, hoặc dùng tab **Tạo hàng loạt** để mỗi phần thành một file riêng. 

### Windows

1. Tải file `CIT-Voice-Studio-v1.0.6-win-x86_64.exe`.
2. Bấm đúp và làm theo hướng dẫn. Bộ cài không đòi quyền quản trị (Administrator).
3. Mở ứng dụng từ biểu tượng ngoài Desktop hoặc trong Start Menu.

> **Nếu hiện màn hình xanh "Windows protected your PC"** thì đây là điều bình thường, không phải virus: bộ cài chưa mua chữ ký số (code signing) nên Windows chưa "quen" ứng dụng. Bấm dòng chữ **More info** (Thông tin thêm), rồi bấm nút **Run anyway** (Vẫn chạy) hiện ra ở dưới. Chỉ làm vậy với file tải từ [trang Releases](../../releases/latest) chính thức. Windows hiện thông báo khác thì xem [Lỗi thường gặp](#lỗi-thường-gặp).

**Gỡ cài đặt:** Settings → Apps → CIT Voice Studio → Uninstall.

### Linux

Cài file `.deb` (Ubuntu, Debian, Linux Mint và các bản dựa trên Debian):

```bash
sudo apt install ./CIT-Voice-Studio-v1.0.6-amd64.deb
```

Mở bằng mục **CIT Voice Studio** trong menu ứng dụng, hoặc gõ `cit-voice-studio` trong Terminal. Gỡ: `sudo apt remove cit-voice-studio`.

Trên Linux, ứng dụng chạy trong một cửa sổ Terminal và mở giao diện bằng trình duyệt tại `http://127.0.0.1:8001`. Giữ Terminal mở trong lúc dùng; đóng Terminal hoặc bấm `Ctrl+C` để tắt.

### macOS

1. Mở file `.dmg`, kéo **CIT Voice Studio** vào thư mục **Applications**.
2. Lần đầu mở, macOS chặn vì ứng dụng chưa được Apple chứng thực: vào **System Settings → Privacy & Security**, kéo xuống cuối, bấm **Open Anyway**.
3. Ứng dụng có cửa sổ riêng; tắt bằng `Cmd+Q`.

Chọn đúng file theo chip của máy: menu  → **About This Mac**, dòng **Chip** ghi "Apple M…" thì tải bản `arm64`, dòng **Processor** ghi "Intel" thì tải bản `x86_64`.

Bản Linux và macOS có file `HUONG-DAN.txt` đi kèm, hướng dẫn chi tiết.

---

## Tính năng

### Tạo giọng nói
- **25 giọng có sẵn**: nam và nữ, giọng Bắc, Trung, Nam, nhiều phong cách (tin tức, kể chuyện, đọc truyện, tự nhiên…). Danh sách chọn giọng ghi rõ giới tính, vùng miền và phong cách.
- **Nghe thử từng giọng** ngay trong danh sách trước khi chọn.
- **Đọc tiếng Anh xen tiếng Việt**: tự nhận ra từ tiếng Anh và đọc đúng.
- Chỉnh tốc độ đọc từ 0.75x đến 1.50x.
- Xuất **WAV** hoặc **MP3**; tần số theo mô hình: Turbo 48 kHz, Nano 24 kHz, Supertonic 44,1 kHz, Kokoro 24 kHz.

### Điều khiển cách đọc
- **Thẻ cảm xúc** chèn ngay trong câu: `[cười]`, `[thở dài]`, `[hắng giọng]`.
- **Thẻ nghỉ** tạo khoảng lặng dài đúng như ý: `[nghỉ 2s]`, `[nghỉ 500ms]` (tối đa 10 giây mỗi thẻ).
- **Từ điển phát âm**: tự đặt cách đọc cho từ viết tắt hay tên riêng mà máy đọc sai, ví dụ `KTX` → "ký túc xá", `SGK` → "sách giáo khoa". Mở bằng nút **Từ điển** trên khung soạn thảo; từ điển được lưu lại và dùng cho mọi lần tạo giọng.
- Từ 1.0.4: **nhập/xuất từ điển bằng file CSV** (mở được bằng Excel, có file mẫu để tải về) và chia trang khi từ điển dài.

### Giọng nước ngoài (mới ở 1.0.3)
- Tải thêm mô hình **Supertonic 3** (~400 MB) trong **Cài đặt → Mô hình** để đọc **31 ngôn ngữ**: Anh, Nhật, Hàn, Pháp, Đức, Tây Ban Nha, Nga, Ả Rập… (chưa có tiếng Trung) với 10 giọng nam nữ.
- Chọn tiếng của đoạn văn ở ô **Ngôn ngữ văn bản** (mặc định **Tiếng Anh**, hoặc **Tự nhận theo văn bản**). Nút nghe thử giọng cũng đọc câu mẫu bằng tiếng đó. Dùng được ở mọi tab: TTS Studio, hội thoại, tạo hàng loạt, lồng tiếng theo phụ đề.
- Chạy bằng CPU, không cần cài gì thêm, có trên cả Windows, Linux và macOS. Tiếng Việt vẫn nên dùng VieNeu (chất lượng tốt hơn); mô hình này không nhân bản giọng.
- **10 giọng dùng chung cho cả 31 ngôn ngữ** (5 nữ F1–F5, 5 nam M1–M5). Chất giọng theo mô tả của Supertone:

| Giọng | Chất giọng | Hợp với |
|---|---|---|
| F1 (nữ) | Điềm tĩnh, hơi trầm | Chăm sóc khách hàng, thiền |
| F2 (nữ) | Tươi sáng, tinh nghịch | Mạng xã hội, nội dung giới trẻ |
| F3 (nữ) | Rõ ràng, kiểu phát thanh viên | Tin tức, thông báo |
| F4 (nữ) | Dứt khoát, tự tin | Giới thiệu doanh nghiệp, đào tạo |
| F5 (nữ) | Dịu dàng, êm | Sách nói, lời động viên |
| M1 (nam) | Năng động, trong | Quảng cáo, thông báo |
| M2 (nam) | Trầm, điềm đạm | Doanh nghiệp, phim tài liệu |
| M3 (nam) | Chỉn chu, đáng tin | Thuyết trình, phát biểu |
| M4 (nam) | Nhẹ nhàng, thân thiện | Giáo dục, thiếu nhi |
| M5 (nam) | Ấm, êm dịu | Sách nói, kể chuyện |

- **31 ngôn ngữ:** Anh, Việt, Nhật, Hàn, Pháp, Đức, Tây Ban Nha, Bồ Đào Nha, Ý, Nga, Indonesia, Hindi, Ả Rập, Thổ Nhĩ Kỳ, Hà Lan, Ba Lan, Ukraina, Thuỵ Điển, Đan Mạch, Phần Lan, Hy Lạp, Séc, Slovakia, Hungary, Romania, Bulgaria, Croatia, Slovenia, Estonia, Latvia, Litva.
- **Chất lượng:** mô hình khoảng 99 triệu tham số, âm thanh 44,1 kHz. Theo Supertone, độ chính xác khi đọc (WER/CER) ngang các mô hình mở lớn hơn nhiều lần, và ít lỗi lặp/bỏ chữ hơn Supertonic 2. Đo trên laptop Core i7-8650U: tiếng Anh tạo nhanh hơn thời gian đọc; tiếng Việt không nhanh hơn VieNeu và đọc chậm hơn khoảng 2 lần, nên tiếng Việt vẫn nên dùng VieNeu. Supertone đã ngừng phát triển mô hình này (kho mã được lưu trữ), nên sẽ không có bản cập nhật.
- **Thẻ cảm xúc** riêng của mô hình: `<laugh>` (cười), `<breath>` (lấy hơi), `<sigh>` (thở dài), chèn bằng thanh cảm xúc. Thẻ nghỉ `[nghỉ 2s]` dùng như bình thường.
- **Từ điển phát âm** dùng được như với VieNeu, tiện để sửa tên riêng, viết tắt mà mô hình đọc sai, ví dụ `CIT` → `C I T`, `Nguyễn` → `Nwin`, `km` → `kilometers`. Từ điển dùng chung cho mọi mô hình đọc được tiếng Việt.

### Giọng bản xứ với Kokoro (mới ở 1.0.6)
- Tải thêm mô hình **Kokoro** trong **Cài đặt → Mô hình** (~350 MB, lần đầu ứng dụng tự cài thêm bộ tách âm khoảng 22 MB) để có **41 giọng bản xứ**: tiếng Anh (Mỹ, Anh), Tây Ban Nha, Pháp, Ý, Bồ Đào Nha, Hindi. Tiếng Nhật (~52 MB, chiếm ~250 MB trên ổ đĩa) và tiếng Trung (~25 MB) thêm bằng nút ngay dưới dòng Kokoro. Âm thanh 24 kHz.
- Mỗi giọng là người bản xứ của một thứ tiếng; chọn giọng thì ô **Ngôn ngữ văn bản** tự chuyển sang tiếng đó. Giọng tiếng Anh tốt nhất; các thứ tiếng khác ít giọng hơn.
- **Không đọc tiếng Việt**, không nhân bản giọng, không có thẻ cảm xúc; từ điển phát âm (viết theo cách đọc tiếng Việt) không áp dụng. Thẻ nghỉ dùng như bình thường.
- Máy có card NVIDIA chọn **Kokoro (GPU NVIDIA)** để đọc văn bản dài nhanh hơn (cần cài hỗ trợ GPU như v3 Turbo GPU).
- Bộ tách âm của Kokoro (có phần giấy phép GPL) **không nằm trong bộ cài**: máy bạn tự tải từ PyPI khi bấm Tải về, vào thư mục `addons/` riêng. Trên macOS chưa dùng được.

### Nhân bản giọng nói
- Chọn **Thu micro** (đọc nội dung bất kỳ bằng giọng tự nhiên khoảng 3–8 giây) hoặc **Nhập file âm thanh** (MP3, WAV hoặc M4A; WAV và M4A có từ 1.0.4) có giọng nói rõ, một người nói, không nhạc nền. Không cần đọc câu cam kết. Ứng dụng giữ tối đa 15 giây từ tiếng nói đầu tiên; Turbo dùng tối đa 8 giây có tiếng.
- Chỉ dùng giọng của bạn hoặc giọng đã được chủ giọng cho phép nhân bản và sử dụng. Phải xác nhận quyền sử dụng trước khi lưu; đây là cam kết, không phải xác minh danh tính.
- Giọng và cam kết lưu trên máy, xoá cùng nhau; không gửi về tác giả, không tự sao chép file âm thanh gốc. Cả micro và file âm thanh không cần bộ nhận dạng câu đồng ý.
- Lưu giọng đã nhân bản để dùng lại, và xoá khi không cần nữa.

### Hội thoại / Podcast
- Viết kịch bản nhiều nhân vật, mỗi nhân vật một giọng; ứng dụng ghép thành một file audio.

### Đọc file
- Lấy văn bản từ **PDF, Word (.docx) và TXT**.
- Thả file phụ đề **.srt** vào để lồng tiếng theo mốc thời gian (xem mục dưới).
- Nút **Làm sạch** bỏ khoảng trắng thừa, gạch đầu dòng và chỗ xuống dòng giữa câu, nhưng giữ nguyên công thức như `1 + 1`.

### Tạo hàng loạt
- Đặt mốc `[P1]`, `[P2]`… ở đầu dòng: mỗi mốc thành **một file audio riêng**.
- Nhập trực tiếp hoặc tải lên file TXT. Có sẵn file mẫu để tải về.
- Tải từng file, hoặc tải tất cả trong một file **.zip**.

### Phụ đề cho video
- Tạo audio kèm **phụ đề .srt**, mốc thời gian khớp theo từng câu. Dùng thẳng trong CapCut, Premiere, DaVinci Resolve…

### Lồng tiếng theo phụ đề (mới ở 1.0.2)
Đã có sẵn file phụ đề của video (tự gõ, xuất từ CapCut/Premiere, hoặc dịch từ phụ đề tiếng nước ngoài)? Ứng dụng đọc từng câu **đúng mốc thời gian** và ra một file audio để ghép thẳng vào video.

1. Mở tab **Đọc file**, thả file `.srt` (hoặc `.vtt`) vào. Ứng dụng hiện danh sách câu kèm mốc thời gian.
2. Chọn giọng (giọng có sẵn hoặc giọng bạn đã nhân bản) và tốc độ đọc, bấm **Lồng tiếng**.
3. Xong: nghe thử, tải **WAV/MP3**. File audio dài đúng bằng video, câu nào nằm đúng mốc câu đó. Bản lồng tiếng được lưu vào **Bản đã tạo**.

- Câu dài hơn khoảng thời gian của nó được **đọc nhanh hơn cho vừa** (tối đa 1,5 lần). Vẫn chưa vừa thì lấn sang khoảng lặng phía sau, hoặc đẩy câu sau lùi lại một chút. **Không bao giờ cắt chữ.**
- Khi có câu bị lùi, ứng dụng kèm **file phụ đề đã chỉnh mốc** để chữ trên video khớp với giọng đọc.
- Tự bỏ thẻ định dạng trong phụ đề (`<i>`, `{\an8}`…) và áp dụng từ điển phát âm.
- Mẹo: câu bị đọc nhanh hoặc bị lùi nhiều thì giảm tốc độ đọc, hoặc rút gọn câu trong file phụ đề.

### Bản đã tạo
- Các bản đã tạo được lưu trên máy và **còn nguyên sau khi tắt ứng dụng**: nghe lại, tải lại WAV/MP3/SRT, mở thư mục chứa file.
- Không tự xoá bản nào. Tab Bản đã tạo hiện số bản, dung lượng và nhắc dọn bớt khi chiếm nhiều ổ đĩa.

---

## Cú pháp nhanh

| Viết trong văn bản | Kết quả |
|---|---|
| `Tin vui [cười] cho cả nhà.` | Cười ngay tại chỗ đó |
| `Phần một. [nghỉ 2s] Phần hai.` | Im lặng đúng 2 giây giữa hai phần |
| `[P1]` … `[P2]` … | Tab **Tạo hàng loạt**: tách thành nhiều file |

---

## Chọn mô hình theo máy

Đổi mô hình trong **Cài đặt → Quản lý & Chọn Mô hình AI**. Mô hình nào máy không chạy được sẽ bị làm mờ, di chuột vào để xem lý do. Từ 1.0.3, ứng dụng nhớ mô hình bạn chọn: lần mở sau dùng lại đúng mô hình đó (nếu mô hình bị xoá hoặc lỗi thì quay về mô hình mặc định).

| Máy của bạn | Nên dùng | Ghi chú |
|---|---|---|
| Máy thường, laptop văn phòng, **máy yếu** | **v3 Turbo INT8** (mặc định) | Có sẵn trong bộ cài. Nhanh nhất khi chạy bằng CPU, âm thanh 48 kHz |
| Máy có **card NVIDIA** (Windows, Linux) | **v3 Turbo GPU NVIDIA** | Bấm **Cài hỗ trợ GPU** ngay tại mô hình đó |
| Muốn thử mô hình nhỏ | v3 Nano (thử nghiệm) | Tải thêm ~400 MB, âm thanh 24 kHz, đọc tiếng Anh kém hơn |
| Đọc văn bản **tiếng nước ngoài** bằng giọng bản xứ | **Kokoro** | Tải thêm ~350 MB; Anh, Tây Ban Nha, Pháp, Ý, Bồ Đào Nha, Hindi, thêm Nhật/Trung. Không đọc tiếng Việt; chưa có trên macOS |
| Cần ngôn ngữ Kokoro không có (Hàn, Đức, Nga…) | **Supertonic 3** | Tải thêm ~400 MB, 31 ngôn ngữ, 10 giọng dùng chung |

**Máy yếu có chạy được không?** Được. Ứng dụng chạy bằng CPU, không cần card đồ hoạ. Đo trên laptop Intel Core i7-8650U (2017, 4 nhân) với mô hình mặc định: đoạn đọc dài 1 phút mất khoảng 30 giây để tạo. Máy mới hơn sẽ nhanh hơn.

Máy yếu cứ giữ **Turbo INT8**. Nano nhỏ hơn nhưng **không nhanh hơn**: trên cùng laptop đó, Nano ở cài đặt mặc định chậm gần gấp đôi Turbo INT8.

**Máy có card NVIDIA:** không có bộ cài riêng cho GPU, vẫn dùng bộ cài như trên. Trong ứng dụng, vào **Cài đặt → Quản lý & Chọn Mô hình AI**, bấm **Cài hỗ trợ GPU** ở mô hình GPU NVIDIA. Ứng dụng tự tải PyTorch/CUDA (vài GB, cần ít nhất 12 GB trống, chỉ tải một lần). Máy cần cài sẵn driver NVIDIA (kiểm tra bằng lệnh `nvidia-smi`). Lợi rõ nhất là khi tạo một đoạn dài sẽ thấy sự khác biệt. macOS chỉ chạy CPU.

---

## Kết nối từ phần mềm khác (API)

Khi ứng dụng đang mở, nó chạy sẵn một máy chủ API ở `http://127.0.0.1:8001`. Phần mềm khác, script hay AI Agent gọi vào đó để tạo giọng nói tự động.

| Method | Đường dẫn | Việc |
|---|---|---|
| `GET` | `/health` | Trạng thái máy chủ |
| `GET` | `/voices` | Danh sách giọng đọc |
| `GET` `POST` | `/stream` | Đọc theo thời gian thực |
| `POST` | `/api/tts/generate` | Văn bản thành WAV/MP3 |
| `POST` | `/api/tts/generate-with-subtitles` | Audio kèm phụ đề .srt |
| `POST` | `/api/tts/conversation` | Hội thoại nhiều người nói |

Thẻ cảm xúc, thẻ nghỉ và từ điển phát âm đều dùng được qua API.

API chỉ dùng giọng có sẵn hoặc giọng nhân bản đã lưu qua `voice_id` từ `/voices`.
Tạo giọng trong ứng dụng bằng micro hoặc nhập file âm thanh kèm cam kết quyền sử dụng, rồi dùng giọng đã lưu qua API. Không mở lại các endpoint `/api/tts/clone` và `/api/tts/clone-to-history`. Supertonic chỉ có giọng sẵn.

Ví dụ nhanh (Python):

```python
import requests

r = requests.post(
    "http://127.0.0.1:8001/api/tts/generate",
    json={"text": "Xin chào từ phần mềm khác.", "voice_id": "Minh Đức"},
)
open("giong-noi.wav", "wb").write(r.content)
```

**Tài liệu đầy đủ:**
- `http://127.0.0.1:8001/docs`: bấm thử từng API ngay trong trình duyệt.
- `http://127.0.0.1:8001/cit-voice-studio.md`: hướng dẫn tích hợp dạng Markdown, nạp thẳng cho Cursor, Claude, ChatGPT…
- `http://127.0.0.1:8001/openapi.json`: nhập vào Postman.
- [docs/postman/CIT-Voice-Studio.postman_collection.json](docs/postman/CIT-Voice-Studio.postman_collection.json): bộ request Postman dựng sẵn, sửa biến `baseUrl` và `apiKey` là dùng.

### Gọi từ máy khác trong mạng LAN

Mặc định chỉ phần mềm **trên cùng máy** gọi được API, và không cần khoá.

Muốn máy khác gọi vào:
1. Mở **Cài đặt → Cho máy khác truy cập API**, tích bật.
2. Bấm **Khởi động lại ngay**. Lần đầu, Windows hỏi quyền tường lửa: chọn **Cho phép** với mạng **Riêng tư**. Trên Linux có bật tường lửa thì chạy `sudo ufw allow 8001/tcp`.
3. Lấy địa chỉ (dạng `http://192.168.x.x:8001`) và **khoá API** hiện ngay trong Cài đặt.
4. Máy khác gửi khoá qua header `X-API-Key`:

```bash
curl.exe -H "X-API-Key: <khoá>" http://192.168.1.5:8001/health
```

Máy khác chỉ gọi được các API tạo giọng ở bảng trên; không xem được các bản đã tạo hay cài đặt. Bấm **Khoá mới** để thu hồi khoá cũ ngay lập tức.

> ⚠️ Chỉ bật trong mạng tin cậy. Khoá đi qua HTTP không mã hoá. Muốn đưa ra Internet, hãy dùng đường hầm HTTPS (Cloudflare Tunnel, ngrok) thay vì mở cổng trên router.

### Chạy trên máy chủ (không màn hình)

Dùng khi muốn một máy Linux chạy suốt ngày làm máy chủ giọng nói cho các máy khác. Chạy từ mã nguồn, không cần cửa sổ ứng dụng.

**1. Cài đặt** (Ubuntu 22.04/24.04, cần `git`; Node 20+ nếu muốn có giao diện):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # cài uv, mở lại terminal
git clone https://github.com/Cuongyd196/cit-voice-studio && cd cit-voice-studio
uv sync                                             # chạy bằng CPU
# uv sync --group gpu-app                           # hoặc: có card NVIDIA (driver ≥ 570, tải thêm ~3,5 GB)
cd app-desktop/cit-voice-app && npm ci && npm run build && cd ../..   # giao diện (bỏ qua nếu chỉ dùng API)
```

**2. Chạy thử:**

```bash
uv run vieneu-stream        # cổng 8001, Ctrl+C để dừng
```

Lần đầu, máy chủ tải mô hình VieNeu (~312 MB, bản GPU ~1 GB) vào `models/hf_cache/` trong thư mục mã nguồn. Có card NVIDIA thì tự dùng GPU. Đổi cổng bằng biến `PORT` (ví dụ `PORT=9000 uv run vieneu-stream`).

**3. Cho máy khác gọi API.** Mặc định máy chủ chỉ nhận request từ chính nó. Bật bằng cách sửa file `~/CitVoiceStudio/remote-access.json` (khởi động một lần ở bước 2 để file tự tạo kèm khoá):

```bash
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path.home() / "CitVoiceStudio" / "remote-access.json"
d = json.loads(p.read_text()); d["enabled"] = True; p.write_text(json.dumps(d))
print("Khoá API:", d["api_key"])
EOF
sudo ufw allow 8001/tcp     # nếu có bật tường lửa
```

Khởi động lại máy chủ để nó nghe trên mọi địa chỉ (`0.0.0.0`), rồi gọi như mục [Gọi từ máy khác trong mạng LAN](#gọi-từ-máy-khác-trong-mạng-lan).

**4. Dùng giao diện của máy chủ.** Máy khác chỉ gọi được API tạo giọng, không mở được giao diện. Muốn quản lý (tải thêm mô hình, nhân bản giọng, xem lịch sử, đổi khoá), mở đường hầm SSH từ máy của bạn rồi vào `http://127.0.0.1:8001`:

```bash
ssh -L 8001:127.0.0.1:8001 user@<ip-máy-chủ>
```

Qua đường hầm, máy chủ coi bạn như đang ngồi tại chỗ nên không cần khoá. Nút **Khởi động lại ngay** trong Cài đặt không dùng được ở chế độ này: sau khi đổi cổng hay bật/tắt truy cập từ xa, khởi động lại bằng lệnh (bước 5).

**5. Tự chạy khi bật máy** (systemd, không cần quyền root):

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/cit-voice-studio.service <<EOF
[Unit]
Description=CIT Voice Studio
After=network-online.target

[Service]
WorkingDirectory=$PWD
ExecStart=$(command -v uv) run --no-sync vieneu-stream
Restart=on-failure

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now cit-voice-studio
sudo loginctl enable-linger $USER          # chạy cả khi chưa đăng nhập
journalctl --user -u cit-voice-studio -f   # xem log
```

Khởi động lại: `systemctl --user restart cit-voice-studio`. Cập nhật: `git pull`, chạy lại `uv sync` (cùng nhóm đã chọn ở bước 1) và `npm run build`, rồi khởi động lại.

Muốn đưa ra Internet, đặt máy chủ sau đường hầm HTTPS (Cloudflare Tunnel, Tailscale) thay vì mở cổng router; request qua đường hầm luôn bị coi là từ xa nên vẫn phải có khoá.

### Chạy bằng Docker

Thay cho các bước 1, 2 và 5 ở trên. Cần Docker Engine trên Linux, kèm plugin compose. Container dùng mạng của máy chủ (`network_mode: host`) để phân biệt request từ chính máy chủ với request từ máy khác, nên không chạy đúng trên Docker Desktop của Windows/macOS.

```bash
git clone https://github.com/Cuongyd196/cit-voice-studio && cd cit-voice-studio
C="docker compose -f packaging/docker/compose.yaml"
$C up -d --build            # build lần đầu vài phút
$C logs -f                  # chờ dòng "Sẵn sàng"
```

**Có card NVIDIA:** cài driver ≥ 570 và [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), kiểm tra bằng `docker run --rm --gpus all ubuntu nvidia-smi`, rồi thêm file GPU vào lệnh:

```bash
C="docker compose -f packaging/docker/compose.yaml -f packaging/docker/compose.gpu.yaml"
$C up -d --build            # ảnh GPU nặng hơn ~3,5 GB
```

- Ảnh không chứa mô hình. Lần chạy đầu, app tải mô hình vào volume `cit-data` (`/data`). Volume này giữ cả lịch sử, cài đặt, khoá API, từ điển và giọng nhân bản, nên build lại hay xoá container không mất gì.
- Container tự chạy lại khi bật máy (`restart: unless-stopped`), không cần systemd.
- Mở giao diện: trên chính máy chủ vào `http://127.0.0.1:8001`, hoặc từ máy khác qua đường hầm SSH như bước 4. Lần đầu phải đồng ý điều khoản trong giao diện.
- Đổi cổng: bỏ comment dòng `PORT` trong `packaging/docker/compose.yaml`.

Bật cho máy khác gọi API (thay cho bước 3) rồi khởi động lại:

```bash
$C exec app python -c "
import json, pathlib
p = pathlib.Path('/data/CitVoiceStudio/remote-access.json')
d = json.loads(p.read_text()); d['enabled'] = True; p.write_text(json.dumps(d))
print('Khoá API:', d['api_key'])"
$C restart
```

Lệnh thường dùng:

```bash
$C ps                           # trạng thái, có kiểm tra sức khoẻ
$C restart                      # khởi động lại (thay cho nút trong Cài đặt)
git pull && $C up -d --build    # cập nhật
$C down                         # dừng; thêm -v sẽ XOÁ luôn dữ liệu trong volume
```

---

## Dữ liệu được lưu ở đâu

Mọi thứ nằm trên máy bạn:

| Hệ điều hành | Thư mục |
|---|---|
| Windows | `%LOCALAPPDATA%\CitVoiceStudio\` |
| Linux | `~/CitVoiceStudio/` |
| macOS | `~/Library/Application Support/CIT Voice Studio/` |

Trong đó:

| Thư mục / file | Nội dung |
|---|---|
| `history\` | Các bản audio và phụ đề đã tạo |
| `pronunciation-dict.json` | Từ điển phát âm |
| `remote-access.json` | Cài đặt truy cập từ máy khác và khoá API |
| `server-settings.json` | Cổng máy chủ |
| `ui-prefs.json` | Giao diện sáng/tối, tự phát sau khi tạo, tốc độ phát |
| `save-settings.json` | Thư mục lưu file, mở file sau khi lưu |

Trên Windows, mô hình và giọng nhân bản nằm trong thư mục `models` cạnh ứng dụng; bộ tách âm của Kokoro và hỗ trợ GPU (nếu bạn cài) nằm trong `addons` và `gpu_venv`, cũng cạnh ứng dụng, và được xoá khi gỡ. Linux và macOS để chúng trong thư mục dữ liệu ở bảng trên. Cập nhật lên bản mới không làm mất dữ liệu.

---

## Lỗi thường gặp

**Windows chặn không cho mở**
Bộ cài chưa được ký số (code signing), nên Windows có thể cảnh báo. Tuỳ thông báo:

- *"Windows protected your PC"* (màn hình xanh SmartScreen): bấm **More info** → **Run anyway**.
- File bị đánh dấu tải từ Internet: chuột phải vào file `.exe` → Properties → tích **Unblock** → OK.
- *"Smart App Control blocked an app that may be unsafe"* (Windows 11): Smart App Control chặn mọi ứng dụng chưa ký số và **không cho mở riêng từng ứng dụng**, nên Unblock hay Run anyway đều không có tác dụng. Cách duy nhất là tắt tính năng này: **Windows Security → App & browser control → Smart App Control settings → Off**.
  > ⚠️ Tắt Smart App Control làm giảm một lớp bảo vệ của Windows, và trên nhiều bản Windows **không bật lại được** nếu không cài lại Windows. Chỉ tắt khi bạn tin nguồn tải về (trang Release chính thức của repo này). Không muốn tắt thì hãy cài trên máy khác.

**macOS: "không thể mở vì không xác minh được nhà phát triển"**
Vào **System Settings → Privacy & Security**, bấm **Open Anyway**. Hoặc chạy trong Terminal:

```bash
xattr -dr com.apple.quarantine "/Applications/CIT Voice Studio.app"
```

**macOS: ứng dụng không mở trên máy cũ**
Cần macOS 14 Sonoma trở lên.

**Linux: giao diện không tự mở**
Mở trình duyệt và vào `http://127.0.0.1:8001`. Giữ cửa sổ Terminal của ứng dụng đang mở.

**Windows: ứng dụng mở bằng trình duyệt thay vì cửa sổ riêng**
Không phải lỗi, mọi tính năng vẫn dùng được. Máy thiếu **Microsoft Edge WebView2 Runtime** nên ứng dụng tự chuyển sang trình duyệt. Muốn có cửa sổ riêng thì cài WebView2 Runtime (miễn phí, của Microsoft):
<https://go.microsoft.com/fwlink/p/?LinkId=2124703>

Windows 11 có sẵn. Windows 10 thường có nếu đã cài Edge bản mới; bản LTSC hoặc máy mới cài lại hay thiếu.

**Chọn mô hình FP32 thì báo lỗi**
Bộ cài chỉ kèm mô hình INT8. FP32 phải tải thêm khoảng 453 MB, nên lần chọn đầu tiên cần Internet.

**Mục chọn mô hình bị làm mờ**
Máy không chạy được mô hình đó. Di chuột vào để xem lý do.

**Tải Kokoro báo lỗi**
Lần đầu, ứng dụng tải mô hình từ Hugging Face rồi tải bộ tách âm từ PyPI, nên cần Internet và không bị chặn hai trang đó (mạng công ty, proxy). Phần mềm diệt virus đôi khi khoá file vừa tải: bấm Tải về lần nữa là được, phần đã tải xong không phải tải lại.

**Báo lỗi cổng 8001 đang bị chiếm**
Đóng hẳn ứng dụng rồi mở lại. Vẫn lỗi thì đổi cổng trong **Cài đặt → Cổng server**, hoặc khởi động lại máy.

**Máy khác không gọi được API**
- Kết nối bị từ chối: kiểm tra đã bật **Cho máy khác truy cập API**, đã khởi động lại ứng dụng, và tường lửa Windows cho phép ứng dụng.
- `401`: thiếu hoặc sai khoá.
- `403`: tính năng đang tắt.
- `404`: đường dẫn không nằm trong danh sách API công khai.

**Máy đọc sai một từ viết tắt**
Thêm từ đó vào **Từ điển** với cách đọc mong muốn, ví dụ `KTX` → `ký túc xá`.

---

## Dự án tạo video có thể dùng kèm

- Tạo video so sánh 2 khái niệm: 🔗 [github.com/Cuongyd196/auto-compare-video](https://github.com/Cuongyd196/auto-compare-video)
- Tạo video từ một đường link / bài viết: 🔗 [github.com/Cuongyd196/auto-video-gen](https://github.com/Cuongyd196/auto-video-gen)
- Tạo video từ một chủ đề bằng Remotion: 🔗 [github.com/Cuongyd196/remotion-cuongit-template](https://github.com/Cuongyd196/remotion-cuongit-template)
- Các video mẫu mình đã làm, xem trong Reels hoặc TikTok:
  - 📹 Facebook: [www.facebook.com/cuongit96/reels/](https://www.facebook.com/cuongit96/reels/)
  - 📹 TikTok: [www.tiktok.com/@cuongit96](https://www.tiktok.com/@cuongit96)


Muốn ủng hộ mình 1 ly cà phê: [buymeacoffee.com/cuongit96](https://buymeacoffee.com/cuongit96)

---

## Nguồn gốc

CIT Voice Studio do **Cường IT** phát triển. Ứng dụng dùng ba mô hình giọng nói của bên thứ ba:

- **VieNeu-TTS** của tác giả **Phạm Nguyễn Ngọc Bảo** - giọng tiếng Việt, nhân bản giọng; kèm sẵn trong bộ cài. Đây là nền tảng của CIT Voice Studio.
- **Supertonic 3** của **Supertone Inc.** - giọng nước ngoài 31 ngôn ngữ; chỉ tải khi bạn chọn (từ 1.0.3).
- **Kokoro-82M** của **hexgrad** (Apache-2.0) - giọng bản xứ 8 ngôn ngữ; chỉ tải khi bạn chọn.

Các mô hình giọng nói là của tác giả của chúng. Phần Cường IT làm là ứng dụng: giao diện, bổ sung một số tính năng và bộ cài cho Windows, Linux và macOS.

Xin cảm ơn tác giả Phạm Nguyễn Ngọc Bảo đã xây dựng và chia sẻ VieNeu-TTS, Supertone đã công bố Supertonic, và hexgrad đã công bố Kokoro.

| | |
|---|---|
| VieNeu-TTS (mã nguồn) | [pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) |
| VieNeu-TTS trên Hugging Face | [pnnbao-ump/VieNeu-TTS](https://huggingface.co/pnnbao-ump/VieNeu-TTS) |
| Supertonic (mã nguồn) | [supertone-oss-archive/supertonic](https://github.com/supertone-oss-archive/supertonic) |
| Supertonic 3 trên Hugging Face | [supertone-oss-archive/supertonic-3](https://huggingface.co/supertone-oss-archive/supertonic-3) |
| Kokoro (mã nguồn) | [hexgrad/kokoro](https://github.com/hexgrad/kokoro) |
| Kokoro-82M trên Hugging Face | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) |
| Tác giả bản này | [me.cuongit.net](https://me.cuongit.net) |

---

## Sử dụng có trách nhiệm

- **Chỉ nhân bản giọng của bạn hoặc giọng đã được cho phép.** Bạn phải có quyền sử dụng bản ghi và dùng giọng đúng phạm vi được đồng ý; ứng dụng không xác minh danh tính hoặc chứng nhận quyền sở hữu giọng.
- **Không giả mạo giọng người khác** (người thân, người nổi tiếng, cán bộ, cơ quan, doanh nghiệp…) để lừa đảo, vay mượn tiền, bôi nhọ, xúc phạm hay gây hiểu lầm.
- **Tôn trọng bản quyền:** văn bản (sách, truyện, báo) phải là của bạn hoặc đã được phép sử dụng.
- Khi đăng tải công khai nội dung mô phỏng giọng người thật, **phải ghi rõ "giọng đọc được tạo bằng AI"**.

Khi cài và mở ứng dụng lần đầu, bạn cần đồng ý [Điều khoản sử dụng](DIEU-KHOAN.md). Người dùng tự chịu trách nhiệm trước pháp luật về nội dung mình tạo ra. Tác giả CIT Voice Studio, VieNeu-TTS, Supertone và Kokoro không chịu trách nhiệm với việc sử dụng sai mục đích.

CIT Voice Studio là ứng dụng độc lập, **không phải sản phẩm chính thức của VieNeu-TTS, Supertone hay Kokoro**.

---

## Ủng hộ

CIT Voice Studio luôn miễn phí. Nếu thấy hữu ích và muốn ủng hộ tác giả làm tiếp, bạn có thể (hoàn toàn tự nguyện):

| Cách ủng hộ | Link |
|---|---|
| 💖 Mọi cách ủng hộ | [cuongit.net/donate](https://cuongit.net/donate) |
| ☕ Visa / PayPal | [buymeacoffee.com/cuongit96](https://buymeacoffee.com/cuongit96) |
| 🏦 Chuyển khoản ngân hàng Việt Nam (mã QR) | [Xem mã QR](https://buymeacoffee.com/cuongit96/gallery/5234541) |
| 💖 GitHub Sponsors | [github.com/sponsors/Cuongyd196](https://github.com/sponsors/Cuongyd196) |

Góp ý, báo lỗi hay chia sẻ ứng dụng cho người cần cũng là một cách ủng hộ rất lớn. Cảm ơn bạn!

---

## Giấy phép

Apache License 2.0 - © Cường IT, dựa trên VieNeu-TTS © Phạm Nguyễn Ngọc Bảo.

Mô hình Supertonic 3 © Supertone Inc., giấy phép **OpenRAIL-M**: được dùng cả mục đích thương mại, nhưng cấm mạo danh người khác khi chưa được đồng ý, lừa đảo, tin giả gây hại, đăng nội dung do AI tạo mà không ghi rõ… (xem [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)). Mô hình không nằm trong bộ cài; file giấy phép tải kèm khi bạn tải mô hình. Giấy phép gốc của Supertone:

- Mô hình: [OpenRAIL-M](https://huggingface.co/supertone-oss-archive/supertonic-3/blob/main/LICENSE)
- Mã mẫu (ứng dụng dùng lại một phần để chạy mô hình): [MIT](https://github.com/supertone-oss-archive/supertonic/blob/main/LICENSE)

Mô hình Kokoro-82M © hexgrad, giấy phép [Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M); mã chạy bản GPU chép từ hexgrad/kokoro (Apache-2.0). Bộ tách âm của Kokoro có phần theo giấy phép **GPL-3.0** (phonemizer, espeak-ng): phần này không nằm trong bộ cài, máy bạn tự tải từ PyPI khi bấm Tải về.

- Miễn phí, dùng được cho cả cá nhân lẫn mục đích thương mại (lồng tiếng video, làm nội dung, dạy học…).
- Mã nguồn mở, theo giấy phép Apache-2.0. Muốn sửa code hoặc góp ý: xem [CONTRIBUTING.md](CONTRIBUTING.md).
- Giấy phép các thư viện đi kèm: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Quyền riêng tư: [PRIVACY.md](PRIVACY.md) - ứng dụng không thu thập dữ liệu.
- Audio bạn tạo ra thuộc về bạn. Bạn tự chịu trách nhiệm về nội dung (xem [Sử dụng có trách nhiệm](#sử-dụng-có-trách-nhiệm)).
