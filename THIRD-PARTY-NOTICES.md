# Thông báo phần mềm bên thứ ba - CIT Voice Studio

CIT Voice Studio dùng các thành phần mã nguồn mở dưới đây. Mỗi thành phần giữ nguyên
bản quyền và giấy phép của tác giả. Ghi công cho VieNeu-TTS, và các thành phần chỉ tải
về máy khi người dùng bấm (hỗ trợ GPU, mô hình tải thêm), nằm trong file `NOTICE`.

## Thư viện LGPL

Các thư viện này được dùng **nguyên bản, không sửa đổi**, dưới dạng thư viện liên kết
động nằm riêng trong thư mục cài đặt. Bạn có quyền thay chúng bằng bản khác tương thích.

| Thành phần | Giấy phép | Mã nguồn |
|---|---|---|
| libsndfile (đọc/ghi WAV, MP3) | LGPL-2.1-or-later | https://github.com/libsndfile/libsndfile |
| LAME (bộ mã MP3, trong libsndfile) | LGPL-2.0-or-later | https://lame.sourceforge.io |
| mpg123 (bộ giải mã MP3, trong libsndfile) | LGPL-2.1 | https://www.mpg123.de |
| libsoxr (đổi tần số lấy mẫu, qua gói `soxr`) | LGPL-2.1-or-later | https://github.com/dofuuz/python-soxr |

Toàn văn LGPL-2.1 có trong thư mục cài đặt, file `_internal/_soundfile_data/COPYING`
(bản Windows).

## Mô hình AI kèm sẵn

| Mô hình | Giấy phép | Nguồn |
|---|---|---|
| VieNeu-TTS v3 Turbo (ONNX int8) và bộ giọng có sẵn | Apache-2.0 | https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo |
| MOSS Audio Tokenizer Nano (ONNX) | Apache-2.0 | https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX |

## Mô hình tải thêm khi dùng

| Mô hình | Giấy phép | Nguồn |
|---|---|---|
| Zipformer ASR tiếng Việt - kiểm tra câu đồng ý khi tạo giọng nhân bản, tải lần đầu tạo giọng | Apache-2.0 | https://huggingface.co/csukuangfj/sherpa-onnx-zipformer-vi-int8-2025-04-20 (gốc: https://huggingface.co/zzasdf/viet_iter3_pseudo_label) |
| Supertonic 3 (Supertone Inc.) - giọng nước ngoài 31 ngôn ngữ, tải khi bạn bấm Tải về trong mục Mô hình. File `LICENSE` của giấy phép tải kèm mô hình. Giấy phép có danh sách cấm dùng (mạo danh khi không được đồng ý, lừa đảo, tin giả gây hại, nội dung do máy tạo mà không ghi rõ…) áp dụng cho mọi người dùng | OpenRAIL-M | https://huggingface.co/supertone-oss-archive/supertonic-3 (mã nguồn mẫu, MIT: https://github.com/supertone-oss-archive/supertonic) |

## Các thư viện khác

Ứng dụng còn dùng khoảng 90 thư viện mã nguồn mở theo giấy phép MIT, BSD, Apache-2.0,
ISC, PSF, MPL-2.0 và SIL Open Font License 1.1, tiêu biểu: Python, NumPy, SciPy,
ONNX Runtime, Hugging Face Hub, FastAPI, Uvicorn, pywebview, pythonnet, OpenSSL,
PyInstaller (bộ khởi động GPL-2.0 kèm ngoại lệ cho phép phân phối), React, Radix UI,
Lucide, Tailwind CSS và phông chữ Inter. Bản quyền thuộc tác giả của từng thư viện.
