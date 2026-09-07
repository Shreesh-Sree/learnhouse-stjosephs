"""Open Badges 2.0 (IMS Global / 1EdTech) credentials for awarded certificates.

SCOPE DECISION (see PENDING_FEATURES.md for the full writeup): Open Badges
2.0 rather than a signed PDF. A PDF would need a rendering dependency this
project doesn't have (no reportlab/weasyprint/etc. in pyproject.toml), and
would only ever prove authenticity to whoever manually checks a signature.
An Open Badges assertion is a real, portable, independently-verifiable
credential a learner can hand to a recruiter, add to a Badgr backpack, or
feed to any OB2-aware verifier — and it needs nothing but JSON, which this
project already has plenty of tools for.

Uses OB2's "hosted" verification method: the assertion is valid precisely
because it lives at a stable, publicly dereferenceable URL that matches its
own "id" field — no signing keys to manage, no rotation story to write. A
revoked certificate (services.courses.certifications.revoke_user_certificate
DELETES the CertificateUser row) simply 404s here too, so there is no
separate "is this revoked" flag to keep in sync — non-existence already
means invalid, the same guarantee the existing certificate-verification
page already relies on.

Every document here is assembled from EXISTING rows (CertificateUser,
Certifications, Course, Organization) — no new table, the same "pure
transformation of durable data" shape as the at-risk dashboard and the
gamification stats.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config.config import get_learnhouse_config
from src.db.courses.certifications import CertificateUser, Certifications
from src.db.courses.courses import Course
from src.db.organizations import Organization
from src.db.users import User
from src.services.email.utils import get_media_base_url
from src.services.nudges.links import org_base_url


def _openbadges_secret() -> bytes:
    """Derive a stable, app-secret-based key for the recipient-hash salt —
    domain-separated from every other JWT-secret-derived credential in this
    codebase (webhook Fernet key, unsubscribe HMAC), same pattern as those."""
    secret = get_learnhouse_config().security_config.auth_jwt_secret_key
    return hashlib.sha256(f"learnhouse.openbadges.v1|{secret}".encode()).digest()


def _recipient_salt(user_certification_uuid: str) -> str:
    """A per-credential salt, stable across requests (so re-fetching the same
    assertion always returns byte-identical JSON) but not guessable without
    the app secret."""
    return hmac.new(
        _openbadges_secret(), user_certification_uuid.encode(), hashlib.sha256
    ).hexdigest()[:32]


def hash_recipient(email: str, user_certification_uuid: str) -> tuple[str, str]:
    """Returns ``(salt, "sha256$<hex>")`` — OB2's recommended privacy-preserving
    recipient identity, salted so the assertion's public JSON never exposes
    the learner's raw email address to anyone scraping badge URLs."""
    salt = _recipient_salt(user_certification_uuid)
    digest = hashlib.sha256(f"{email}{salt}".encode()).hexdigest()
    return salt, f"sha256${digest}"


def _course_image_url(media_base: str, org: Organization, course: Course) -> Optional[str]:
    if course.thumbnail_image:
        return f"{media_base}/content/orgs/{org.org_uuid}/courses/{course.course_uuid}/thumbnails/{course.thumbnail_image}"
    if org.logo_image:
        return f"{media_base}/content/orgs/{org.org_uuid}/logos/{org.logo_image}"
    return None


def issuer_url(api_base: str, org: Organization) -> str:
    return f"{api_base}/certifications/openbadges/issuer/{org.org_uuid}.json"


def badgeclass_url(api_base: str, certification: Certifications) -> str:
    return f"{api_base}/certifications/openbadges/badgeclass/{certification.certification_uuid}.json"


def assertion_url(api_base: str, cert_user: CertificateUser) -> str:
    return f"{api_base}/certifications/openbadges/assertion/{cert_user.user_certification_uuid}.json"


def build_issuer_profile(org: Organization, api_base: str, org_frontend_url: str) -> dict:
    profile = {
        "@context": "https://w3id.org/openbadges/v2",
        "type": "Issuer",
        "id": issuer_url(api_base, org),
        "name": org.name,
        "url": org_frontend_url,
    }
    if org.logo_image:
        profile["image"] = f"{api_base}/content/orgs/{org.org_uuid}/logos/{org.logo_image}"
    return profile


def build_badge_class(
    certification: Certifications, course: Course, org: Organization, api_base: str
) -> dict:
    badge = {
        "@context": "https://w3id.org/openbadges/v2",
        "type": "BadgeClass",
        "id": badgeclass_url(api_base, certification),
        "name": f"{course.name} — Certificate of Completion",
        "description": course.description or f"Awarded for completing {course.name}.",
        "criteria": {
            "narrative": f"Successfully completed every required activity and assignment in “{course.name}”.",
        },
        "issuer": issuer_url(api_base, org),
    }
    image = _course_image_url(api_base, org, course)
    if image:
        badge["image"] = image
    return badge


def build_assertion(
    cert_user: CertificateUser,
    certification: Certifications,
    course: Course,
    org: Organization,
    user: User,
    api_base: str,
) -> dict:
    salt, hashed_identity = hash_recipient(user.email, cert_user.user_certification_uuid)

    issued_on = cert_user.created_at
    try:
        # Normalize to a bare ISO date — this codebase's "created_at" strings
        # come from str(datetime.now()), not a strict ISO 8601 format OB2
        # validators expect.
        issued_on = datetime.fromisoformat(str(cert_user.created_at).strip()).date().isoformat()
    except (ValueError, TypeError):
        pass

    return {
        "@context": "https://w3id.org/openbadges/v2",
        "type": "Assertion",
        "id": assertion_url(api_base, cert_user),
        "recipient": {
            "type": "email",
            "hashed": True,
            "salt": salt,
            "identity": hashed_identity,
        },
        "badge": badgeclass_url(api_base, certification),
        "verification": {"type": "hosted"},
        "issuedOn": issued_on,
    }


# ---------------------------------------------------------------------------
# Public, unauthenticated lookups — an OB2 verifier (Badgr, a recruiter's
# browser, LinkedIn) has no LearnHouse session and must not need one.
# ---------------------------------------------------------------------------


async def get_issuer_profile(org_uuid: str, db_session: AsyncSession) -> dict:
    org = (await db_session.execute(
        select(Organization).where(Organization.org_uuid == org_uuid)
    )).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    api_base = get_media_base_url(None)
    frontend_url = await org_base_url(org.slug, db_session, org.id)
    return build_issuer_profile(org, api_base, frontend_url)


async def get_badge_class(certification_uuid: str, db_session: AsyncSession) -> dict:
    certification = (await db_session.execute(
        select(Certifications).where(Certifications.certification_uuid == certification_uuid)
    )).scalars().first()
    if not certification:
        raise HTTPException(status_code=404, detail="Certification not found")

    course = (await db_session.execute(
        select(Course).where(Course.id == certification.course_id)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    org = (await db_session.execute(
        select(Organization).where(Organization.id == course.org_id)
    )).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    api_base = get_media_base_url(None)
    return build_badge_class(certification, course, org, api_base)


async def get_assertion(user_certification_uuid: str, db_session: AsyncSession) -> dict:
    # A revoked certificate is a DELETED CertificateUser row (see
    # services.courses.certifications.revoke_user_certificate) — this lookup
    # 404s exactly the same way for "never existed" and "was revoked", which
    # is the correct outcome for a verifier: both mean "do not trust this".
    cert_user = (await db_session.execute(
        select(CertificateUser).where(CertificateUser.user_certification_uuid == user_certification_uuid)
    )).scalars().first()
    if not cert_user:
        raise HTTPException(status_code=404, detail="Certificate not found")

    certification = (await db_session.execute(
        select(Certifications).where(Certifications.id == cert_user.certification_id)
    )).scalars().first()
    if not certification:
        raise HTTPException(status_code=404, detail="Certification not found")

    course = (await db_session.execute(
        select(Course).where(Course.id == certification.course_id)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    org = (await db_session.execute(
        select(Organization).where(Organization.id == course.org_id)
    )).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    user = (await db_session.execute(
        select(User).where(User.id == cert_user.user_id)
    )).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Recipient not found")

    api_base = get_media_base_url(None)
    return build_assertion(cert_user, certification, course, org, user, api_base)
