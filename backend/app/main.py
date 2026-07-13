from fastapi import FastAPI

from app.routers.auth import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="Facebook Reporting API")
    app.include_router(auth_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
