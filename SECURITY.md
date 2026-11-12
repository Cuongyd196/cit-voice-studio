# Chính sách bảo mật

## Báo lỗ hổng

Vui lòng **không** báo lỗ hổng bảo mật qua issue công khai.

Hãy báo riêng qua GitHub: vào tab **Security** của repo, chọn **Report a vulnerability**. Chỉ chủ dự án đọc được báo cáo này.

Nên ghi:
- Phiên bản app và hệ điều hành.
- Cách tái hiện, từng bước.
- Ảnh hưởng: kẻ tấn công làm được gì.

Bạn sẽ nhận phản hồi trong vòng 7 ngày. Khi bản sửa được phát hành, bạn sẽ được ghi công nếu muốn.

## Phạm vi

Đáng quan tâm nhất là những phần nhận kết nối từ bên ngoài:
- **Truy cập từ xa và API key** (`apps/remote_access.py`): bỏ qua xác thực, lộ khoá API.
- **API cục bộ:** trang web lạ mở trên cùng máy đọc hoặc sửa được dữ liệu của app (CORS, DNS rebinding).
- **Đọc file người dùng tải lên:** PDF, DOCX, SRT, âm thanh.
- **Bộ cài và cơ chế tải thêm thư viện** (GPU, Kokoro).

## Phiên bản được hỗ trợ

Chỉ bản phát hành mới nhất được nhận bản vá bảo mật.
