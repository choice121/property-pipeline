import logging

from fastapi import APIRouter, Depends

from database.db import get_db
from database.repository import Repository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats/quality")
def quality_stats(repo: Repository = Depends(get_db)):
    """Aggregate data quality stats grouped by scrape source."""
    return repo.quality_stats_by_source()


@router.get("/stats/scrape-runs")
def scrape_runs(limit: int = 50, repo: Repository = Depends(get_db)):
    """Return the most recent scrape run logs."""
    return repo.list_scrape_runs(limit=limit)
