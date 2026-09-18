#!/usr/bin/env python3
"""One-command, REAL Cloudinary verification for LifeClip.

Run AFTER filling backend/.env with your CLOUDINARY_API_KEY / SECRET:

    cd backend
    python scripts/verify_cloudinary.py

It will:
  1. Build signed upload parameters (exactly like the production flow)
  2. Upload a real sample image to  cloud: tecwmb40  folder: lifeclip/
  3. Fetch it back via the authenticated Admin API
  4. Print an optimized delivery URL + a thumbnail URL
  5. Delete the test asset (cleanup)

No mocks: every step talks to api.cloudinary.com / res.cloudinary.com.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.config import get_settings  # noqa: E402
from app.services import cloudinary_service  # noqa: E402


def main() -> int:
    settings = get_settings()
    print("LifeClip — Cloudinary verification")
    print("=" * 46)
    print(f"Cloud name : {settings.cloudinary_cloud_name or '(missing!)'}")
    print(f"API key    : {settings.cloudinary_api_key[:4] + '…' if settings.cloudinary_api_key else '(missing!)'}")
    print(f"API secret : {'set (hidden)' if settings.cloudinary_api_secret else '(missing!)'}")
    print(f"Folder     : {settings.cloudinary_folder}")
    if not settings.cloudinary_configured:
        print("\n❌ Credentials missing. Fill CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET")
        print("   in backend/.env (find them via 'Go to API Keys' in your Cloudinary console).")
        return 1

    # 1) Signed params
    sig = cloudinary_service.build_signed_upload(settings, "verify_sample.jpg")
    print("\n1) Signed upload parameters built")
    print(f"   public_id : {sig.public_id}")
    print(f"   signature : {sig.signature[:12]}…  (api_secret never returned)")

    # 2) Real upload of a real sample image
    import requests

    sample = HERE.parent.parent / "samples" / "sample_event_poster.jpg"
    if not sample.exists():
        print(f"\n❌ Sample image not found at {sample}. Run scripts/generate_samples.py first.")
        return 1
    with open(sample, "rb") as fp:
        resp = requests.post(
            sig.upload_url,
            data={
                "api_key": sig.api_key,
                "timestamp": sig.timestamp,
                "signature": sig.signature,
                "folder": sig.folder,
                "public_id": sig.public_id,
                "tags": sig.tags,
                "context": sig.context,
            },
            files={"file": ("verify_sample.jpg", fp, "image/jpeg")},
            timeout=60,
        )
    if resp.status_code != 200:
        print(f"\n❌ Upload rejected ({resp.status_code}): {resp.text[:300]}")
        print("   Most likely the API key/secret pair is wrong — regenerate in the console.")
        return 1
    asset = resp.json()
    print("\n2) ✅ Upload accepted by Cloudinary")
    print(f"   secure_url: {asset['secure_url'][:80]}…")
    print(f"   {asset.get('width')}x{asset.get('height')}  {asset.get('bytes', 0)//1024} KB  {asset.get('format')}")

    # 3) Admin API verification (what POST /api/clips does)
    info = cloudinary_service.verify_and_fetch_asset(settings, asset["public_id"])
    print("\n3) ✅ Verified via authenticated Admin API")
    print(f"   exists in cloud: {info['public_id']}")

    # 4) Delivery URLs (thumbnails/previews the app uses)
    print("\n4) Optimized delivery URLs (open in a browser):")
    print(f"   thumbnail: {cloudinary_service.thumbnail_url(settings, asset['public_id'])}")
    print(f"   preview  : {cloudinary_service.preview_url(settings, asset['public_id'])}")

    # 5) Cleanup
    deleted = cloudinary_service.delete_asset(settings, asset["public_id"])
    print(f"\n5) Cleanup: test asset deleted -> {'✅ yes' if deleted else '⚠️ no (check credentials)'}")
    print("\nAll good — the LifeClip app will now upload, store, transform and analyze for real.")
    return 0 if deleted else 2


if __name__ == "__main__":
    raise SystemExit(main())
