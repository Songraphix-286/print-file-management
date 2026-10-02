# Hello Kitty Print File Manager

Dự án này là một ứng dụng Python quản lý file in ấn theo mô hình cute, tối giản và dễ nhìn, có giao diện kiểu Hello Kitty với màu hồng pastel.

Tính năng chính:
- Quản lý file theo hạng mục: In bạt, Decal, PP, Khác
- Quét folder tự động để phát hiện file mới, file bị chỉnh sửa hoặc file bị xóa
- Lưu lịch sử thay đổi vào SQLite
- Cảnh báo hiển thị trên giao diện sau mỗi lần quét
- Giao diện dễ dùng, phù hợp cho doanh nghiệp in ấn hoặc phòng thiết kế

Yêu cầu:
- Python 3.9+
- Tkinter có sẵn trong Python

Cách chạy:
1. Tạo môi trường ảo:
   python -m venv .venv
2. Kích hoạt môi trường:
   - Windows: .venv\Scripts\activate
   - macOS/Linux: source .venv/bin/activate
3. Chạy ứng dụng:
   python app.py

Giao diện hiện có:
- Header kiểu kitty hồng pastel
- Bảng danh sách file theo từng hạng mục
- Khu vực thông báo cảnh báo
- Nút chọn folder và quét folder tự động

Lưu ý:
- Ứng dụng hiện đang dùng cơ chế quét định kỳ để kiểm tra thay đổi, phù hợp cho demo và MVP.
- Nếu bạn muốn nâng cấp lên realtime với watchdog hoặc web app Flask/FastAPI, mình có thể tiếp tục phát triển thêm.
