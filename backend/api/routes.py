# backend/api/routes.py
"""
LabIQ — API entry point
Registers all sub-routers from split modules.
"""
from fastapi import APIRouter
from api.esql     import router as esql_router
from api.patients import router as patients_router
from api.alerts   import router as alerts_router
from api.upload   import router as upload_router
from api.chat     import router as chat_router

# Single router that main.py includes
router = APIRouter()
router.include_router(esql_router)
router.include_router(patients_router)
router.include_router(alerts_router)
router.include_router(upload_router)
router.include_router(chat_router)
