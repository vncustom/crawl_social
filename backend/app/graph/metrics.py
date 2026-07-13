from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    candidates: tuple[str, ...]
    period: str
    additive: bool
    unit: str


METRICS = {
    "daily_new_followers": MetricDefinition(
        ("page_daily_follows_unique", "page_daily_follows"), "day", True, "people"
    ),
    "followers_total": MetricDefinition(("page_follows",), "day", False, "people"),
    "post_engagements": MetricDefinition(
        ("page_post_engagements",), "day", True, "interactions"
    ),
    "video_views": MetricDefinition(("page_video_views",), "day", True, "views"),
    "page_views": MetricDefinition(("page_views_total",), "day", True, "views"),
}
