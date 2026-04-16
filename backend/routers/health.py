from fastapi import APIRouter
from services import setup_service

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/setup/status")
def setup_status():
    return setup_service.get_setup_status()
