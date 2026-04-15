import logging
import os

from imagekitio import ImageKit

logger = logging.getLogger(__name__)


def _get_ik() -> ImageKit:
    return ImageKit(private_key=os.environ["IMAGEKIT_PRIVATE_KEY"])


def delete_file(file_id: str) -> None:
    ik = _get_ik()
    ik.files.delete(file_id)
    logger.info('Deleted ImageKit file: %s', file_id)


def upload_file(file_bytes: bytes, filename: str, property_id: str) -> dict:
    ik = _get_ik()
    result = ik.files.upload(
        file=file_bytes,
        file_name=filename,
        folder=f'/properties/{property_id}',
    )
    logger.info('Uploaded to ImageKit: %s → %s', filename, result.url)
    return {'url': result.url, 'file_id': result.file_id}
