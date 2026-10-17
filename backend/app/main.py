from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import Settings
from app.core.database import make_engine, session_factory


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or Settings()
    owned_engine = engine is None
    engine = engine if engine is not None else make_engine(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(app):
        yield
        if owned_engine:
            engine.dispose()

    app = FastAPI(title="REBOOTX Backend", version="0.1.0", lifespan=lifespan)
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.sessions = session_factory(engine)
    app.include_router(router)
    return app


app = create_app()
