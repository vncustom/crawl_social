# Facebook Page Audit Crawler

Cong cu Python de crawl bai viet Facebook Page, luu snapshot vao SQLite, kiem tra bai da dang co bi xoa hay khong, va xuat bao cao CSV. App co ca command line va giao dien Tkinter.

## Chuc nang

- `sync`: crawl bai viet theo khoang ngay, luu snapshot vao SQLite, tu gioi han 500 bai/lien chay va nghi giua cac request.
- `check-deleted`: kiem tra toi da 500 bai da tung luu con ton tai tren Graph API khong. Lenh nay ton request hon `sync`.
- `report`: xuat bao cao audit ra CSV.
- `gui`: mo giao dien Tkinter de nhap ngay, chay sync, check deleted, export report.

## Cai dat

Can Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Tkinter thuong co san trong Python tren Windows, nen khong nam trong `requirements.txt`.

## Cau hinh token

App doc Page Access Token tu bien moi truong `FB_PAGE_ACCESS_TOKEN`.

```powershell
$env:FB_PAGE_ACCESS_TOKEN="page_access_token_cua_ban"
```

Mac dinh Page ID dang la `1125132200689307`. Neu can doi Page ID ma khong sua code:

```powershell
$env:FB_PAGE_ID="page_id_cua_ban"
```

Co the doi Graph API version:

```powershell
$env:FB_GRAPH_VERSION="v25.0"
```

Co the doi gioi han an toan neu that su can:

```powershell
$env:FB_SYNC_MAX_POSTS="500"
$env:FB_SYNC_SLEEP_SECONDS="1.5"
$env:FB_CHECK_MAX_POSTS="500"
$env:FB_CHECK_SLEEP_SECONDS="0.5"
```

Khuyen nghi giu mac dinh de giam rui ro rate limit.

Khong commit token len GitHub. Nen de token trong bien moi truong hoac file `.env` local, va `.env` da duoc ignore.

## Cach su dung command line

### 1. Crawl va luu snapshot

```powershell
python fbcrawl.py sync --since 2026-06-01 --until 2026-06-17
```

Lenh nay tao/cap nhat SQLite DB mac dinh tai:

```text
facebook_archive/facebook_audit.db
```

Du lieu chinh:

- `posts`: trang thai hien tai cua tung bai da thay.
- `post_snapshots`: moi lan crawl luu mot snapshot.
- `deletion_events`: cac lan phat hien bai nghi da bi xoa.

Moi lan `sync` mac dinh chi lay toi da 500 bai. Neu dat gioi han nay, app se dung va bao dang dung o bai/ngay nao. Hay chia nho khoang ngay hon hoac chay tiep vao ngay khac.

Khi `sync` chay het tron mot khoang ngay, app se so sanh cac `post_id` trong lan sync moi voi cac bai da tung luu trong cung khoang ngay. Neu bai cu khong con xuat hien trong snapshot moi, app danh dau `suspected_deleted` voi source `sync_snapshot`. Cach nay it request hon viec goi tung `post_id`.

### 2. Kiem tra bai bi xoa

```powershell
python fbcrawl.py check-deleted
```

Lenh nay doc cac bai trong DB, goi Graph API theo tung `post_id`, va danh dau `suspected_deleted` neu bai khong con truy cap duoc. De giam rui ro rate limit, app chi check toi da 500 bai moi lan va nghi giua cac request.

Luu y: ket qua la "nghi da xoa" vi Graph API co the khong tra bai do vi quyen/token/loi tam thoi. Nen uu tien `sync` dinh ky de co snapshot, chi dung `check-deleted` khi can xac minh them.

### 3. Xuat bao cao CSV

```powershell
python fbcrawl.py report --out facebook_archive/audit_report.csv
```

CSV gom `post_id`, `status`, thoi diem thay dau/cuoi, thoi diem check, thoi diem nghi xoa, noi dung bai, permalink, anh, va thong tin YouTube neu co.

### 4. Dung DB tuy chinh

Moi command co the dung `--db`:

```powershell
python fbcrawl.py --db data/my_page_audit.db sync --since 2026-06-01 --until 2026-06-17
python fbcrawl.py --db data/my_page_audit.db check-deleted
python fbcrawl.py --db data/my_page_audit.db report --out data/audit_report.csv
```

## Cach su dung giao dien Tkinter

Mo app:

```powershell
python fbcrawl.py gui
```

Hoac chi can:

```powershell
python fbcrawl.py
```

Trong giao dien:

1. Nhap duong dan SQLite DB.
2. Nhap ngay bat dau va ngay ket thuc theo dinh dang `YYYY-MM-DD`.
3. Nhap duong dan file report CSV.
4. Bam `Sync` de crawl, luu snapshot, va tu so sanh snapshot neu sync tron khoang ngay.
5. Bam `Check Deleted` de kiem tra them bang tung `post_id` neu can.
6. Bam `Export Report` de xuat CSV.

Khi tac vu dang chay, app se khoa cac nut va hien thanh tien trinh de tranh nham la chuong trinh bi treo. Neu thieu token, sai ngay, loi mang, loi Graph API, hoac loi ghi file, app se hien hop thoai thong bao loi.

## Kiem thu

Chay unit test:

```powershell
python -m unittest discover -s tests -v
```

Kiem tra syntax:

```powershell
python -m py_compile fbcrawl.py tests/test_fbcrawl.py
```

## Ghi chu van hanh

- Nen chay `sync` theo lich, vi he thong chi phat hien xoa cho cac bai da tung duoc luu.
- Voi Page dang rat nhieu bai, nen sync theo ngay/tuan thay vi chon khoang qua dai.
- Khong nen bam `check-deleted` lien tuc. Lenh nay goi tung `post_id`, mac du da gioi han 500 bai moi lan.
- De audit nhan vien dang/xoa bai chinh xac hon, nen yeu cau nhan vien dang qua cong cu noi bo hoac luu mapping `employee_id -> post_id`.
- Thu muc `facebook_archive/`, SQLite DB, CSV report, cache va token local da duoc ignore trong Git.
