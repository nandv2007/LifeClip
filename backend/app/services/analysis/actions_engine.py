"""Action engine — decides what a user can realistically do next, per category.

Rules:
  * Suggest only actions supported by what was actually extracted.
  * 2–5 primary actions; the rest go under "More".
  * Each action carries a human reason ("We found an event date and venue.")
  * Consequential actions (calendar/reminder/share) are confirmed + editable in
    the UI before anything happens — nothing runs silently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ActionSpec:
    action_type: str
    label: str
    reason: str
    primary: bool


def _has(fields: dict[str, str], *names: str) -> bool:
    return any(fields.get(n) for n in names)


def suggest_actions(category: str, fields: dict[str, str]) -> list[ActionSpec]:
    """Return ordered actions: primaries first, then secondary ('More')."""
    actions: list[ActionSpec] = []

    def add(t: str, label: str, reason: str, primary: bool = False):
        actions.append(ActionSpec(t, label, reason, primary))

    if category == "event":
        if _has(fields, "date"):
            add("calendar", "Add to Calendar",
                "We found an event date" + (" and venue" if _has(fields, "location") else "") + ".",
                True)
            add("reminder", "Set a Reminder", "Get notified before this starts.", True)
        if _has(fields, "location"):
            add("directions", "Find Location", "Open the venue in your maps app.", True)
        if _has(fields, "url"):
            add("open_link", "Open Event Link", "This poster includes a link.", False)
        add("share", "Share", "Send the details to someone.", False)
        add("copy_text", "Copy Text", "Copy everything we read.", False)

    elif category == "receipt":
        add("save", "Save Purchase", "Keep this receipt in your LifeClips.", True)
        if _has(fields, "total"):
            add("expense", "Save as Expense", "We found a total — log it for your records.", True)
        if _has(fields, "warranty"):
            add("warranty", "Warranty Reminder", "Warranty terms were mentioned on this receipt.", True)
        elif _has(fields, "returns"):
            add("reminder", "Return Reminder", "Return terms were mentioned on this receipt.", True)
        add("copy_text", "Copy Text", "Copy everything we read.", False)
        add("share", "Share", "Send the receipt details.", False)

    elif category == "ticket":
        if _has(fields, "date"):
            add("calendar", "Add to Calendar",
                "We found a date" + (" and time" if _has(fields, "time") else "") + " on this ticket.", True)
            add("reminder", "Set a Reminder", "Get notified before you need this ticket.", True)
        add("save", "Save Ticket", "Keep this ticket handy in your LifeClips.", True)
        add("open_original", "View Original", "Open the full-resolution ticket.", False)
        add("share", "Share", "Send the ticket details.", False)

    elif category == "notes":
        add("summarize", "Summarize", "Turn these notes into key points.", True)
        add("quiz", "Quiz Me", "Practice with fill-in-the-blank questions from these notes.", True)
        add("flashcards", "Create Flashcards", "Make term/definition cards from these notes.", True)
        add("explain", "Explain Simply", "See the main ideas in plain words.", False)
        add("copy_text", "Copy Text", "Copy everything we read.", False)
        add("translate", "Translate", "Open this text in Google Translate.", False)

    elif category == "menu":
        add("translate", "Translate Menu", "Open the menu text in Google Translate.", True)
        if _has(fields, "dishes"):
            add("save", "Save Menu", "Keep this menu in your LifeClips.", True)
        add("copy_text", "Copy Text", "Copy everything we read.", False)
        add("share", "Share", "Send this menu to someone.", False)

    elif category == "product":
        add("save", "Save Product", "Keep the product details in your LifeClips.", True)
        q = fields.get("model") or fields.get("product") or ""
        add("search", "Find Manual / Search",
            f"Search the web for '{q[:40]}'." if q else "Search the web for this product.", True)
        if _has(fields, "warranty"):
            add("warranty", "Warranty Reminder", f"We found warranty info: '{fields['warranty'][:60]}'.", True)
        add("copy_text", "Copy Text", "Copy everything we read.", False)

    elif category == "document":
        add("summarize", "Summarize", "Get the key points of this document.", True)
        if _has(fields, "deadline", "date"):
            add("reminder", "Set a Reminder", "We found a date/deadline in this document.", True)
        add("save", "Save Document", "Keep this document in your LifeClips.", False)
        add("share", "Share", "Send the document details.", False)
        add("copy_text", "Copy Text", "Copy everything we read.", False)

    else:  # other / unknown — never an empty result
        if _has(fields, "length"):
            add("copy_text", "Copy Text", "Copy everything we read from this image.", True)
            add("summarize", "Summarize", "Get the key points.", True)
            add("translate", "Translate", "Open this text in Google Translate.", True)
        add("save", "Save to LifeClips", "Keep this image and its analysis.", True)
        add("open_original", "View Original", "Open the full-resolution image.", False)

    # Guarantee 2–5 primaries: promote from secondary if needed.
    primaries = [a for a in actions if a.primary]
    if len(primaries) < 2:
        for a in actions:
            if not a.primary and len([x for x in actions if x.primary]) < 3:
                a.primary = True
    if not actions:
        actions.append(ActionSpec("save", "Save to LifeClips", "Keep this image for later.", True))
        actions.append(ActionSpec("open_original", "View Original", "Open the full-resolution image.", False))
    return actions
