"""Signed-upload endpoint: produces one-time signed parameters so the browser
can upload the user's chosen file directly to Cloudinary. The API secret stays
here on the server; only the signature, timestamp and public params leave."""

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_settings
from ..deps import get_session
from ..models import Session
from ..schemas import UploadSignatureIn, UploadSignatureOut
from ..services.cloudinary_service import (
    CloudinaryNotConfigured,
    build_signed_upload,
)

router = APIRouter(tags=["uploads"])


@router.post("/api/upload-signature", response_model=UploadSignatureOut)
def upload_signature(payload: UploadSignatureIn, _: Session = Depends(get_session)):
    settings = get_settings()

    # Validate BEFORE anything is sent to Cloudinary.
    if payload.mime_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=415,
            detail={
                "code": "unsupported_type",
                "message": (
                    "LifeClip works with photos: JPEG, PNG or WebP. "
                    "That file type isn't supported yet."
                ),
            },
        )
    if payload.byte_size > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail={
                "code": "file_too_large",
                "message": f"That file is too large. Please choose an image under {mb} MB.",
            },
        )

    try:
        params = build_signed_upload(settings, payload.filename)
    except CloudinaryNotConfigured as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "cloudinary_not_configured", "message": str(exc)},
        )

    return UploadSignatureOut(
        upload_url=params.upload_url,
        cloud_name=params.cloud_name,
        api_key=params.api_key,
        timestamp=params.timestamp,
        folder=params.folder,
        public_id=params.public_id,
        signature=params.signature,
        tags=params.tags,
        context=params.context,
        max_upload_bytes=settings.max_upload_bytes,
    )
