import os
import json
import csv
import requests
from pathlib import Path
from datetime import datetime

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
        "fields": ",".join([
            "id",
            "message",
            "created_time",
            "permalink_url",
            "full_picture",
            "attachments{media,type,url,target,subattachments}",
            "comments.summary(true).limit(0)",
            "reactions.summary(true).limit(0)",
            "shares"
        ])
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


def save_posts(posts, since_date, until_date):
    base_folder = Path("facebook_archive")
    archive_folder = base_folder / f"{since_date}_to_{until_date}"
    archive_folder.mkdir(parents=True, exist_ok=True)

    json_file = archive_folder / "posts.json"
    csv_file = archive_folder / "posts.csv"

    # Lưu JSON đầy đủ
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    # Lưu CSV dễ mở bằng Excel
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "post_id",
            "created_time",
            "message",
            "permalink_url",
            "full_picture",
            "reaction_count",
            "comment_count",
            "share_count"
        ])

        for post in posts:
            writer.writerow([
                post.get("id", ""),
                post.get("created_time", ""),
                post.get("message", ""),
                post.get("permalink_url", ""),
                post.get("full_picture", ""),
                get_count(post, "reactions"),
                get_count(post, "comments"),
                post.get("shares", {}).get("count", 0)
            ])

    return archive_folder, json_file, csv_file


if __name__ == "__main__":
    print("Dang lay bai viet tu Facebook...")

    posts = fetch_posts_since_until(SINCE_DATE, UNTIL_DATE)

    folder, json_file, csv_file = save_posts(posts, SINCE_DATE, UNTIL_DATE)

    print(f"Fetched {len(posts)} posts")
    print(f"Saved folder: {folder.resolve()}")
    print(f"JSON file: {json_file.resolve()}")
    print(f"CSV file: {csv_file.resolve()}")