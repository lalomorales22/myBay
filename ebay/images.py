"""
eBay Image Upload via Trading API (UploadSiteHostedPictures)

Uploads image files directly to eBay's picture servers.
Returns permanent https://i.ebayimg.com/... URLs for use in listings.
"""

import os
import mimetypes
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from xml.etree import ElementTree as ET

import httpx

from .config import get_config
from .auth import get_auth

# Max image size eBay accepts (12 MB)
MAX_IMAGE_SIZE = 12 * 1024 * 1024

# Supported image formats
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}

# Trading API compatibility level
COMPATIBILITY_LEVEL = "967"


@dataclass
class ImageUploadResult:
    """Result of a single image upload."""
    filepath: str
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BatchUploadResult:
    """Result of uploading multiple images."""
    results: list[ImageUploadResult] = field(default_factory=list)

    @property
    def successful_urls(self) -> list[str]:
        return [r.url for r in self.results if r.success and r.url]

    @property
    def failed(self) -> list[ImageUploadResult]:
        return [r for r in self.results if not r.success]

    @property
    def all_successful(self) -> bool:
        return len(self.results) > 0 and all(r.success for r in self.results)

    @property
    def any_successful(self) -> bool:
        return any(r.success for r in self.results)


def _validate_image(filepath: str) -> Optional[str]:
    """Validate an image file. Returns error string or None if valid."""
    path = Path(filepath)
    if not path.exists():
        return f"File not found: {filepath}"
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return f"Unsupported format '{path.suffix}' — use {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    size = path.stat().st_size
    if size > MAX_IMAGE_SIZE:
        return f"File too large ({size / 1024 / 1024:.1f} MB) — max {MAX_IMAGE_SIZE / 1024 / 1024:.0f} MB"
    if size == 0:
        return "File is empty"
    return None


def _build_upload_xml() -> str:
    """Build the XML request body for UploadSiteHostedPictures."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
        '<PictureSet>Supersize</PictureSet>'
        '</UploadSiteHostedPicturesRequest>'
    )


def _parse_upload_response(xml_text: str) -> tuple[Optional[str], Optional[str]]:
    """Parse XML response. Returns (url, error)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return None, f"Failed to parse eBay response: {e}"

    ns = {"e": "urn:ebay:apis:eBLBaseComponents"}

    ack = root.findtext("e:Ack", namespaces=ns) or root.findtext("Ack") or ""
    if ack.lower() not in ("success", "warning"):
        errors = root.findall("e:Errors", namespaces=ns) or root.findall("Errors")
        msg_parts = []
        for err in errors:
            short = err.findtext("e:ShortMessage", namespaces=ns) or err.findtext("ShortMessage") or ""
            long_msg = err.findtext("e:LongMessage", namespaces=ns) or err.findtext("LongMessage") or ""
            msg_parts.append(long_msg or short)
        return None, "; ".join(msg_parts) or f"eBay returned Ack={ack}"

    full_url = (
        root.findtext(".//e:SiteHostedPictureDetails/e:FullURL", namespaces=ns)
        or root.findtext(".//SiteHostedPictureDetails/FullURL")
    )
    if not full_url:
        return None, "eBay response missing FullURL"

    return full_url, None


class EbayImages:
    """Uploads images to eBay's picture hosting service."""

    def __init__(self):
        self.config = get_config()
        self.auth = get_auth()

    def upload_image(self, filepath: str) -> ImageUploadResult:
        """
        Upload a single image to eBay Picture Services.

        Args:
            filepath: Absolute path to the image file

        Returns:
            ImageUploadResult with the hosted URL or error
        """
        validation_error = _validate_image(filepath)
        if validation_error:
            return ImageUploadResult(filepath=filepath, success=False, error=validation_error)

        try:
            token = self.auth.get_valid_token()
        except ValueError as e:
            return ImageUploadResult(filepath=filepath, success=False, error=str(e))

        api_url = f"{self.config.api_base_url}/ws/api.dll"
        headers = {
            "X-EBAY-API-IAF-TOKEN": token,
            "X-EBAY-API-CALL-NAME": "UploadSiteHostedPictures",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": COMPATIBILITY_LEVEL,
        }

        xml_body = _build_upload_xml()
        path = Path(filepath)
        content_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"

        try:
            with open(filepath, "rb") as f:
                image_data = f.read()

            files = [
                ("XML Payload", ("request.xml", xml_body.encode("utf-8"), "text/xml")),
                ("image", (path.name, image_data, content_type)),
            ]

            with httpx.Client(timeout=60.0) as client:
                resp = client.post(api_url, headers=headers, files=files)

            if resp.status_code != 200:
                return ImageUploadResult(
                    filepath=filepath, success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}"
                )

            url, error = _parse_upload_response(resp.text)
            if error:
                return ImageUploadResult(filepath=filepath, success=False, error=error)

            return ImageUploadResult(filepath=filepath, success=True, url=url)

        except httpx.TimeoutException:
            return ImageUploadResult(filepath=filepath, success=False, error="Upload timed out")
        except Exception as e:
            return ImageUploadResult(filepath=filepath, success=False, error=str(e))

    def upload_images(
        self,
        filepaths: list[str],
        on_progress: Optional[Callable[[int, int, ImageUploadResult], None]] = None,
    ) -> BatchUploadResult:
        """
        Upload multiple images to eBay Picture Services.

        Args:
            filepaths: List of absolute paths to image files
            on_progress: Callback(current_index, total, result) called after each upload

        Returns:
            BatchUploadResult with all individual results
        """
        batch = BatchUploadResult()
        total = len(filepaths)

        for i, fp in enumerate(filepaths):
            result = self.upload_image(fp)
            batch.results.append(result)

            status = "ok" if result.success else f"FAILED: {result.error}"
            print(f"  Uploaded image {i + 1}/{total}: {Path(fp).name} — {status}")

            if on_progress:
                on_progress(i + 1, total, result)

        return batch


# Singleton
_images: Optional[EbayImages] = None


def get_images() -> EbayImages:
    """Get the global EbayImages instance."""
    global _images
    if _images is None:
        _images = EbayImages()
    return _images


def upload_image(filepath: str) -> ImageUploadResult:
    """Upload a single image to eBay. Convenience wrapper."""
    return get_images().upload_image(filepath)


def upload_images(
    filepaths: list[str],
    on_progress: Optional[Callable[[int, int, ImageUploadResult], None]] = None,
) -> BatchUploadResult:
    """Upload multiple images to eBay. Convenience wrapper."""
    return get_images().upload_images(filepaths, on_progress=on_progress)
