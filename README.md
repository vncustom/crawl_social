# Facebook Reporting Dashboard

Ứng dụng nội bộ thu thập dữ liệu nhiều Facebook Page, lưu lịch sử vào PostgreSQL, hiển thị dashboard theo khoảng ngày và xuất báo cáo Excel 7 sheet. Người dùng đăng nhập bằng một tài khoản quản trị; cấu trúc dữ liệu đã chừa trường `role` để bổ sung phân quyền sau.

Ứng dụng cũ `fbcrawl.py` vẫn được giữ nguyên để audit bài viết bằng SQLite/CSV.

## Chức năng chính

- Nhập từng Page ID trong trang quản trị; Page mặc định là `1125132200689307`.
- Token chỉ được đọc từ biến môi trường `FB_PAGE_ACCESS_TOKEN`, không lưu trong database hay trả về API.
- Tạo backfill 90 ngày khi thêm Page, đồng bộ thủ công và theo dõi trạng thái job.
- Lọc dashboard theo Page và hai ngày bao gồm cả ngày đầu/cuối; mặc định từ một tháng trước đến hôm nay theo `Asia/Bangkok`.
- KPI, bài đăng theo ngày, top 5 bài và biểu đồ Insights theo ngày: follower mới, tổng follower, tương tác bài, lượt xem video và lượt xem Page.
- Xuất Excel dùng đúng cùng dataset với dashboard, giữ ô trống khi Facebook không cung cấp metric.

## Khởi chạy bằng Docker

Yêu cầu Docker Desktop có Docker Compose. Tạo cấu hình local:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay tối thiểu ba giá trị:

- `FB_PAGE_ACCESS_TOKEN`: Page Access Token có quyền đọc Page/Insights cần thiết.
- `APP_SECRET_KEY`: chuỗi ngẫu nhiên ít nhất 32 ký tự.
- `POSTGRES_PASSWORD`: mật khẩu database mạnh.

Khởi động, migrate database và tạo dữ liệu ban đầu:

```powershell
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m app.cli create-admin --username admin
docker compose exec api python -m app.cli seed-default-page
Invoke-RestMethod http://localhost:8000/api/health
```

Lệnh `create-admin` yêu cầu nhập mật khẩu hai lần, tối thiểu 12 ký tự. Lệnh seed xác minh Page mặc định qua Facebook và tạo job backfill 90 ngày; có thể chạy lại an toàn mà không tạo Page trùng.

Mở dashboard tại [http://localhost:3000](http://localhost:3000). API trực tiếp ở `http://localhost:8000`; frontend tự proxy `/api` tới API trong Docker.

> Worker có thể khởi động lại trong khoảng ngắn trước lần migration đầu tiên. Sau `alembic upgrade head`, chính sách restart sẽ tự đưa worker về trạng thái hoạt động.

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `FB_PAGE_ACCESS_TOKEN` | bắt buộc | Token chung dùng gọi Facebook Graph API |
| `FB_GRAPH_VERSION` | `v25.0` | Phiên bản Graph API |
| `DEFAULT_PAGE_ID` | `1125132200689307` | Page được tạo bởi lệnh seed |
| `DATABASE_URL` | Compose tự đặt | SQLAlchemy URL tới PostgreSQL |
| `APP_SECRET_KEY` | bắt buộc | Khóa bí mật của ứng dụng |
| `REPORT_TIMEZONE` | `Asia/Bangkok` | Múi giờ tính ngày báo cáo |
| `COOKIE_SECURE` | `false` | Đặt `true` khi chạy production qua HTTPS |
| `POSTGRES_DB/USER/PASSWORD` | xem `.env.example` | Cấu hình PostgreSQL trong Compose |

Không commit `.env` hoặc token. Khi xoay token, thay `FB_PAGE_ACCESS_TOKEN` trong `.env` rồi chạy:

```powershell
docker compose up -d --force-recreate api worker
```

## Vận hành

- Mỗi Page chỉ có một job ở trạng thái active (`queued`, `running`, `retrying`, `cancelling`). Yêu cầu trùng trả về job hiện có thay vì chạy song song.
- Job định kỳ lấy dữ liệu hôm qua đến hôm nay lúc 02:00 theo múi giờ Page. Page đã tắt hoặc tắt đồng bộ hằng ngày sẽ được bỏ qua.
- Dashboard đánh dấu dữ liệu `fresh`, `stale`, `partial` hoặc `unavailable`. `partial/unavailable` thường nghĩa là token thiếu quyền hoặc Facebook đã đổi/ngừng metric; hệ thống không tự thay bằng metric khác và không biến dữ liệu thiếu thành 0.
- Khi metric lỗi, xem trạng thái job và `metric_availability`, kiểm tra quyền token và phiên bản Graph API, sau đó tạo backfill cho khoảng ngày cần lấy lại.
- Sau khi triển khai HTTPS, đặt `COOKIE_SECURE=true`.
- Phiên bản đầu có một quản trị viên và chưa phân quyền. Khi mở rộng nhiều người dùng, áp dụng `AdminUser.role` cho quyền xem Page, chạy job và quản trị tài khoản.

### Sao lưu và khôi phục PostgreSQL

```powershell
docker compose exec -T db pg_dump -U facebook -Fc facebook_reporting > facebook_reporting.dump
Get-Content facebook_reporting.dump -AsByteStream | docker compose exec -T db pg_restore -U facebook -d facebook_reporting --clean --if-exists
```

Nên dừng `worker` trong lúc khôi phục và khởi động lại sau khi hoàn tất:

```powershell
docker compose stop worker
docker compose start worker
```

## Phát triển và kiểm thử

Backend cần Python 3.12+:

```powershell
cd backend
python -m pip install -e ".[test]"
python -m pytest -q
```

Frontend cần Node.js 22+:

```powershell
cd frontend
npm ci
npm run lint
npm test -- --run
npm run build
```

Kiểm thử crawler cũ:

```powershell
python -m unittest discover -s tests -v
```

## Crawler audit cũ

Các lệnh cũ tiếp tục sử dụng `FB_PAGE_ACCESS_TOKEN`, `FB_PAGE_ID` và SQLite:

```powershell
python fbcrawl.py sync --since 2026-06-01 --until 2026-06-17
python fbcrawl.py check-deleted --since 2026-06-01 --until 2026-06-08
python fbcrawl.py report --out facebook_archive/audit_report.csv
python fbcrawl.py gui
```

`check-deleted` chỉ nên dùng khi cần xác minh thêm vì gọi từng `post_id`; kết quả vẫn là “nghi đã xóa” nếu token/quyền truy cập thay đổi.
