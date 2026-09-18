"""Action confirmation — the user reviews/edits extracted values, THEN
confirms. Nothing external happens without this explicit step."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session as OrmSession

from ..db import get_db
from ..deps import get_session
from ..models import Action, Clip, Session, utcnow
from ..schemas import ActionConfirmIn, ActionConfirmOut
from ..services.datetime_parse import parse_date, parse_time
from ..services.ics import build_event_ics, safe_filename

router = APIRouter(tags=["actions"])


def _get_action(db: OrmSession, session: Session, action_id: str) -> tuple[Action, Clip]:
    action = db.get(Action, action_id)
    if not action:
        raise HTTPException(404, detail={"code": "not_found", "message": "We couldn't find that action."})
    clip = db.get(Clip, action.clip_id)
    if not clip or clip.session_id != session.id:
        raise HTTPException(404, detail={"code": "not_found", "message": "We couldn't find that action."})
    return action, clip


@router.post("/api/actions/{action_id}/confirm", response_model=ActionConfirmOut)
def confirm_action(action_id: str, payload: ActionConfirmIn,
                   session: Session = Depends(get_session),
                   db: OrmSession = Depends(get_db)):
    action, clip = _get_action(db, session, action_id)
    p = payload.payload or {}

    out = ActionConfirmOut(id=action.id, status="confirmed")

    if action.action_type in ("calendar", "reminder", "warranty"):
        # Re-validate the edited event before accepting it.
        title = str(p.get("title") or clip.title or "LifeClip event").strip()[:200]
        date_val = parse_date(str(p.get("date", "")))
        if date_val is None:
            raise HTTPException(
                422,
                detail={"code": "date_required",
                        "message": "Please add a date so we can put this on your calendar."},
            )
        time_val = parse_time(str(p.get("time", ""))) if p.get("time") else None
        location = str(p.get("location", "")).strip()[:300]
        reminder_minutes = p.get("reminder_minutes")
        try:
            reminder_minutes = int(reminder_minutes) if reminder_minutes is not None else None
        except (TypeError, ValueError):
            reminder_minutes = None
        if action.action_type == "reminder" and reminder_minutes is None:
            reminder_minutes = 60

        merged = {
            "title": title,
            "date": date_val.isoformat(),
            "time": time_val.strftime("%H:%M") if time_val else "",
            "location": location,
            "reminder_minutes": reminder_minutes,
            "all_day": time_val is None,
        }
        action.payload = json.dumps(merged)
        action.status = "confirmed"
        action.confirmed_at = utcnow()
        db.commit()
        out.download_url = f"/api/actions/{action.id}/ics"
        return out

    if action.action_type == "directions":
        query = str(p.get("location") or p.get("query") or "").strip()[:200]
        if not query:
            raise HTTPException(422, detail={"code": "location_required",
                                             "message": "Add a location so we can look it up."})
        action.payload = json.dumps({"query": query})
        action.status, action.confirmed_at = "confirmed", utcnow()
        db.commit()
        out.external_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
        return out

    if action.action_type == "search":
        query = str(p.get("query") or clip.title or "").strip()[:200]
        if not query:
            raise HTTPException(422, detail={"code": "query_required",
                                             "message": "Add what you'd like to search for."})
        action.status, action.confirmed_at = "confirmed", utcnow()
        db.commit()
        out.external_url = f"https://www.google.com/search?q={quote_plus(query)}"
        return out

    if action.action_type == "open_link":
        url = str(p.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        # Never allow dangerous schemes to reach window.open on the client.
        lowered = url.lower()
        if not lowered.startswith(("https://", "http://")) or any(
            bad in lowered for bad in ("javascript:", "data:", "vbscript:")
        ):
            raise HTTPException(
                400,
                detail={"code": "unsafe_url",
                        "message": "That link doesn't look safe to open."},
            )
        action.status, action.confirmed_at = "confirmed", utcnow()
        db.commit()
        out.external_url = url
        return out

    if action.action_type == "translate":
        text = str(p.get("text") or (clip.raw_text or ""))[:4000]
        action.status, action.confirmed_at = "confirmed", utcnow()
        db.commit()
        out.external_url = (
            "https://translate.google.com/?sl=auto&tl=en&text=" + quote_plus(text)
        )
        return out

    if action.action_type == "copy_text":
        action.status, action.confirmed_at = "done", utcnow()
        db.commit()
        out.content = clip.raw_text or ""
        out.status = "done"
        return out

    if action.action_type == "share":
        action.status, action.confirmed_at = "confirmed", utcnow()
        db.commit()
        bits = [clip.title or "LifeClip item"]
        for f in clip.fields[:6]:
            if f.value:
                bits.append(f"{f.label or f.name}: {f.value}")
        out.content = "\n".join(bits)
        return out

    if action.action_type in ("save", "expense"):
        # Persisted as durable metadata; exportable later.
        meta = dict(p)
        if action.action_type == "expense":
            meta.setdefault("total", next((f.value for f in clip.fields if f.name == "total"), ""))
            meta.setdefault("currency", next((f.value for f in clip.fields if f.name == "currency"), ""))
            meta.setdefault("merchant", clip.title or "")
        action.payload = json.dumps(meta)
        action.status, action.confirmed_at = "done", utcnow()
        db.commit()
        out.status = "done"
        return out

    if action.action_type == "open_original":
        action.status, action.confirmed_at = "confirmed", utcnow()
        db.commit()
        out.external_url = clip.secure_url
        return out

    # Unknown action types: record confirmation honestly.
    action.status, action.confirmed_at = "confirmed", utcnow()
    db.commit()
    return out


@router.get("/api/actions/{action_id}/ics")
def download_ics(action_id: str,
                 session: Session = Depends(get_session),
                 db: OrmSession = Depends(get_db)):
    action, _ = _get_action(db, session, action_id)
    if action.action_type not in ("calendar", "reminder", "warranty"):
        raise HTTPException(400, detail={"code": "not_calendar",
                                         "message": "That action doesn't create a calendar file."})
    try:
        p = json.loads(action.payload or "{}")
    except json.JSONDecodeError:
        p = {}
    date_val = parse_date(str(p.get("date", "")))
    if date_val is None:
        raise HTTPException(422, detail={"code": "date_required",
                                         "message": "This action needs a date first."})
    time_val = parse_time(str(p.get("time", ""))) if p.get("time") else None
    if time_val:
        start = datetime.combine(date_val, time_val, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
    else:
        start = datetime.combine(date_val, datetime.min.time(), tzinfo=timezone.utc)
        end = start  # zero-duration 'appointment-style' all-day-ish entry
    ics = build_event_ics(
        title=str(p.get("title") or "LifeClip event"),
        start=start,
        end=end,
        location=str(p.get("location") or ""),
        description="Created with LifeClip — every photo should be actionable.",
        reminder_minutes=p.get("reminder_minutes"),
    )
    filename = safe_filename(str(p.get("title") or "lifeclip-event"))
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
