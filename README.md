# Facebook Page Crawlers & Web Dashboard

Dự án này bao gồm ứng dụng Web Dashboard trực quan cùng với các công cụ Python thu thập dữ liệu Facebook Page qua Graph API:

1. **`app_web.py` (Phiên bản Web Dashboard)**:
   - Giao diện Web SPA hiện đại, trực quan, phục vụ tại `http://localhost:8000`.
   - Xem bài đăng dạng thẻ Feed trực quan kèm hình ảnh thumbnail, link video.
   - **Nút 1-Click Copy**: Sao chép nội dung bài viết, danh sách comment hoặc link bài đăng chỉ với 1 cú nhấp chuột.
   - Bộ lọc tìm kiếm nhanh bài viết/comment, lọc bài có video/ảnh.
   - Xuất dữ liệu linh hoạt ra CSV và JSON.

2. **`fbcrawl_v2.py` (Mới / Tkinter GUI)**:
   - Giao diện Tkinter GUI đơn giản.
   - Lấy toàn bộ bình luận cho từng bài viết và xuất ra CSV/JSON.

3. **`fbcrawl.py` (Cũ / Kiểm tra bài bị xóa)**:
   - Lưu trữ lịch sử bài viết vào SQLite database (`facebook_audit.db`).
   - Kiểm tra phát hiện bài viết bị xóa khỏi trang.

---

## Yêu cầu hệ thống

- Python 3.10+
- Thư viện: `requests`, `fastapi`, `uvicorn`

Cài đặt thư viện:
```bash
pip install -r requirements.txt
```

---

## 1. 🚀 Khởi chạy Web Dashboard (`app_web.py`)

```bash
python app_web.py
```
Mở trình duyệt truy cập: [http://localhost:8000](http://localhost:8000)

### 🔑 Quản trị Admin & Dropdown Chọn Page
- **Tài khoản Admin mặc định**: User: `admin` / Password: `admin`
- **TÍnh năng Admin**: Bấm **🔑 Đăng nhập Admin** ở góc phải giao diện để mở bảng quản trị. Admin có quyền thêm/sửa/xóa các bộ `FB_PAGE_ID` và `FB_PAGE_ACCESS_TOKEN` tương ứng. Danh sách này được **tự động lưu vào file `.env`**.
- **Người dùng thông thường**: Không cần nhập Access Token. Chỉ cần mở menu **Dropdown Chọn Facebook Page** do Admin cấu hình sẵn để crawl dữ liệu bảo mật.

---

## 1. Phiên bản fbcrawl_v2.py (Khuyên dùng)

### Chức năng chính
- Nhập trực tiếp Page ID và Page Access Token ngay trên giao diện hoặc cấu hình qua biến môi trường.
- Crawl danh sách bài đăng trong khoảng thời gian chỉ định.
- Lấy toàn bộ comment của từng bài đăng.
- Xuất kết quả trực tiếp ra thư mục `facebook_export/` dưới dạng CSV và JSON.
  - Định dạng CSV dùng UTF-8 có BOM (`utf-8-sig`) giúp hiển thị đúng tiếng Việt trong Microsoft Excel.

### Cách chạy nhanh
```bash
python fbcrawl_v2.py
```

### Các cột trong báo cáo CSV (`fbcrawl_v2.py`):
- `FB_PAGE_ID`: ID của trang Facebook.
- `post_id`: ID bài đăng.
- `created_time`: Thời gian đăng bài (múi giờ máy local).
- `permalink_url`: Đường dẫn tới bài viết.
- `message`: Nội dung bài viết.
- `full_picture`: URL hình ảnh đi kèm.
- `video_link`: Link video (YouTube hoặc Facebook video).
- `comments`: Danh sách tất cả bình luận có cấu trúc: `[Thời gian] Người dùng: Nội dung`.

---

## 2. Phiên bản fbcrawl.py (Nguyên bản)

Phiên bản này lưu trữ lịch sử qua database SQLite nội bộ và cho phép kiểm tra bài viết đã bị xóa khỏi Graph API.

### Cách chạy qua GUI
```bash
python fbcrawl.py gui
```

### Các câu lệnh CLI phổ biến
- **Đồng bộ bài viết**:
  ```bash
  python fbcrawl.py sync --since 2026-06-01 --until 2026-06-17
  ```
- **Kiểm tra bài đăng bị xóa**:
  ```bash
  python fbcrawl.py check-deleted --since 2026-06-01 --until 2026-06-08
  ```
- **Xuất báo cáo từ SQLite**:
  ```bash
  python fbcrawl.py report --out facebook_archive/audit_report.csv
  ```

---

## Cấu hình Biến Môi Trường (Tùy chọn)

Bạn có thể tạo một file `.env` ở thư mục gốc của dự án để điền các giá trị mặc định:

```env
FB_PAGE_ID=1125132200689307
FB_PAGE_ACCESS_TOKEN=nhập_token_của_bạn_vào_đây
FB_GRAPH_VERSION=v25.0
FB_SYNC_MAX_POSTS=500
FB_SYNC_SLEEP_SECONDS=1.5
```

---

## Kiểm thử ứng dụng
Để chạy bộ kiểm thử tự động của bản crawler cũ:
```bash
python -m unittest discover -s tests -v
```

