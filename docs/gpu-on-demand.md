# Bộ hỗ trợ GPU tải theo yêu cầu

Bản desktop chỉ kèm `tools/uv.exe`; không kèm PyTorch, torchaudio hay
transformers. Build bằng `scripts/build_desktop_exe.bat` để có công cụ này trong bundle.
Người dùng bản `.exe` cũ phải cập nhật app để nhận thay đổi.

Trong Settings, máy NVIDIA chưa có thư viện sẽ hiện **Cài hỗ trợ GPU**.
Nút này tải mô hình và cài thư viện ở worker nền, kể cả khi mô hình đã có sẵn.
Máy CPU không tải thư viện GPU. Backend chạy bằng Python riêng cũng cài được
từ Settings khi tìm thấy công cụ `uv`, không yêu cầu cờ PyInstaller.

Lần đầu cần mạng và ít nhất 12 GB trống. Python được chọn cùng major/minor với
app; dữ liệu nằm trong `gpu_venv/<phiên bản Python>` cạnh app, hoặc
`%LOCALAPPDATA%/CitVoiceStudio/gpu_venv` nếu thư mục app chỉ đọc.
Cache tải và Python dùng chung nằm trong thư mục cha. PyTorch 2.8.0 / torchaudio
2.8.0 lấy từ kho CUDA cu128; transformers 4.57.6 và safetensors lấy từ PyPI.

Giao diện hiển thị từng bước cài, không dùng phần trăm tải mô hình để biểu diễn
dung lượng bộ GPU. Huỷ dừng tiến trình cài; Thử lại dùng lại cache đã tải.
App kiểm tra import và phép tính CUDA trong Python riêng rồi trong tiến trình
app trước khi áp dụng mô hình. Nếu chỉ bước nạp vào app thất bại, người dùng
được hướng dẫn khởi động lại để nạp thư viện ngay từ đầu.

## Kiểm tra bản phát hành trên Windows NVIDIA

1. Build `.exe` mới và xác nhận `_internal/tools/uv.exe` tồn tại. Kiểm tra
   không có torch/CUDA trong bundle CPU.
2. Trên máy RTX 3060 với driver phù hợp, không cài Python/uv trong PATH,
   mở Settings và bấm Cài hỗ trợ GPU. Xác nhận các bước cài hiện rõ.
3. Chờ cài xong, xác nhận GPU được áp dụng và tổng hợp thử một câu.
4. Mở lại app: dùng lại thư viện đã cài, không tải bộ GPU lần nữa.
5. Kiểm tra huỷ khi đang cài, mạng lỗi rồi Thử lại, thiếu dung lượng,
   thư mục cài chỉ đọc và mô hình có sẵn nhưng chưa có thư viện GPU.
6. Trên máy CPU, mở app và dùng bản int8: không tải bộ hỗ trợ GPU.

Các unit test dùng mô phỏng GPU và mạng; không thay thế kiểm tra `.exe` trên
RTX 3060 thật.
