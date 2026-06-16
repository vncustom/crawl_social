import csv
import json
import os
from datetime import datetime
from pathlib import Path
import re  # Thêm thư viện re để dùng regex kiểm tra link
import requests

PAGE_ID = "1125132200689307"
ACCESS_TOKEN = os.environ["FB_PAGE_ACCESS_TOKEN"]
GRAPH_VERSION = "v25.0"

SINCE_DATE = "2026-06-01"
UNTIL_DATE = "2026-06-17"


def fetch_posts_since_until(since_date, until_date):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PAGE_ID}/posts"

    params = {
        "access_token": ACCESS_TOKEN,
        "since": since_date,
        "until": until_date,
        "limit": 100,
        "fields": ",".join(
            [
                "id",
                "message",
                "created_time",
                "permalink_url",
                "full_picture",
                "attachments{media,type,url,target,subattachments}",
                "comments.summary(true).limit(0)",
                "reactions.summary(true).limit(0)",
                "shares",
            ]
        ),
    }

    all_posts = []

    while url:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        all_posts.extend(data.get("data", []))

        url = data.get("paging", {}).get("next")
        params = None

    return all_posts


def get_count(post, key):
    try:
        return post.get(key, {}).get("summary", {}).get("total_count", 0)
    except Exception:
        return 0


def get_youtube_video_info(fb_url):
    """Hàm tách link YouTube gốc và lấy Title từ oEmbed API của YouTube."""
    if not fb_url:
        return "", ""

    # 1. Trích xuất link youtube thực tế từ link chuyển hướng của Facebook (l_facebook hoặc tương tự nếu có)
    # Hoặc nếu link đã là dạng youtube sẵn
    youtube_url = fb_url
    if "facebook.com/l.php" in fb_url:
        match = re.search(r"[?&]u=([^&]+)", fb_url)
        if match:
            import urllib.parse

            youtube_url = urllib.parse.unquote(match.group(1))

    # Kiểm tra xem link có đúng là youtube/youtu.be không
    if not any(domain in youtube_url for domain in ["youtube.com", "youtu.be"]):
        return "", ""

    # Chuẩn hóa link về dạng cơ bản để lưu trữ sạch hơn (tùy chọn)
    # 2. Gọi oEmbed API của YouTube để lấy Title video mà không cần API Key
    try:
        oembed_url = (
            f"https://www.youtube.com/oembed?url={youtube_url}&format=json"
        )
        res = requests.get(oembed_url, timeout=10)
        if res.status_code == 200:
            video_data = res.json()
            return youtube_url, video_data.get("title", "")
    except Exception:
        pass

    return youtube_url, ""


def extract_youtube_link(post):
    """Duyệt qua các attachments của post để tìm link bài viết dẫn đến video YouTube."""
    attachments = post.get("attachments", {}).get("data", [])
    for att in attachments:
        # Check link ở target.url hoặc url thông thường
        target_url = att.get("target", {}).get("url") or att.get("url")

        # Nếu tìm thấy link, kiểm tra xem có phải youtube không
        if target_url:
            video_url, video_title = get_youtube_video_info(target_url)
            if video_url:
                return video_url, video_title

        # Check thêm subattachments nếu có bài gom nhiều link
        sub_attachments = att.get("subattachments", {}).get("data", [])
        for sub_att in sub_attachments:
            sub_target_url = sub_att.get("target", {}).get("url") or sub_att.get(
                "url"
            )
            if sub_target_url:
                video_url, video_title = get_youtube_video_info(sub_target_url)
                if video_url:
                    return video_url, video_title

    return "", ""


def save_posts(posts, since_date, until_date):
    base_folder = Path("facebook_archive")
    archive_folder = base_folder / f"{since_date}_to_{until_date}"
    archive_folder.mkdir(parents=True, exist_ok=True)

    json_file = archive_folder / "posts.json"
    csv_file = archive_folder / "posts.csv"

    # Xử lý bổ sung thông tin YouTube vào danh sách posts trước khi lưu
    print("Đang quét và lấy thông tin video YouTube từ các bài post...")
    for post in posts:
        video_url, video_title = extract_youtube_link(post)
        post["youtube_video_url"] = video_url
        post["youtube_video_title"] = video_title

    # Lưu JSON đầy đủ
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    # Lưu CSV dễ mở bằng Excel
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)

        # Thêm 2 cột mới vào header
        writer.writerow(
            [
                "post_id",
                "created_time",
                "message",
                "permalink_url",
                "full_picture",
                "reaction_count",
                "comment_count",
                "share_count",
                "youtube_video_url",
                "youtube_video_title",
            ]
        )

        for post in posts:
            writer.writerow(
                [
                    post.get("id", ""),
                    post.get("created_time", ""),
                    post.get("message", ""),
                    post.get("permalink_url", ""),
                    post.get("full_picture", ""),
                    get_count(post, "reactions"),
                    get_count(post, "comments"),
                    post.get("shares", {}).get("count", 0),
                    post.get("youtube_video_url", ""),
                    post.get("youtube_video_title", ""),
                ]
            )

    return archive_folder, json_file, csv_file


if __name__ == "__main__":
    print("Dang lay bai viet tu Facebook...")

    posts = fetch_posts_since_until(SINCE_DATE, UNTIL_DATE)

    folder, json_file, csv_file = save_posts(posts, SINCE_DATE, UNTIL_DATE)

    print(f"Fetched {len(posts)} posts")
    print(f"Saved folder: {folder.resolve()}")
    print(f"JSON file: {json_file.resolve()}")
    print(f"CSV file: {csv_file.resolve()}")