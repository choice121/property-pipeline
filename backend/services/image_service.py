import os
import shutil
from typing import List

import httpx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "images")


def get_property_dir(property_id: str) -> str:
    return os.path.join(STORAGE_DIR, property_id)


def download_images(property_id: str, image_urls: list) -> List[str]:
    prop_dir = get_property_dir(property_id)
    os.makedirs(prop_dir, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    saved_paths = []
    counter = 1

    for url in image_urls[:20]:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                continue
            if len(resp.content) < 5 * 1024:
                continue
            filepath = os.path.join(prop_dir, f"{counter}.jpg")
            with open(filepath, "wb") as f:
                f.write(resp.content)
            saved_paths.append(f"storage/images/{property_id}/{counter}.jpg")
            counter += 1
        except Exception:
            continue

    return saved_paths


def delete_image(property_id: str, index: int) -> List[str]:
    prop_dir = get_property_dir(property_id)
    target = os.path.join(prop_dir, f"{index}.jpg")

    if os.path.exists(target):
        os.remove(target)

    existing = sorted(
        [f for f in os.listdir(prop_dir) if f.endswith(".jpg")],
        key=lambda x: int(x.split(".")[0])
    )

    for i, fname in enumerate(existing, start=1):
        old_path = os.path.join(prop_dir, fname)
        new_path = os.path.join(prop_dir, f"{i}.jpg")
        if old_path != new_path:
            os.rename(old_path, new_path)

    total = len(existing)
    return [f"storage/images/{property_id}/{i}.jpg" for i in range(1, total + 1)]


def reorder_images(property_id: str, new_order: List[int]) -> List[str]:
    prop_dir = get_property_dir(property_id)

    temp_names = []
    for i, original_index in enumerate(new_order):
        src = os.path.join(prop_dir, f"{original_index}.jpg")
        tmp = os.path.join(prop_dir, f"tmp_{i}.jpg")
        if os.path.exists(src):
            os.rename(src, tmp)
            temp_names.append((i + 1, tmp))

    new_paths = []
    for final_index, tmp_path in temp_names:
        dest = os.path.join(prop_dir, f"{final_index}.jpg")
        os.rename(tmp_path, dest)
        new_paths.append(f"storage/images/{property_id}/{final_index}.jpg")

    return new_paths
