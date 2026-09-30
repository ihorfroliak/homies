"""Structured notification templates (OAT-03). No free-form strings in
business logic: every notification references a template_id + locale, and the
payload carries typed variables. render() produces the final message."""

# template_id -> locale -> {subject, body}
TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "BookingCreated": {
        "en": {"subject": "Booking received",
               "body": "Your booking {correlation_id} for {check_in}–{check_out} is received."},
        "uk": {"subject": "Бронювання отримано",
               "body": "Ваше бронювання {correlation_id} на {check_in}–{check_out} отримано."},
    },
    "BookingConfirmed": {
        "en": {"subject": "Booking confirmed",
               "body": "Booking {correlation_id} is confirmed. Amount {amount} {currency}."},
    },
    "CheckInAvailable": {
        "en": {"subject": "Check-in instructions",
               "body": "Check-in for {correlation_id} opens {check_in}. Instructions to follow."},
    },
    "CheckInCompleted": {
        "en": {"subject": "Guest checked in",
               "body": "Guest checked in for booking {correlation_id}."},
    },
    "CancellationProcessed": {
        "en": {"subject": "Booking cancelled",
               "body": "Booking {correlation_id} cancelled. Refunded: {refunded}."},
    },
    "PayoutExecuted": {
        "en": {"subject": "Payout sent",
               "body": "Payout of {net} {currency} sent for booking {correlation_id}."},
    },
    "IncidentOpened": {
        "en": {"subject": "Incident opened",
               "body": "Incident ({kind}) opened on booking {correlation_id}: {note}"},
    },
    # TASK-014 saved-search alert (PRODUCT). Only the user's own search name,
    # a link to the public listing page and the two unsubscribe links: no
    # address, no price snapshot, no owner or contact detail.
    "SAVED_SEARCH_MATCH": {
        "en": {"subject": "A new listing matches your saved search",
               "body": ("A listing that matches your saved search \"{search_name}\" "
                        "has just been published on Homies:\n{listing_url}\n\n"
                        "Stop alerts for this search: {unsubscribe_search_url}\n"
                        "Stop all saved-search emails: {unsubscribe_all_url}\n")},
        "pl": {"subject": "Nowe ogłoszenie pasuje do Twojego zapisanego wyszukiwania",
               "body": ("Pojawiło się ogłoszenie pasujące do wyszukiwania \"{search_name}\":\n"
                        "{listing_url}\n\n"
                        "Wyłącz powiadomienia dla tego wyszukiwania: {unsubscribe_search_url}\n"
                        "Wyłącz wszystkie e-maile o wyszukiwaniach: {unsubscribe_all_url}\n")},
    },
}

DEFAULT_LOCALE = "en"


def template_id_for(event_type: str) -> str:
    return event_type  # 1:1 for the pilot


def render(template_id: str, locale: str, variables: dict) -> dict:
    """Return {subject, body}. Falls back to default locale, then to a generic
    message — never raises, so a missing template cannot break delivery."""
    by_locale = TEMPLATES.get(template_id, {})
    tpl = by_locale.get(locale) or by_locale.get(DEFAULT_LOCALE)
    if tpl is None:
        return {"subject": template_id, "body": f"{template_id}: {variables}"}
    safe = {"correlation_id": variables.get("correlation_id", "")}
    safe.update({k: v for k, v in variables.items()})
    try:
        return {"subject": tpl["subject"].format(**_Default(safe)),
                "body": tpl["body"].format(**_Default(safe))}
    except Exception:  # noqa: BLE001 — formatting must never break delivery
        return {"subject": tpl["subject"], "body": f"{template_id}: {variables}"}


class _Default(dict):
    def __missing__(self, key):  # tolerate missing variables in templates
        return "-"
