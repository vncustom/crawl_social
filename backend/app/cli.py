import argparse
import getpass
from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.graph.client import GraphClient
from app.models import AdminUser, JobType, Page
from app.sync.jobs import enqueue_job


class SeedSettings(Protocol):
    default_page_id: str
    report_timezone: str


class PageIdentityClient(Protocol):
    def get_page_identity(self, page_id: str) -> dict: ...


def create_admin(username: str) -> None:
    password = getpass.getpass("Mật khẩu: ")
    confirmation = getpass.getpass("Nhập lại mật khẩu: ")
    if password != confirmation:
        raise SystemExit("Mật khẩu nhập lại không khớp.")
    if len(password) < 12:
        raise SystemExit("Mật khẩu phải có ít nhất 12 ký tự.")
    with SessionLocal() as db:
        if db.scalar(select(AdminUser).where(AdminUser.username == username)):
            raise SystemExit("Tài khoản đã tồn tại.")
        db.add(AdminUser(username=username, password_hash=hash_password(password)))
        db.commit()


def seed_default_page(
    db: Session,
    graph: PageIdentityClient,
    settings: SeedSettings,
    *,
    today: date | None = None,
) -> tuple[Page, bool]:
    existing = db.scalar(
        select(Page).where(Page.external_page_id == settings.default_page_id)
    )
    if existing:
        return existing, False

    identity = graph.get_page_identity(settings.default_page_id)
    page = Page(
        external_page_id=settings.default_page_id,
        display_name=identity.get("name") or settings.default_page_id,
        category=identity.get("category"),
        public_link=identity.get("link"),
    )
    db.add(page)
    db.commit()
    report_day = today or datetime.now(ZoneInfo(settings.report_timezone)).date()
    enqueue_job(
        db,
        page.id,
        JobType.backfill,
        report_day - timedelta(days=89),
        report_day,
        None,
    )
    return page, True


def run_seed_default_page(settings: Settings | None = None) -> None:
    current = settings or get_settings()
    graph = GraphClient(current.fb_page_access_token, current.fb_graph_version)
    try:
        with SessionLocal() as db:
            page, created = seed_default_page(db, graph, current)
    finally:
        graph.close()
    action = "Đã tạo" if created else "Đã tồn tại"
    print(f"{action} Page {page.external_page_id} ({page.display_name}).")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-admin")
    create.add_argument("--username", required=True)
    subparsers.add_parser("seed-default-page")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.username)
    elif args.command == "seed-default-page":
        run_seed_default_page()


if __name__ == "__main__":
    main()
