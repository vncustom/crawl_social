from collections.abc import Iterator
from datetime import datetime
from typing import Any

import httpx


POST_FIELDS = ",".join(
    [
        "id",
        "message",
        "created_time",
        "permalink_url",
        "attachments{media,type,url,target,subattachments}",
        "comments.summary(true).limit(0)",
        "reactions.summary(true).limit(0)",
        "shares",
    ]
)


class GraphAPIError(RuntimeError):
    def __init__(self, kind: str, code: int | None, message: str):
        self.kind = kind
        self.code = code
        super().__init__(message)


def classify_error(status_code: int, code: int | None) -> str:
    if code == 190:
        return "authentication"
    if code in {10, 200, 299}:
        return "permission"
    if code in {4, 17, 32, 613} or status_code == 429:
        return "rate_limit"
    if status_code >= 500:
        return "transient"
    return "invalid_request"


class GraphClient:
    def __init__(
        self,
        access_token: str,
        version: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._access_token = access_token
        self._client = httpx.Client(
            base_url=f"https://graph.facebook.com/{version}/",
            timeout=60,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.get(url, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise GraphAPIError("transient", None, "Facebook Graph API tạm thời không kết nối được.") from exc
        if response.is_success:
            return response.json()
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        code = error.get("code")
        raw_message = str(error.get("message") or "Facebook Graph API trả về lỗi.")
        safe_message = raw_message.replace(self._access_token, "[REDACTED]")
        raise GraphAPIError(classify_error(response.status_code, code), code, safe_message)

    def get_page_identity(self, page_id: str) -> dict[str, Any]:
        return self._request(
            page_id,
            {
                "access_token": self._access_token,
                "fields": "id,name,category,link,followers_count,fan_count",
            },
        )

    def _iterate(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        url: str | None = path
        request_params: dict[str, Any] | None = params
        while url:
            payload = self._request(url, request_params)
            yield from payload.get("data", [])
            url = payload.get("paging", {}).get("next")
            request_params = None

    def iter_posts(
        self,
        page_id: str,
        since: datetime,
        until: datetime,
    ) -> Iterator[dict[str, Any]]:
        return self._iterate(
            f"{page_id}/posts",
            {
                "access_token": self._access_token,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "limit": 100,
                "fields": POST_FIELDS,
            },
        )

    def iter_insights(self, page_id: str, metrics: tuple[str, ...], since: datetime, until: datetime) -> Iterator[dict[str, Any]]:
        return self._iterate(
            f"{page_id}/insights",
            {"access_token": self._access_token, "metric": ",".join(metrics), "period": "day", "since": since.isoformat(), "until": until.isoformat()},
        )

    def iter_videos(self, page_id: str, since: datetime, until: datetime) -> Iterator[dict[str, Any]]:
        return self._iterate(
            f"{page_id}/videos",
            {"access_token": self._access_token, "since": since.isoformat(), "until": until.isoformat(), "fields": "id,title,description,created_time,length,permalink_url"},
        )

    def iter_comments(self, post_id: str) -> Iterator[dict[str, Any]]:
        return self._iterate(
            f"{post_id}/comments",
            {"access_token": self._access_token, "limit": 100, "fields": "id,created_time,message,from,like_count,comment_count"},
        )
