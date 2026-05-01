import json
import logging
import uuid
from datetime import datetime

from database.supabase_client import get_supabase
from database.repository import Repository, PropertyRecord

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    'active':   'published',
    'rented':   'rented',
    'archived': 'archived',
    'draft':    'draft',
    'paused':   'archived',
}

_sync_stats = {
    'last_sync_at':  None,
    'last_imported': 0,
    'last_updated':  0,
    'last_total':    0,
    'last_error':    None,
    'running':       False,
}

_SELECT_COLS = (
    'id,status,title,description,showing_instructions,'
    'address,city,state,zip,county,lat,lng,'
    'property_type,year_built,floors,unit_number,total_units,'
    'bedrooms,bathrooms,half_bathrooms,total_bathrooms,'
    'square_footage,lot_size_sqft,garage_spaces,'
    'monthly_rent,security_deposit,last_months_rent,application_fee,'
    'pet_deposit,admin_fee,parking_fee,move_in_special,'
    'available_date,lease_terms,minimum_lease_months,'
    'pets_allowed,pet_types_allowed,pet_weight_limit,pet_details,smoking_allowed,'
    'utilities_included,parking,amenities,appliances,flooring,'
    'heating_type,cooling_type,laundry_type,has_basement,has_central_air,'
    'virtual_tour_url,created_at,updated_at'
)
# Photos live in property_photos (id, property_id, url, file_id, display_order)
# They were columns photo_urls / photo_file_ids on properties before Choice migration
# 20260426000002.  We fetch them in a second query and join by property_id.


def get_sync_stats() -> dict:
    return dict(_sync_stats)


def _jl(val) -> str:
    if isinstance(val, list):
        return json.dumps(val)
    return '[]'


def _row_to_record(row: dict, pipeline_id: str, photo_urls: list[str] | None = None) -> PropertyRecord:
    now = datetime.utcnow().isoformat()
    av = row.get('available_date')
    return PropertyRecord(
        id=pipeline_id,
        source='live_site',
        source_url=None,
        source_listing_id=None,
        choice_property_id=row['id'],
        status=_STATUS_MAP.get(row.get('status', 'active'), 'published'),
        published_at=row.get('created_at'),
        title=row.get('title'),
        description=row.get('description'),
        showing_instructions=row.get('showing_instructions'),
        address=row.get('address'),
        city=row.get('city'),
        state=row.get('state'),
        zip=row.get('zip'),
        county=row.get('county'),
        lat=row.get('lat'),
        lng=row.get('lng'),
        property_type=row.get('property_type'),
        year_built=row.get('year_built'),
        floors=row.get('floors'),
        unit_number=row.get('unit_number'),
        total_units=row.get('total_units'),
        bedrooms=row.get('bedrooms'),
        bathrooms=row.get('bathrooms'),
        half_bathrooms=row.get('half_bathrooms'),
        total_bathrooms=row.get('total_bathrooms'),
        square_footage=row.get('square_footage'),
        lot_size_sqft=row.get('lot_size_sqft'),
        garage_spaces=row.get('garage_spaces'),
        monthly_rent=row.get('monthly_rent'),
        security_deposit=row.get('security_deposit'),
        last_months_rent=row.get('last_months_rent'),
        application_fee=row.get('application_fee'),
        pet_deposit=row.get('pet_deposit'),
        admin_fee=row.get('admin_fee'),
        parking_fee=row.get('parking_fee'),
        move_in_special=row.get('move_in_special'),
        available_date=str(av) if av else None,
        lease_terms=_jl(row.get('lease_terms')),
        minimum_lease_months=row.get('minimum_lease_months'),
        pets_allowed=row.get('pets_allowed', False),
        pet_types_allowed=_jl(row.get('pet_types_allowed')),
        pet_weight_limit=row.get('pet_weight_limit'),
        pet_details=row.get('pet_details'),
        smoking_allowed=row.get('smoking_allowed', False),
        utilities_included=_jl(row.get('utilities_included')),
        parking=row.get('parking'),
        amenities=_jl(row.get('amenities')),
        appliances=_jl(row.get('appliances')),
        flooring=_jl(row.get('flooring')),
        heating_type=row.get('heating_type'),
        cooling_type=row.get('cooling_type'),
        laundry_type=row.get('laundry_type'),
        has_basement=row.get('has_basement', False),
        has_central_air=row.get('has_central_air', False),
        virtual_tour_url=row.get('virtual_tour_url'),
        # Photos now come from property_photos table (url ordered by display_order)
        original_image_urls=json.dumps(photo_urls or []),
        local_image_paths='[]',
        original_data='{}',
        edited_fields='[]',
        missing_fields='[]',
        inferred_features='[]',
        scraped_at=row.get('created_at') or now,
        updated_at=now,
    )


def _update_existing(prop: PropertyRecord, row: dict, repo: Repository) -> bool:
    """
    Update pipeline fields from live site for a property that already exists.
    Only updates fields that haven't been manually edited in the pipeline.
    Returns True if anything changed.
    """
    try:
        edited_fields = json.loads(prop.edited_fields or '[]')
    except Exception:
        edited_fields = []

    changed = False
    scalar_fields = [
        'title', 'description', 'showing_instructions', 'address', 'city',
        'state', 'zip', 'county', 'lat', 'lng', 'property_type', 'year_built',
        'floors', 'unit_number', 'total_units', 'bedrooms', 'bathrooms',
        'half_bathrooms', 'total_bathrooms', 'square_footage', 'lot_size_sqft',
        'garage_spaces', 'monthly_rent', 'security_deposit', 'last_months_rent',
        'application_fee', 'pet_deposit', 'admin_fee', 'parking_fee',
        'move_in_special', 'minimum_lease_months', 'pets_allowed',
        'pet_weight_limit', 'pet_details', 'smoking_allowed', 'parking',
        'heating_type', 'cooling_type', 'laundry_type', 'has_basement',
        'has_central_air', 'virtual_tour_url',
    ]
    array_fields = [
        'lease_terms', 'pet_types_allowed', 'utilities_included',
        'amenities', 'appliances', 'flooring',
    ]

    for field in scalar_fields:
        if field in edited_fields:
            continue
        live_val = row.get(field)
        current_val = getattr(prop, field, None)
        if live_val != current_val:
            setattr(prop, field, live_val)
            changed = True

    for field in array_fields:
        if field in edited_fields:
            continue
        live_val = _jl(row.get(field))
        current_val = getattr(prop, field, '[]')
        if live_val != current_val:
            setattr(prop, field, live_val)
            changed = True

    av = row.get('available_date')
    if 'available_date' not in edited_fields:
        new_av = str(av) if av else None
        if new_av != prop.available_date:
            prop.available_date = new_av
            changed = True

    live_status = _STATUS_MAP.get(row.get('status', 'active'), 'published')
    if live_status != prop.status and prop.status not in ('draft', 'edited'):
        prop.status = live_status
        changed = True

    if changed:
        prop.updated_at = datetime.utcnow().isoformat()
        repo.save(prop)

    return changed


def _fetch_photos_by_property(sb) -> dict[str, list[str]]:
    """Fetch all property_photos rows and return a dict of property_id → [url, ...] sorted by display_order."""
    try:
        result = sb.table('property_photos').select(
            'property_id,url,display_order'
        ).order('display_order', desc=False).execute()
        photos: dict[str, list[str]] = {}
        for row in (result.data or []):
            pid = row.get('property_id')
            url = row.get('url')
            if pid and url:
                photos.setdefault(pid, []).append(url)
        return photos
    except Exception as e:
        logger.warning('Could not fetch property_photos: %s', e)
        return {}


def sync_from_live(repo: Repository) -> dict:
    global _sync_stats
    _sync_stats['running'] = True

    try:
        from services import setup_service
        readiness = setup_service.get_setup_status()
        if not readiness['core_ready']:
            raise RuntimeError(readiness['summary'])

        sb = get_supabase()

        # Fetch live properties and their photos (two queries, joined in Python)
        result = sb.table('properties').select(_SELECT_COLS).execute()
        live_props = result.data or []
        photos_by_property = _fetch_photos_by_property(sb)

        all_pipeline = repo.list()
        tracked = {p.choice_property_id: p for p in all_pipeline if p.choice_property_id}

        imported = 0
        updated = 0

        for row in live_props:
            supabase_id = row['id']
            photo_urls = photos_by_property.get(supabase_id, [])
            if supabase_id in tracked:
                did_update = _update_existing(tracked[supabase_id], row, repo)
                if did_update:
                    updated += 1
            else:
                new_id = str(uuid.uuid4())
                prop = _row_to_record(row, new_id, photo_urls=photo_urls)
                repo.save(prop)
                imported += 1

        _sync_stats = {
            'last_sync_at':  datetime.utcnow().isoformat(),
            'last_imported': imported,
            'last_updated':  updated,
            'last_total':    len(live_props),
            'last_error':    None,
            'running':       False,
        }
        logger.info('Live sync: imported=%d updated=%d total=%d', imported, updated, len(live_props))
        return {'imported': imported, 'updated': updated, 'total': len(live_props)}

    except Exception as e:
        logger.error('Live sync failed: %s', e)
        _sync_stats['last_error'] = str(e)
        _sync_stats['last_sync_at'] = datetime.utcnow().isoformat()
        _sync_stats['running'] = False
        raise
