# Facebook Page Crawlers

Dự án này lưu trữ hai phiên bản ứng dụng Python thu thập dữ liệu Facebook Page (bài viết và bình luận) qua Graph API:

1. **`fbcrawl_v2.py` (Mới / Đơn giản)**:
   - Giao diện GUI (Tkinter) cho phép nhập trực tiếp `FB_PAGE_ID` và `FB_PAGE_ACCESS_TOKEN` (tự động fallback về biến môi trường / `.env` nếu để trống).
   - Lấy **toàn bộ bình luận** (phân trang đầy đủ) cho từng bài viết.
   - Bỏ qua tính năng kiểm tra bài viết bị xóa.
   - Không dùng SQLite database, xuất trực tiếp báo cáo ra CSV/JSON.

2. **`fbcrawl.py` (Cũ / Kiểm tra bài bị xóa)**:
   - Lưu trữ bài viết và các bản snapshot vào SQLite database (`facebook_audit.db`).
   - Có tính năng quét so sánh các bài viết cũ để phát hiện bài viết bị xóa khỏi trang.
   - Xuất báo cáo từ database SQLite ra file CSV.

---

## Yêu cầu hệ thống

- Python 3.10+
- Thư viện `requests`
- Thư viện `tkinter` (mặc định đã đi kèm với Python trên Windows)

Cài đặt thư viện:
```bash
pip install requests
```

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

