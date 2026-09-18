"""Cloudinary integration — the real media infrastructure layer.

Architecture (signed direct upload):

  React ──POST /api/upload-signature──> Backend
  Backend ──signed params (SHA-1)──> React
  React ──file + params──> Cloudinary Upload API        (api.cloudinary.com)
  Cloudinary ──asset JSON──> React
  React ──public_id──> POST /api/clips ──> Backend
  Backend ──Admin API──> verifies + fetches canonical asset data
  Backend ──stores metadata ──> PostgreSQL/SQLite
  Backend ──transformation URLs (thumbnails/previews) ──> React

The API secret NEVER leaves this service. URL building for delivery does not
require the secret (unsigned delivery URLs); uploads and destructive admin
operations stay server-side.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import cloudinary
import cloudinary.api
import cloudinary.uploader
import cloudinary.utils

from ..config import Settings


class CloudinaryNotConfigured(Exception):
    """Raised when credentials are missing — the API turns this into a clear,
    human-readable 503 so the user knows exactly what to do."""


class CloudinaryOperationError(Exception):
    """Raised when Cloudinary rejects a call (auth failure, missing asset...)."""


def _configure(settings: Settings) -> None:
    if not settings.cloudinary_configured:
        raise CloudinaryNotConfigured(
            "Cloudinary is not configured on the server yet. Add "
            "CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET to backend/.env."
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


@dataclass
class SignedUploadParams:
    upload_url: str
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    public_id: str
    signature: str
    tags: str
    context: str


def build_signed_upload(settings: Settings, original_filename: str) -> SignedUploadParams:
    """Produce the one-time signed parameters for a browser->Cloudinary upload.

    Signature = SHA-1 of the alphabetically-sorted params + api_secret, exactly
    as Cloudinary documents. The secret itself is never returned.
    """
    _configure(settings)
    timestamp = int(time.time())
    folder = settings.cloudinary_folder
    public_id = f"{folder}/{uuid.uuid4().hex}"
    tags = "lifeclip,app-upload"
    # Non-sensitive provenance metadata stored alongside the asset.
    safe_name = (original_filename or "capture")[:80].replace("=", "").replace("&", "")
    context = f"caption=LifeClip upload|original={safe_name}"
    to_sign = {
        "context": context,
        "folder": folder,
        "public_id": public_id,
        "tags": tags,
        "timestamp": timestamp,
    }
    signature = cloudinary.utils.api_sign_request(
        to_sign, settings.cloudinary_api_secret
    )
    return SignedUploadParams(
        upload_url=(
            f"https://api.cloudinary.com/v1_1/"
            f"{settings.cloudinary_cloud_name}/image/upload"
        ),
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        timestamp=timestamp,
        folder=folder,
        public_id=public_id,
        signature=signature,
        tags=tags,
        context=context,
    )


def verify_and_fetch_asset(settings: Settings, public_id: str) -> dict:
    """Fetch canonical asset data via the authenticated Admin API.

    This proves the asset really exists in our Cloudinary cloud and prevents
    the client from claiming arbitrary URLs.
    """
    _configure(settings)
    try:
        res = cloudinary.api.resource(public_id, resource_type="image")
    except cloudinary.exceptions.NotFound as exc:  # type: ignore[attr-defined]
        raise CloudinaryOperationError(
            "We could not find that upload in Cloudinary. Please try uploading again."
        ) from exc
    except Exception as exc:  # auth failures, network issues, ...
        raise CloudinaryOperationError(
            "Cloudinary could not verify the upload. If credentials were just "
            "added, restart the backend and try again."
        ) from exc
    return {
        "public_id": res["public_id"],
        "secure_url": res["secure_url"],
        "format": res.get("format", ""),
        "width": int(res.get("width", 0)),
        "height": int(res.get("height", 0)),
        "bytes": int(res.get("bytes", 0)),
        "resource_type": res.get("resource_type", "image"),
    }


def delete_asset(settings: Settings, public_id: str) -> bool:
    """Permanently delete the asset from Cloudinary. Returns True on success.
    Failures are reported honestly — the database row is removed regardless so
    the clip disappears from LifeClip views, and the caller surfaces a warning.
    """
    try:
        _configure(settings)
    except CloudinaryNotConfigured:
        return False
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="image")
        return result.get("result") == "ok"
    except Exception:
        return False


def _delivery_url(settings: Settings, public_id: str, transformation: str) -> str:
    """Build an optimized delivery URL (no credentials needed — unsigned).

    f_auto + q_auto lets Cloudinary pick the best format/quality per device.
    """
    cloud = settings.cloudinary_cloud_name or "res.cloudinary.com"
    return (
        f"https://res.cloudinary.com/{cloud}/image/upload/"
        f"{transformation}/{public_id}"
    )


def thumbnail_url(settings: Settings, public_id: str) -> str:
    return _delivery_url(settings, public_id, "c_fill,g_auto,w_320,h_320,q_auto,f_auto")


def preview_url(settings: Settings, public_id: str) -> str:
    return _delivery_url(settings, public_id, "c_limit,w_1200,q_auto,f_auto")


def analysis_url(settings: Settings, public_id: str, fmt: str) -> str:
    """URL the analyzer downloads. Converted to PNG with a size cap so OCR gets
    a predictable, reasonably-sized image regardless of the original format."""
    return _delivery_url(settings, public_id, "c_limit,w_2000,h_2000,q_auto,f_png")
