from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool

from ip_sakti.config import Settings
from ip_sakti.storage.mongo import create_client, initialize_database
from ip_sakti.embeddings.local import LocalEmbedder
from ip_sakti.retrieval.search import RetrievalService
from ip_sakti.api.search import router as search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    client = create_client(settings)
    try:
        await run_in_threadpool(client.admin.command, "ping")
        await run_in_threadpool(initialize_database, client[settings.database])
        app.state.client = client
        app.state.database = settings.database
        app.state.retrieval = RetrievalService(client[settings.database], LocalEmbedder(
            settings.embedding_device, settings.embedding_model,
            settings.embedding_revision, settings.embedding_batch_size))
        app.state.retrieval_lock = Lock()
        yield
    finally:
        client.close()


app = FastAPI(title="IP-SAKTI corpus service", lifespan=lifespan)
app.include_router(search_router)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(request: Request):
    try:
        request.app.state.client.admin.command("ping")
    except PyMongoError:
        return JSONResponse(status_code=503, content={"status": "database_unavailable"})
    return {"status": "ready", "database": request.app.state.database}

