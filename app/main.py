from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.routers import address, audit_logs, boundaries, geocode, legal_documents, units


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title="GIS Admin API",
    description="API khai thác dữ liệu địa giới hành chính Việt Nam (gis_admin) trên MongoDB Atlas",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(units.router, prefix=settings.api_prefix)
app.include_router(boundaries.router, prefix=settings.api_prefix)
app.include_router(legal_documents.router, prefix=settings.api_prefix)
app.include_router(audit_logs.router, prefix=settings.api_prefix)
app.include_router(address.router, prefix=settings.api_prefix)
app.include_router(geocode.router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
