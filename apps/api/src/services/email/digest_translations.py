"""Copy for the weekly student digest email.

English only for now — merged into EMAIL_TRANSLATIONS the same way
nudge_translations is (see that package's __init__.py), so ``t()``'s
existing "fall back to English" behavior means every other locale already
degrades gracefully rather than showing a raw key. A real, disclosed scope
limit: adding the other ~20 languages this app ships would mean translating
the copy well, not machine-translating placeholder strings into a school's
outgoing mail.
"""

DIGEST_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "digest.subject": "Your week at {org_name}",
        "digest.heading": "Here's what's coming up",
        "digest.intro": "A quick look at {org_name} for the week ahead.",
        "digest.due_this_week.title": "Due this week",
        "digest.due_this_week.item": "{title} — {course_name}, due {due_date}",
        "digest.not_started.title": "You haven't started yet",
        "digest.not_started.item": "{title} — {course_name}",
        "digest.cta": "Open {org_name}",
        "digest.footer": "You're getting this because you're enrolled at {org_name}.",
        "digest.unsubscribe": "Unsubscribe from this weekly email",
    }
}
