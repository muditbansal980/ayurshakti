from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool

from ip_sakti.config import Settings
from ip_sakti.storage.mongo import create_client, initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    client = create_client(settings)
    try:
        await run_in_threadpool(client.admin.command, "ping")
        await run_in_threadpool(initialize_database, client[settings.database])
        app.state.client = client
        app.state.database = settings.database
        yield
    finally:
        client.close()


app = FastAPI(title="IP-SAKTI corpus service", lifespan=lifespan)


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

