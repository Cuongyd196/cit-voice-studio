# Quyền riêng tư — CIT Voice Studio

**CIT Voice Studio không thu thập dữ liệu của bạn.** Không cần tài khoản, không có
quảng cáo, không gửi thống kê sử dụng hay báo lỗi về cho tác giả.

## Dữ liệu nằm ở đâu

Mọi thứ bạn nhập và tạo ra chỉ nằm trên máy của bạn:

- văn bản, audio và phụ đề đã tạo (tab Lịch sử);
- giọng đã nhân bản và file giọng mẫu bạn đưa vào;
- từ điển phát âm và các cài đặt.

Vị trí thư mục dữ liệu ghi trong README, mục "Dữ liệu được lưu ở đâu". Gỡ ứng dụng hoặc xoá
các thư mục đó là xoá hết.

## Khi nào ứng dụng dùng mạng

Sau khi cài, ứng dụng chạy được hoàn toàn không cần Internet. Nó chỉ kết nối ra ngoài
trong các trường hợp sau, và chỉ tải xuống, không gửi nội dung của bạn đi:

| Trường hợp | Kết nối tới | Mặc định |
|---|---|---|
| Kiểm tra bản mới (bạn bật trong Cài đặt, hoặc bấm "Kiểm tra cập nhật") | GitHub, tối đa một lần mỗi ngày | **Tắt** |
| Bạn bấm Tải về một mô hình không kèm sẵn | Hugging Face | Chỉ khi bạn bấm |
| Bạn bấm "Cài hỗ trợ GPU" | PyPI, download.pytorch.org, GitHub / releases.astral.sh | Chỉ khi bạn bấm |
| Bạn bấm một đường link trong ứng dụng | Trang web đó, mở bằng trình duyệt | Chỉ khi bạn bấm |

Như mọi kết nối Internet, các máy chủ trên thấy địa chỉ IP của bạn và tên phần mềm
(`CIT-Voice-Studio/<phiên bản>`). Ứng dụng không gửi kèm văn bản, audio hay thông tin cá
nhân nào.

## Cho máy khác truy cập (API)

Tính năng này **tắt sẵn**. Khi bạn bật, các máy khác trong mạng gọi được API tạo giọng
của máy bạn bằng khoá API. Văn bản chúng gửi tới được xử lý ngay trên máy bạn. Kết nối
trong mạng nội bộ dùng HTTP không mã hoá, nên chỉ bật trong mạng bạn tin tưởng.

## Audio tạo ra

File WAV/MP3 ứng dụng xuất ra có ghi chú "AI-generated speech … CIT Voice Studio"
trong phần thông tin của file (theo yêu cầu đánh dấu nội dung do AI tạo ra). Ghi chú này
không chứa thông tin cá nhân nào.
