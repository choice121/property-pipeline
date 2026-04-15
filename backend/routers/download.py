import base64
import io
import json
import os
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from database.db import get_db
from database.repository import PropertyRecord, Repository

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "images")


def fmt(val, suffix="", fallback="N/A"):
    if val is None or val == "" or val == []:
        return fallback
    return f"{val}{suffix}"


def fmt_price(val):
    if val is None:
        return "N/A"
    return f"${int(val):,}/mo"


def build_details_txt(p: PropertyRecord) -> str:
    lines = [
        "PROPERTY DETAILS",
        "=" * 48,
        f"ID:              {p.id}",
        f"Status:          {p.status or 'N/A'}",
        "",
        "LOCATION",
        "-" * 48,
        f"Address:         {p.address or 'N/A'}",
        f"City:            {p.city or 'N/A'}",
        f"State:           {p.state or 'N/A'}",
        f"Zip:             {p.zip or 'N/A'}",
        f"County:          {p.county or 'N/A'}",
        f"Coordinates:     {p.lat or 'N/A'}, {p.lng or 'N/A'}",
        "",
        "DETAILS",
        "-" * 48,
        f"Property Type:   {p.property_type or 'N/A'}",
        f"Bedrooms:        {fmt(p.bedrooms)}",
        f"Bathrooms:       {fmt(p.bathrooms)}",
        f"Half Bathrooms:  {fmt(p.half_bathrooms)}",
        f"Total Bathrooms: {fmt(p.total_bathrooms)}",
        f"Square Footage:  {f'{p.square_footage:,} sqft' if p.square_footage else 'N/A'}",
        f"Lot Size:        {f'{p.lot_size_sqft:,} sqft' if p.lot_size_sqft else 'N/A'}",
        f"Year Built:      {fmt(p.year_built)}",
        f"Garage Spaces:   {fmt(p.garage_spaces)}",
        f"Basement:        {'Yes' if p.has_basement else 'No'}",
        f"Central Air:     {'Yes' if p.has_central_air else 'No'}",
        "",
        "PRICING",
        "-" * 48,
        f"Monthly Rent:    {fmt_price(p.monthly_rent)}",
        f"Security Deposit:{fmt_price(p.security_deposit)}",
        f"Application Fee: {fmt_price(p.application_fee)}",
        "",
        "POLICIES",
        "-" * 48,
        f"Pets Allowed:    {'Yes' if p.pets_allowed else 'No'}",
        f"Pet Details:     {p.pet_details or 'N/A'}",
        f"Smoking Allowed: {'Yes' if p.smoking_allowed else 'No'}",
        f"Parking:         {p.parking or 'N/A'}",
        f"Heating Type:    {p.heating_type or 'N/A'}",
        f"Cooling Type:    {p.cooling_type or 'N/A'}",
        f"Laundry Type:    {p.laundry_type or 'N/A'}",
        "",
        "DESCRIPTION",
        "-" * 48,
        p.description or "No description available.",
        "",
        "SOURCE",
        "-" * 48,
        f"Source:          {p.source or 'N/A'}",
        f"Source URL:      {p.source_url or 'N/A'}",
        f"Listing ID:      {p.source_listing_id or 'N/A'}",
        f"Scraped At:      {p.scraped_at or 'N/A'}",
        f"Downloaded At:   {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    ]

    amenities = []
    try:
        amenities = json.loads(p.amenities or "[]")
    except Exception:
        pass
    if amenities:
        lines += ["", "AMENITIES", "-" * 48]
        for a in amenities:
            lines.append(f"  • {a}")

    return "\n".join(lines)


def build_property_html(p: PropertyRecord, image_data: list) -> str:
    def safe(val, fallback="—"):
        return str(val) if val is not None else fallback

    price = fmt_price(p.monthly_rent)
    beds = f"{p.bedrooms} bd" if p.bedrooms is not None else "—"
    baths = f"{p.bathrooms} ba" if p.bathrooms is not None else "—"
    sqft = f"{p.square_footage:,} sqft" if p.square_footage else "—"
    ptype = p.property_type or "—"
    year = str(p.year_built) if p.year_built else "—"
    address_line = ", ".join(filter(None, [p.address, p.city, p.state, p.zip]))

    amenities = []
    try:
        amenities = json.loads(p.amenities or "[]")
    except Exception:
        pass

    amenity_html = ""
    if amenities:
        items = "".join(
            f'<span style="display:inline-block;background:#f3f4f6;border-radius:999px;'
            f'padding:4px 12px;font-size:13px;margin:3px;">{a}</span>'
            for a in amenities
        )
        amenity_html = (
            f'<div style="margin-top:24px"><h3 style="font-size:14px;font-weight:600;'
            f'color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">'
            f'Amenities</h3><div>{items}</div></div>'
        )

    images_html = ""
    for i, (mime, b64) in enumerate(image_data):
        label = "Hero Photo" if i == 0 else f"Photo {i + 1}"
        images_html += (
            f'<div style="margin-bottom:12px">'
            f'<img src="data:{mime};base64,{b64}" alt="{label}" '
            f'style="width:100%;border-radius:10px;display:block;max-height:420px;object-fit:cover;" />'
            f'</div>'
        )

    source_link = ""
    if p.source_url:
        source_link = (
            f'<p style="margin-top:8px;font-size:13px;color:#6b7280">Source: '
            f'<a href="{p.source_url}" style="color:#2563eb">{p.source_url}</a></p>'
        )

    description_html = ""
    if p.description:
        desc = p.description.replace("<", "&lt;").replace(">", "&gt;")
        description_html = (
            f'<div style="margin-top:24px">'
            f'<h3 style="font-size:14px;font-weight:600;color:#6b7280;'
            f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Description</h3>'
            f'<p style="font-size:15px;line-height:1.7;color:#374151">{desc}</p></div>'
        )

    policies = []
    if p.pets_allowed is not None:
        policies.append(f"Pets: {'Allowed' if p.pets_allowed else 'Not Allowed'}")
    if p.parking:
        policies.append(f"Parking: {p.parking}")
    if p.smoking_allowed is not None:
        policies.append(f"Smoking: {'Allowed' if p.smoking_allowed else 'Not Allowed'}")

    policies_html = ""
    if policies:
        items = "".join(
            f'<li style="padding:6px 0;border-bottom:1px solid #f3f4f6;'
            f'font-size:14px;color:#374151">{po}</li>'
            for po in policies
        )
        policies_html = (
            f'<div style="margin-top:24px"><h3 style="font-size:14px;font-weight:600;'
            f'color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">'
            f'Policies</h3><ul style="list-style:none;padding:0;margin:0">{items}</ul></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{address_line or 'Property'}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f9fafb; color: #111827; }}
  .container {{ max-width: 680px; margin: 0 auto; padding: 20px 16px 60px; }}
  .badge {{ display: inline-block; background: #111827; color: #fff; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 12px; }}
</style>
</head>
<body>
<div class="container">
  <span class="badge">{safe(p.status)}</span>
  <h1 style="font-size:22px;font-weight:700;line-height:1.3;margin-bottom:4px">{address_line or 'Property'}</h1>
  <p style="font-size:26px;font-weight:800;color:#111827;margin:8px 0">{price}</p>
  <div style="display:flex;flex-wrap:wrap;gap:16px;margin:14px 0 20px;font-size:15px;color:#374151">
    <span><strong>{beds}</strong></span>
    <span><strong>{baths}</strong></span>
    <span><strong>{sqft}</strong></span>
    <span style="color:#6b7280">{ptype}</span>
    <span style="color:#6b7280">Built {year}</span>
  </div>
  {images_html if images_html else '<div style="background:#f3f4f6;border-radius:10px;height:200px;display:flex;align-items:center;justify-content:center;color:#9ca3af;font-size:14px">No photos available</div>'}
  {description_html}
  {amenity_html}
  {policies_html}
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb">
    <p style="font-size:13px;color:#9ca3af">Property ID: {p.id} &nbsp;·&nbsp; Scraped: {(str(p.scraped_at) or '')[:10]}</p>
    {source_link}
    <p style="font-size:12px;color:#d1d5db;margin-top:6px">Downloaded {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · Choice Properties Pipeline</p>
  </div>
</div>
</body>
</html>"""


def safe_zip_name(p: PropertyRecord) -> str:
    parts = []
    if p.bedrooms is not None:
        parts.append(f"{p.bedrooms}BR")
    if p.property_type:
        parts.append(p.property_type.replace("_", "-").title())
    if p.city:
        parts.append(p.city.replace(" ", "-"))
    if p.state:
        parts.append(p.state)
    if not parts:
        parts.append(p.id)
    return "_".join(parts)


@router.get("/properties/{id}/download")
def download_property(id: str, repo: Repository = Depends(get_db)):
    prop = repo.get(id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        local_paths = json.loads(prop.local_image_paths or "[]")
    except Exception:
        local_paths = []

    image_data = []
    for path in local_paths:
        parts = path.replace("\\", "/").split("/")
        if len(parts) >= 2:
            prop_id = parts[-2]
            filename = parts[-1]
            filepath = os.path.join(STORAGE_DIR, prop_id, filename)
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    raw = f.read()
                b64 = base64.b64encode(raw).decode("utf-8")
                image_data.append(("image/jpeg", b64, filepath, filename))

    zip_buffer = io.BytesIO()
    folder_name = safe_zip_name(prop)

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (mime, b64, filepath, filename) in enumerate(image_data):
            with open(filepath, "rb") as f:
                raw = f.read()
            zip_filename = f"{folder_name}/hero.jpg" if i == 0 else f"{folder_name}/photo-{i + 1:02d}.jpg"
            zf.writestr(zip_filename, raw)

        details_txt = build_details_txt(prop)
        zf.writestr(f"{folder_name}/details.txt", details_txt)

        inline_images = [(mime, b64) for mime, b64, _, _ in image_data]
        html_content = build_property_html(prop, inline_images)
        zf.writestr(f"{folder_name}/property.html", html_content)

    zip_buffer.seek(0)
    zip_filename_dl = f"{folder_name}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename_dl}"'},
    )
