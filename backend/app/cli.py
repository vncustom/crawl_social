import argparse
import getpass

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import AdminUser


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


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-admin")
    create.add_argument("--username", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.username)


if __name__ == "__main__":
    main()
