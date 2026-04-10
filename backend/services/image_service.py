import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import httpx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "images")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_property_dir(property_id: str) -> str:
    return os.path.join(STORAGE_DIR, property_id)


def _download_one(url: str, filepath: str) -> bool:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            return False
        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            return False
        if len(resp.content) < 5 * 1024:
            return False
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return True
    except Exception:
        return False


def download_images(property_id: str, image_urls: list) -> List[str]:
    prop_dir = get_property_dir(property_id)
    os.makedirs(prop_dir, exist_ok=True)

    indexed = list(enumerate(image_urls, start=1))

    def fetch(args):
        index, url = args
        filepath = os.path.join(prop_dir, f"{index}.jpg")
        success = _download_one(url, filepath)
        return index, success

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch, item): item[0] for item in indexed}
        for future in as_completed(futures):
            index, success = future.result()
            results[index] = success

    saved_indices = sorted(i for i, ok in results.items() if ok)

    final_paths = []
    for new_pos, old_index in enumerate(saved_indices, start=1):
        old_path = os.path.join(prop_dir, f"{old_index}.jpg")
        new_path = os.path.join(prop_dir, f"{new_pos}.jpg")
        if old_path != new_path and os.path.exists(old_path):
            os.rename(old_path, new_path)
        final_paths.append(f"storage/images/{property_id}/{new_pos}.jpg")

    return final_paths


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
