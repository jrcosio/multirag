from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import documents, health, jobs, query

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(query.router, prefix="/query", tags=["query"])
