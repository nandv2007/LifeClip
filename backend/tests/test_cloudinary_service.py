"""Cloudinary signed-upload contract, verified WITHOUT real credentials:

* signature = SHA-1 of the sorted params string + api_secret (as Cloudinary documents)
* the API secret is never present in anything returned to the browser
* delivery URLs point at the correct cloud and carry optimization params
"""

import hashlib

from app.config import get_settings
from app.services import cloudinary_service
from app.services.cloudinary_service import build_signed_upload


def _settings_with_creds(monkeypatch):
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "tecwmb40")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "123456789012345")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test-secret-do-not-use")
    get_settings.cache_clear()
    s = get_settings()
    yield s
    get_settings.cache_clear()


def test_signature_matches_cloudinary_algorithm(monkeypatch):
    gen = _settings_with_creds(monkeypatch)
    settings = next(gen)
    params = build_signed_upload(settings, "poster.jpg")

    # Recompute the expected signature by hand per Cloudinary docs.
    to_sign = (
        f"context={params.context}&folder={params.folder}&public_id={params.public_id}"
        f"&tags={params.tags}&timestamp={params.timestamp}"
    )
    expected = hashlib.sha1((to_sign + "test-secret-do-not-use").encode()).hexdigest()
    assert params.signature == expected

    # Upload URL targets the configured cloud's real upload endpoint.
    assert params.upload_url == f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload"
    # The folder is sent exactly once. Cloudinary returns the final asset as
    # lifeclip/<uuid>; prefixing public_id too would create lifeclip/lifeclip/.
    assert params.folder == "lifeclip"
    assert "/" not in params.public_id


def test_secret_never_leaks_in_sign_params(monkeypatch):
    settings = next(_settings_with_creds(monkeypatch))
    params = build_signed_upload(settings, "x.jpg")
    returned_values = " ".join(
        str(v)
        for v in (
            params.upload_url, params.cloud_name, params.api_key, params.timestamp,
            params.folder, params.public_id, params.tags, params.context,
        )
    )
    assert "test-secret-do-not-use" not in returned_values


def test_delivery_urls_are_optimized(monkeypatch):
    settings = next(_settings_with_creds(monkeypatch))
    thumb = cloudinary_service.thumbnail_url(settings, "lifeclip/abc")
    assert thumb.startswith("https://res.cloudinary.com/tecwmb40/image/upload/")
    assert "f_auto" in thumb and "q_auto" in thumb
    prev = cloudinary_service.preview_url(settings, "lifeclip/abc")
    assert "c_limit" in prev
