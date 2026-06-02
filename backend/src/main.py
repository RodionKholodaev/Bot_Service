import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.logger_config import setup_logging
from src.config import settings
from src.database import Base, engine
from src.routers import auth, bots, api_keys, user, stats, payments
from src.services import docker_manager
from src.core.exception_handlers import register_exception_handlers
from src.services.polling_worker import run_polling_worker
import asyncio

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    settings.BOTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"BOTS_DATA_DIR = {settings.BOTS_DATA_DIR.resolve()}")

    try:
        docker_manager.ensure_network()
    except Exception as e:
        logger.warning(f"Не удалось подготовить Docker-сеть: {e}")
        logger.warning("Убедись, что Docker Desktop запущен")

    task = asyncio.create_task(run_polling_worker())
    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # ── shutdown ── (контейнеры ботов специально не трогаем — пусть продолжают работать)


app = FastAPI(title="CryptoBot API", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bots.router)
app.include_router(api_keys.router)
app.include_router(user.router)
app.include_router(stats.router)
app.include_router(payments.router)
# app.include_router(support.router)

@app.get("/health")
def health():
    return {"status": "ok"}
