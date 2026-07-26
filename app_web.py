"""
app_web.py - Web Dashboard Server cho Facebook Page Crawler

Sử dụng FastAPI + Uvicorn kết hợp giao diện Web SPA trực quan.
 Tận dụng core logic từ fbcrawl_v2.py để đảm bảo tính nhất quán.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Import core logic từ fbcrawl_v2
from fbcrawl_v2 import (
    DEFAULT_ACCESS_TOKEN,
    DEFAULT_MAX_POSTS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PAGE_ID,
    extract_video_link,
    fetch_all_comments,
    fetch_posts,
    format_comments,
    format_local_datetime,
    validate_date,
)

app = FastAPI(title="Facebook Page Crawler Web Dashboard")

# Cấu hình thư mục static và templates
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Phục vụ trang Web Dashboard chính."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Giao diện index.html không tồn tại.")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.get("/api/config")
async def get_default_config():
    """Trả về cấu hình mặc định từ biến môi trường."""
    pid = os.getenv("FB_PAGE_ID", DEFAULT_PAGE_ID)
    tok = os.getenv("FB_PAGE_ACCESS_TOKEN", DEFAULT_ACCESS_TOKEN)
    return {
        "page_id": pid,
        "has_token": bool(tok),
        "token_preview": (tok[:6] + "..." + tok[-4:]) if len(tok) > 10 else ("*" * len(tok)),
        "max_posts": int(os.getenv("FB_SYNC_MAX_POSTS", DEFAULT_MAX_POSTS)),
        "default_since": datetime.now().strftime("%Y-%m-01"),
        "default_until": datetime.now().strftime("%Y-%m-%d"),
    }


@app.post("/api/crawl")
async def crawl_api(request: Request):
    """Endpoint REST crawl truyền thống, trả về toàn bộ dữ liệu JSON."""
    body = await request.json()
    page_id = (body.get("page_id") or "").strip() or os.getenv("FB_PAGE_ID", "").strip()
    access_token = (body.get("access_token") or "").strip() or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    since_date = (body.get("since_date") or "").strip()
    until_date = (body.get("until_date") or "").strip()
    max_posts = int(body.get("max_posts") or DEFAULT_MAX_POSTS)

    if not page_id:
        raise HTTPException(status_code=400, detail="Thiếu FB_PAGE_ID.")
    if not access_token:
        raise HTTPException(status_code=400, detail="Thiếu FB_PAGE_ACCESS_TOKEN.")

    try:
        validate_date(since_date)
        validate_date(until_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        fetch_result = fetch_posts(
            since_date=since_date,
            until_date=until_date,
            page_id=page_id,
            access_token=access_token,
            max_posts=max_posts,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi Facebook API: {exc}")

    posts_output = []
    total = len(fetch_result.posts)
    video_count = 0
    image_count = 0
    total_comments_count = 0

    for idx, post in enumerate(fetch_result.posts):
        post_id = post.get("id", "")
        comments_raw = fetch_all_comments(post_id, access_token)
        comments_text = format_comments(comments_raw)
        total_comments_count += len(comments_raw)

        video_link = extract_video_link(post)
        full_picture = post.get("full_picture", "")

        if video_link:
            video_count += 1
        if full_picture:
            image_count += 1

        formatted_comments_list = []
        for c in comments_raw:
            formatted_comments_list.append({
                "id": c.get("id", ""),
                "author": c.get("from", {}).get("name", "Người dùng Facebook"),
                "message": c.get("message", ""),
                "created_time": format_local_datetime(c.get("created_time", "")),
                "like_count": c.get("like_count", 0),
            })

        posts_output.append({
            "FB_PAGE_ID": page_id,
            "post_id": post_id,
            "created_time": format_local_datetime(post.get("created_time", "")),
            "permalink_url": post.get("permalink_url", ""),
            "message": post.get("message", ""),
            "full_picture": full_picture,
            "video_link": video_link,
            "comments_text": comments_text,
            "comments_list": formatted_comments_list,
            "comment_count": len(comments_raw),
        })

    return {
        "status": "success",
        "page_id": page_id,
        "since_date": since_date,
        "until_date": until_date,
        "stats": {
            "total_posts": total,
            "total_comments": total_comments_count,
            "video_posts": video_count,
            "image_posts": image_count,
            "page_requests": fetch_result.page_requests,
            "stopped_by_limit": fetch_result.stopped_by_limit,
            "stopped_at": fetch_result.stopped_at_created_time or fetch_result.stopped_at_post_id,
        },
        "posts": posts_output,
    }


@app.post("/api/crawl/stream")
async def crawl_stream_api(request: Request):
    """Endpoint SSE (Server-Sent Events) giúp hiển thị tiến trình theo thời gian thực."""
    body = await request.json()
    page_id = (body.get("page_id") or "").strip() or os.getenv("FB_PAGE_ID", "").strip()
    access_token = (body.get("access_token") or "").strip() or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    since_date = (body.get("since_date") or "").strip()
    until_date = (body.get("until_date") or "").strip()
    max_posts = int(body.get("max_posts") or DEFAULT_MAX_POSTS)

    async def event_generator() -> AsyncGenerator[str, None]:
        if not page_id or not access_token:
            yield f"data: {json.dumps({'event': 'error', 'message': 'Thiếu FB_PAGE_ID hoặc FB_PAGE_ACCESS_TOKEN.'})}\n\n"
            return

        try:
            validate_date(since_date)
            validate_date(until_date)
        except ValueError as exc:
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"
            return

        yield f"data: {json.dumps({'event': 'progress', 'phase': 'posts', 'message': 'Đang tải danh sách bài viết từ Facebook...'})}\n\n"

        def progress_cb(count, req_count):
            pass

        try:
            fetch_result = fetch_posts(
                since_date=since_date,
                until_date=until_date,
                page_id=page_id,
                access_token=access_token,
                max_posts=max_posts,
                progress_callback=progress_cb,
            )
        except Exception as exc:
            yield f"data: {json.dumps({'event': 'error', 'message': f'Lỗi gọi Graph API: {exc}'})}\n\n"
            return

        posts_output = []
        total = len(fetch_result.posts)
        video_count = 0
        image_count = 0
        total_comments_count = 0

        yield f"data: {json.dumps({'event': 'progress', 'phase': 'comments_start', 'total_posts': total, 'message': f'Đã lấy {total} bài viết. Bắt đầu tải bình luận...'})}\n\n"

        for idx, post in enumerate(fetch_result.posts):
            post_id = post.get("id", "")
            yield f"data: {json.dumps({'event': 'progress', 'phase': 'comments', 'current': idx + 1, 'total': total, 'message': f'Đang lấy bình luận bài {idx + 1}/{total}...'})}\n\n"

            comments_raw = fetch_all_comments(post_id, access_token)
            comments_text = format_comments(comments_raw)
            total_comments_count += len(comments_raw)

            video_link = extract_video_link(post)
            full_picture = post.get("full_picture", "")

            if video_link:
                video_count += 1
            if full_picture:
                image_count += 1

            formatted_comments_list = []
            for c in comments_raw:
                formatted_comments_list.append({
                    "id": c.get("id", ""),
                    "author": c.get("from", {}).get("name", "Người dùng Facebook"),
                    "message": c.get("message", ""),
                    "created_time": format_local_datetime(c.get("created_time", "")),
                    "like_count": c.get("like_count", 0),
                })

            post_data = {
                "FB_PAGE_ID": page_id,
                "post_id": post_id,
                "created_time": format_local_datetime(post.get("created_time", "")),
                "permalink_url": post.get("permalink_url", ""),
                "message": post.get("message", ""),
                "full_picture": full_picture,
                "video_link": video_link,
                "comments_text": comments_text,
                "comments_list": formatted_comments_list,
                "comment_count": len(comments_raw),
            }
            posts_output.append(post_data)

            # Phát sự kiện có bài viết mới tới giao diện để render tức thì
            yield f"data: {json.dumps({'event': 'post_loaded', 'post': post_data})}\n\n"

        summary_result = {
            "event": "complete",
            "page_id": page_id,
            "since_date": since_date,
            "until_date": until_date,
            "stats": {
                "total_posts": total,
                "total_comments": total_comments_count,
                "video_posts": video_count,
                "image_posts": image_count,
                "page_requests": fetch_result.page_requests,
                "stopped_by_limit": fetch_result.stopped_by_limit,
                "stopped_at": fetch_result.stopped_at_created_time or fetch_result.stopped_at_post_id,
            },
            "posts": posts_output,
        }
        yield f"data: {json.dumps(summary_result)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def start():
    """Khởi chạy web server."""
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Dashboard Web đang chạy tại: http://localhost:{port}")
    uvicorn.run("app_web:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    start()
