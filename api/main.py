from contextlib import asynccontextmanager
from api.utils.database import engine as db_engine
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from api.utils.middlewares import LimitUploadSize
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from api.utils.security import (
    verify_api_key,
    verify_jwt,
    limiter,
)
from api.utils.logger import logger, trace_id_var
import uuid
# Importamos execute en lugar de retry
from api.routers import config, ingest, execute, process 
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.utils.models import Base
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized.")
    yield


app = FastAPI(
    title="Slancio", # <-- Cambiamos el nombre
    description="Dynamic Margin Optimizer and Cart Recovery Engine", # <-- Y la descripción
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def inject_trace_id(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response

@app.get("/health", tags=['System'])
async def health_check():
    return {"status": "ok", "trace_id": trace_id_var.get()}

app.include_router(config.router, dependencies=[Depends(verify_jwt)])
app.include_router(ingest.router, prefix="/webhook")
app.include_router(process.router, prefix="/webhook")
app.include_router(execute.router, prefix="/webhook") # <-- Enchufamos execute

app.add_middleware(LimitUploadSize)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # (El handler de validación queda exactamente igual)
    logger.error(f"Payload validation rejected: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_failed",
            "message": "The payload doesnt follow the correct schema",
            "trace_id": trace_id_var.get(),
            "details": [
                {
                    "field": " -> ".join([str(loc) for loc in error["loc"]]),
                    "issue": error["msg"],
                }
                for error in exc.errors()
            ],
        },
    )