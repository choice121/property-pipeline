import logging

from fastapi import APIRouter, Depends, HTTPException

from database.db import get_db
from database.repository import Repository
from services import live_sync_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post('/sync/from-live')
def sync_from_live(repo: Repository = Depends(get_db)):
    try:
        stats = live_sync_service.sync_from_live(repo)
        return stats
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'Sync failed: {e}')


@router.get('/sync/status')
def get_sync_status():
    return live_sync_service.get_sync_stats()
