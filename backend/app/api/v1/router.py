from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, blockchain, contracts, evidence, health, landlords, properties, rag, risk, users

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
