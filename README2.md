# fbcrawl\_v2.py – Facebook Page Crawler

Phiên bản đơn giản hoá, tập trung vào **crawl bài viết + toàn bộ comment** và xuất báo cáo thẳng ra CSV/JSON — không dùng database, không kiểm tra bài bị xoá.

---

## Yêu cầu

| Yêu cầu | Phiên bản tối thiểu |
|---|---|
| Python | 3.10+ |
| Thư viện | `requests` |
| Tkinter | Đã tích hợp sẵn trong Python (không cần cài thêm) |

Cài thư viện:

```bash
pip install requests
```

---

## Chạy nhanh

```bash
python fbcrawl_v2.py
```

Giao diện Tkinter sẽ mở ra ngay.

---

## Cấu hình biến môi trường (tuỳ chọn)

Nếu muốn điền sẵn thông tin mặc định mà không cần gõ mỗi lần mở app, hãy đặt các biến môi trường sau:

| Biến | Mô tả | Mặc định |
|---|---|---|
| `FB_PAGE_ID` | ID của Facebook Page cần crawl | *(trống)* |
| `FB_PAGE_ACCESS_TOKEN` | Page Access Token (từ Meta Developer) | *(trống)* |
| `FB_GRAPH_VERSION` | Phiên bản Graph API | `v25.0` |
| `FB_SYNC_MAX_POSTS` | Số bài tối đa mỗi lần crawl | `500` |
| `FB_SYNC_SLEEP_SECONDS` | Thời gian chờ giữa các request phân trang bài | `1.5` |

Ví dụ trên Windows (Command Prompt):

```cmd
set FB_PAGE_ID=123456789
set FB_PAGE_ACCESS_TOKEN=EAAxxxxxxxxxx
python fbcrawl_v2.py
```

Ví dụ trên Windows (PowerShell):

```powershell
$env:FB_PAGE_ID = "123456789"
$env:FB_PAGE_ACCESS_TOKEN = "EAAxxxxxxxxxx"
python fbcrawl_v2.py
```

Hoặc lưu vào file `.env` và dùng `python-dotenv` để nạp trước khi chạy.

> **Lưu ý:** Nếu bạn nhập trực tiếp vào giao diện, giá trị trong ô nhập sẽ **được ưu tiên** hơn biến môi trường.

---

## Hướng dẫn sử dụng giao diện

```
┌─────────────────────────────────────────────────────────────┐
│  Facebook Page Crawler v2                                   │
├─────────────────────────────────────────────────────────────┤
│  Cau hinh API                                               │
│    FB_PAGE_ID            [ _________________ ]              │
│    FB_PAGE_ACCESS_TOKEN  [ **************** ] [Hien/An]     │
│    (De trong se dung os.getenv)                             │
├─────────────────────────────────────────────────────────────┤
│  Khoang thoi gian crawl                                     │
│    Tu ngay (YYYY-MM-DD)  [ 2025-07-01      ]               │
│    Den ngay (YYYY-MM-DD) [ 2025-07-26      ]               │
├─────────────────────────────────────────────────────────────┤
│  Cai dat xuat file                                          │
│    Thu muc xuat file     [ facebook_export ]               │
│    So bai toi da         [ 500             ]               │
├─────────────────────────────────────────────────────────────┤
│          [ Crawl & Xuat bao cao ]                           │
│  ████████████████░░░░░░░░░░░░░░  (progress bar)            │
│  Dang lay comment 12/50 ...                                 │
└─────────────────────────────────────────────────────────────┘
```

### Các bước thực hiện

1. **Điền `FB_PAGE_ID`** – ID của trang Facebook (ví dụ: `1125132200689307`).
2. **Điền `FB_PAGE_ACCESS_TOKEN`** – Token lấy từ [Meta for Developers](https://developers.facebook.com/). Nhấn **Hiện/Ẩn** để kiểm tra token đã điền đúng chưa.
3. **Chọn khoảng ngày** – Nhập `Tu ngay` và `Den ngay` theo định dạng `YYYY-MM-DD`.
4. **Chỉnh Số bài tối đa** nếu cần (mặc định 500).
5. Nhấn **Crawl & Xuất báo cáo** và đợi thanh tiến trình chạy xong.
6. Hộp thoại kết quả sẽ hiển thị đường dẫn đầy đủ đến file CSV và JSON.

---

## File xuất ra

Mỗi lần crawl sẽ tạo **2 file** trong thư mục xuất (mặc định `facebook_export/`):

```
facebook_export/
├── fb_report_2025-07-01_to_2025-07-26_20250726_153012.csv
└── fb_report_2025-07-01_to_2025-07-26_20250726_153012.json
```

Tên file tự động thêm timestamp để tránh ghi đè.

### Cấu trúc CSV

| Cột | Mô tả |
|---|---|
| `FB_PAGE_ID` | ID của Page đã crawl |
| `post_id` | ID duy nhất của bài viết |
| `created_time` | Thời gian đăng (định dạng `dd/mm/yyyy HH:MM:SS`, múi giờ local) |
| `permalink_url` | Link trực tiếp đến bài viết |
| `message` | Nội dung văn bản của bài viết |
| `full_picture` | URL ảnh đính kèm (nếu có) |
| `video_link` | Link video YouTube hoặc Facebook (nếu có) |
| `comments` | Toàn bộ comment, mỗi dòng: `[dd/mm/yyyy HH:MM:SS] Tên: nội dung` |

> **Mẹo:** File CSV được lưu với encoding `utf-8-sig` (UTF-8 có BOM) để mở đúng font tiếng Việt trong Microsoft Excel.

---

## Lấy Page Access Token

1. Truy cập [Meta for Developers](https://developers.facebook.com/) → chọn ứng dụng của bạn.
2. Vào **Tools → Graph API Explorer**.
3. Chọn **User or Page** → chọn đúng Page.
4. Chọn các quyền: `pages_read_engagement`, `pages_show_list`, `pages_read_user_content`.
5. Nhấn **Generate Access Token** và copy token.

> **Lưu ý:** Page Access Token dài hạn (Long-lived) có thể tồn tại đến 60 ngày. Token ngắn hạn chỉ tồn tại ~1–2 giờ.

---

## Giới hạn kỹ thuật

| Giới hạn | Chi tiết |
|---|---|
| **Rate limit** | Graph API giới hạn ~200 request/giờ mỗi token. Script tự thêm delay giữa các request. |
| **Comment riêng tư** | Token phải là Page Access Token mới đọc được comment của Page. |
| **Số bài** | Nếu khoảng ngày lớn, tăng `So bai toi da` hoặc chia nhỏ khoảng ngày. |
| **Video link** | Chỉ trích xuất được YouTube và Facebook video trực tiếp. Link drive/cloud khác không được nhận diện. |

---

## So sánh với fbcrawl.py (bản gốc)

| Tính năng | `fbcrawl.py` | `fbcrawl_v2.py` |
|---|---|---|
| Lấy bài viết | ✅ | ✅ |
| Lấy toàn bộ comment | ❌ (chỉ đếm số lượng) | ✅ |
| Kiểm tra bài bị xoá | ✅ | ❌ (bỏ) |
| Lưu vào SQLite | ✅ | ❌ |
| Xuất CSV/JSON trực tiếp | ❌ | ✅ |
| Nhập Page ID & Token qua GUI | ❌ | ✅ |
| Cần cấu hình DB | ✅ | ❌ |

---

## Cấu trúc mã nguồn

```
fbcrawl_v2.py
├── configure_console_encoding()   – Cấu hình encoding stdout/stderr UTF-8
├── validate_date()                – Kiểm tra định dạng ngày
├── parse_datetime_value()         – Parse ISO 8601 datetime
├── format_local_datetime()        – Chuyển UTC → múi giờ local, định dạng đẹp
├── get_youtube_url()              – Trích xuất URL YouTube từ link Facebook
├── extract_video_link()           – Tìm video link trong attachments
├── fetch_all_comments()           – Lấy toàn bộ comment (có phân trang)
├── format_comments()              – Định dạng comment thành văn bản
├── fetch_posts()                  – Gọi Graph API /posts (có phân trang)
├── crawl_and_export()             – Orchestrate: crawl → comment → xuất file
└── launch_gui()                   – Giao diện Tkinter
```

---

## Ví dụ kết quả comments trong CSV

```
[26/07/2025 09:15:32] Nguyen Van A: Bài hay quá!
[26/07/2025 09:20:11] Tran Thi B: Cho hỏi link xem ở đâu ạ?
[26/07/2025 09:45:00] Le Van C: Cảm ơn admin đã chia sẻ
```

---

## Giấy phép

Xem file `LICENSE` trong thư mục gốc của dự án.
