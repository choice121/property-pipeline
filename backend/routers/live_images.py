import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from database.db import get_db
from database.repository import Repository
from database.supabase_client import get_supabase
from services import imagekit_service

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
MAX_BYTES = 15 * 1024 * 1024


def _require_live(prop):
    if not prop:
        raise HTTPException(status_code=404, detail='Property not found')
    if not prop.choice_property_id:
        raise HTTPException(status_code=400, detail='Property is not linked to the live site')


def _fetch_photos(supabase_id: str) -> tuple[list, list]:
    sb = get_supabase()
    res = (
        sb.table('properties')
        .select('photo_urls,photo_file_ids')
        .eq('id', supabase_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail='Property not found on live site')
    row = res.data[0]
    return (row.get('photo_urls') or []), (row.get('photo_file_ids') or [])


def _save_photos(supabase_id: str, urls: list, file_ids: list) -> list:
    sb = get_supabase()
    sb.table('properties').update({
        'photo_urls': urls,
        'photo_file_ids': file_ids,
    }).eq('id', supabase_id).execute()
    return [{'url': u, 'file_id': f} for u, f in zip(urls, file_ids)]


@router.get('/live-images/{id}')
def get_live_images(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    _require_live(prop)
    urls, file_ids = _fetch_photos(prop.choice_property_id)
    photos = [{'url': u, 'file_id': f} for u, f in zip(urls, file_ids)]
    return {'photos': photos, 'count': len(photos)}


@router.delete('/live-images/{id}/{file_id}')
def delete_live_image(id: str, file_id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    _require_live(prop)

    urls, file_ids = _fetch_photos(prop.choice_property_id)
    if file_id not in file_ids:
        raise HTTPException(status_code=404, detail='Image not found')

    try:
        imagekit_service.delete_file(file_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'ImageKit delete failed: {e}')

    idx = file_ids.index(file_id)
    new_urls = [u for i, u in enumerate(urls) if i != idx]
    new_ids = [f for i, f in enumerate(file_ids) if i != idx]
    photos = _save_photos(prop.choice_property_id, new_urls, new_ids)
    return {'ok': True, 'photos': photos}


@router.put('/live-images/{id}/reorder')
def reorder_live_images(id: str, body: dict, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    _require_live(prop)

    order = body.get('order', [])
    urls, file_ids = _fetch_photos(prop.choice_property_id)

    if len(order) != len(urls) or sorted(order) != list(range(len(urls))):
        raise HTTPException(status_code=400, detail='Invalid reorder indices')

    new_urls = [urls[i] for i in order]
    new_ids = [file_ids[i] for i in order]
    photos = _save_photos(prop.choice_property_id, new_urls, new_ids)
    return {'ok': True, 'photos': photos}


@router.post('/live-images/{id}/upload')
async def upload_live_image(
    id: str,
    file: UploadFile = File(...),
    repo: Repository = Depends(get_db),
):
    prop = repo.get(id)
    _require_live(prop)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail='Invalid file type. Use JPEG, PNG, or WebP.')

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail='File too large (max 15 MB)')

    try:
        result = imagekit_service.upload_file(
            content,
            file.filename or 'photo.jpg',
            prop.choice_property_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'Upload failed: {e}')

    urls, file_ids = _fetch_photos(prop.choice_property_id)
    new_urls = urls + [result['url']]
    new_ids = file_ids + [result['file_id']]
    photos = _save_photos(prop.choice_property_id, new_urls, new_ids)
    return {'ok': True, 'photo': result, 'photos': photos}
