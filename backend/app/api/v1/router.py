from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    blockchain,
    contracts,
    counsel_queue,
    esign,
    evidence,
    health,
    hug,
    incidents,
    landlords,
    ml,
    notifications,
    properties,
    rag,
    risk,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(properties.router)
api_router.include_router(landlords.router)
api_router.include_router(contracts.router)
api_router.include_router(evidence.router)
api_router.include_router(risk.router)
api_router.include_router(rag.router)
api_router.include_router(blockchain.router)
api_router.include_router(ml.router)
api_router.include_router(hug.router)
api_router.include_router(incidents.router)
api_router.include_router(counsel_queue.router)
api_router.include_router(esign.router)
api_router.include_router(notifications.router)
