"""SCORM 1.2 package upload, manifest parsing, and content serving.

Independent, from-scratch OSS implementation — not a port of anything, and
not the ee/services/scorm/scorm.py module this project's own test suite
treats as a withheld Enterprise deliverable (see that module's tests, which
explicitly `pytest.importorskip`/`skip("EE not present (OSS build)")` around
its absence). The manifest edge cases handled below (xml:base prepending,
nested item trees, backslash/relative-path normalization, mastery score) are
properties of the public SCORM 1.2 / IMS Content Packaging specification
itself, not anyone's proprietary logic.

Scope is deliberately SCORM 1.2 only. A manifest that looks like SCORM 2004
(detected via the IMS CP namespace URI on the manifest root, or the
2004-only adlseq/imsss namespaces) is rejected with a clear error rather
than mis-played as 1.2.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import defusedxml.ElementTree as ET
from defusedxml.ElementTree import ParseError
from fastapi import HTTPException, Request, Response, UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import Activity
from src.db.courses.courses import Course
from src.db.courses.scorm import (
    SCORM_COMPLETING_STATUSES,
    ScormLessonStatus,
    ScormResultRow,
    ScormTrackingData,
    ScormTrackingDataRead,
    ScormTrackingDataUpdate,
    ScormVersionEnum,
)
from src.db.organizations import Organization
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.security.rbac import AccessAction, check_resource_access
from src.services.courses.transfer.storage_utils import delete_storage_directory
from src.services.trail.trail import add_activity_to_trail
from src.services.utils.upload_content import read_content_nested, upload_content

logger = logging.getLogger(__name__)

# --- Package limits -----------------------------------------------------
# Smaller than the full-course-export caps in transfer/import_service.py — a
# single SCORM package is one activity's worth of content, not a whole
# course archive.
MAX_SCORM_PACKAGE_SIZE = 200 * 1024 * 1024
MAX_SCORM_FILE_SIZE = 100 * 1024 * 1024
MAX_SCORM_ENTRY_COUNT = 10000
MAX_SCORM_COMPRESSION_RATIO = 20
_ZIP_SYMLINK_MODE = 0xA000 << 16

# IMS Content Packaging namespace URIs. The manifest root's own namespace
# reliably distinguishes SCORM 1.2 packages from SCORM 2004 ones regardless
# of authoring tool, since it's the schema the package claims to conform to.
_IMSCP_1P1P2_NS = "imscp_rootv1p1p2"  # SCORM 1.2
_IMSCP_2004_NS_MARKERS = ("imscp_v1p1", "adlseq_", "imsss_")


def validate_scorm_zip(content: bytes) -> bool:
    """Magic-byte check that ``content`` is a ZIP file."""
    return content[:4] == b"PK\x03\x04" or content[:4] == b"PK\x05\x06"


def sanitize_path(path: str) -> str:
    """Normalize a manifest- or request-supplied relative path.

    Backslashes become forward slashes, leading slashes are stripped, and
    ``.``/``..`` segments are dropped entirely (not merely resolved) so the
    result can never climb above wherever it's joined against.
    """
    if not path:
        return ""
    normalized = path.replace("\\", "/").lstrip("/")
    parts = [p for p in normalized.split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def _local_tag(elem) -> str:
    """Element tag name with any XML namespace prefix stripped."""
    tag = elem.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _iter_local(elem, tagname: str):
    """All descendants of ``elem`` (elem included) whose local tag matches."""
    for node in elem.iter():
        if _local_tag(node) == tagname:
            yield node


def _find_local(elem, tagname: str):
    for node in _iter_local(elem, tagname):
        return node
    return None


def _attr_local(elem, name: str) -> Optional[str]:
    """Attribute value by local name, regardless of the namespace prefix
    used for it (adlcp:scormtype vs adlcp:scormType vs an unprefixed
    scormtype all resolve the same way)."""
    for key, value in elem.attrib.items():
        local = key.split("}", 1)[1] if "}" in key else key
        if local.lower() == name.lower():
            return value
    return None


def detect_scorm_version(root) -> ScormVersionEnum:
    """SCORM_2004 if the manifest's own namespace or a 2004-only sequencing
    namespace is present anywhere in the tree; SCORM_12 otherwise (including
    when the schema can't be determined — 1.2 is the more permissive,
    far more common real-world case)."""
    root_ns = root.tag.split("}", 1)[0].lstrip("{") if "}" in root.tag else ""
    if any(marker in root_ns for marker in _IMSCP_2004_NS_MARKERS):
        return ScormVersionEnum.SCORM_2004
    # A 2004 package sometimes keeps a 1.2-shaped root namespace but pulls in
    # the simple-sequencing/navigation namespaces on the manifest element
    # itself — those are 2004-exclusive regardless of the root NS.
    for key in getattr(root, "attrib", {}):
        if "}" in key:
            ns = key.split("}", 1)[0].lstrip("{")
            if any(marker in ns for marker in _IMSCP_2004_NS_MARKERS):
                return ScormVersionEnum.SCORM_2004
    return ScormVersionEnum.SCORM_12


@dataclass
class ScormSco:
    launch_path: str
    title: str
    mastery_score: Optional[str] = None


def _resource_href(resource) -> Optional[str]:
    """The resource's own href, or its first <file href="..."> child's, with
    any xml:base on the <resources> parent and the <resource> itself
    prepended in the correct order (outer base, then inner base, then href)
    — IMS CP resolves relative URLs exactly like nested HTML <base> tags."""
    href = _attr_local(resource, "href")
    if not href:
        file_elem = _find_local(resource, "file")
        if file_elem is not None:
            href = _attr_local(file_elem, "href")
    if not href:
        return None

    xml_base_attr = "{http://www.w3.org/XML/1998/namespace}base"
    base = resource.get(xml_base_attr, "")
    return f"{base}{href}" if base else href


def extract_scos_from_manifest(root, version: ScormVersionEnum) -> list[ScormSco]:
    """Walk the default <organization>'s <item> tree and return one ScormSco
    per LEAF item that resolves to a launchable resource, in document order.

    A wrapping "chapter" item (no identifierref, only child items) is
    skipped — only leaves are launchable SCOs. Nesting depth is not
    otherwise meaningful here since this player launches one SCO at a time
    rather than implementing SCORM 2004 sequencing.
    """
    resources_elem = _find_local(root, "resources")
    resources_xml_base = ""
    resources_by_id: dict[str, object] = {}
    if resources_elem is not None:
        xml_base_attr = "{http://www.w3.org/XML/1998/namespace}base"
        resources_xml_base = resources_elem.get(xml_base_attr, "")
        for resource in _iter_local(resources_elem, "resource"):
            rid = resource.get("identifier")
            if rid:
                resources_by_id[rid] = resource

    organizations_elem = _find_local(root, "organizations")
    if organizations_elem is None:
        return []

    default_id = organizations_elem.get("default")
    organization = None
    if default_id:
        for org in _iter_local(organizations_elem, "organization"):
            if org.get("identifier") == default_id:
                organization = org
                break
    if organization is None:
        organization = _find_local(organizations_elem, "organization")
    if organization is None:
        return []

    scos: list[ScormSco] = []

    def walk(item) -> None:
        child_items = [c for c in item if _local_tag(c) == "item"]
        ref = item.get("identifierref")
        if not child_items and ref and ref in resources_by_id:
            resource = resources_by_id[ref]
            href = _resource_href(resource)
            if href:
                full_path = f"{resources_xml_base}{href}"
                title_elem = _find_local(item, "title")
                # <adlcp:masteryscore> is a CHILD ELEMENT of <item> per the
                # SCORM 1.2 spec, not an attribute — easy to get wrong since
                # most other adlcp-namespaced values (scormtype) ARE
                # attributes.
                mastery_elem = _find_local(item, "masteryscore")
                mastery = (mastery_elem.text or "").strip() if mastery_elem is not None else None
                scos.append(
                    ScormSco(
                        launch_path=sanitize_path(full_path),
                        title=(title_elem.text or "").strip() if title_elem is not None else "",
                        mastery_score=mastery,
                    )
                )
        for child in child_items:
            walk(child)

    # Only walk the organization's direct <item> children — iterating the
    # whole subtree here (rather than via walk's own recursion) keeps a
    # top-level item that duplicates as a resources/<item> descendant from
    # being visited twice.
    for top_item in organization:
        if _local_tag(top_item) == "item":
            walk(top_item)

    return scos


def get_package_title(root) -> str:
    organizations_elem = _find_local(root, "organizations")
    if organizations_elem is not None:
        organization = _find_local(organizations_elem, "organization")
        if organization is not None:
            title_elem = _find_local(organization, "title")
            if title_elem is not None and title_elem.text:
                return title_elem.text.strip()
    return ""


def _safe_extract_zip(zip_path: str, extract_dir: str) -> None:
    """Extract ``zip_path`` into ``extract_dir`` with the same defenses as
    the course-import pipeline: reject symlink entries outright, cap
    per-file and aggregate uncompressed size, cap entry count, guard against
    a suspicious compression ratio (zip bomb), and re-verify every target
    path stays contained after resolving symlinks — a fresh extract_dir
    shouldn't have any, but a contained-but-crafted entry earlier in the
    archive must not be able to redirect a later write via one.
    """
    abs_extract = os.path.realpath(extract_dir)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        infolist = zip_ref.infolist()

        if len(infolist) > MAX_SCORM_ENTRY_COUNT:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid SCORM package: too many entries (max {MAX_SCORM_ENTRY_COUNT})",
            )

        compressed_size = os.path.getsize(zip_path)
        uncompressed_size = sum(info.file_size for info in infolist)
        if uncompressed_size > MAX_SCORM_PACKAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Invalid SCORM package: uncompressed size exceeds limit",
            )
        if compressed_size > 0 and uncompressed_size > compressed_size * MAX_SCORM_COMPRESSION_RATIO:
            raise HTTPException(
                status_code=400,
                detail="Invalid SCORM package: suspicious compression ratio",
            )

        for info in infolist:
            if info.external_attr & _ZIP_SYMLINK_MODE:
                continue  # symlink entry: skip rather than follow or write as one

            if info.file_size > MAX_SCORM_FILE_SIZE:
                continue  # oversized single entry: skip it, keep the rest of the package

            safe_path = sanitize_path(info.filename)
            if not safe_path:
                continue

            target_path = os.path.join(extract_dir, safe_path)
            resolved = os.path.realpath(target_path)
            try:
                contained = os.path.commonpath([abs_extract, resolved]) == abs_extract
            except ValueError:
                contained = False
            if not contained:
                continue

            if info.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zip_ref.open(info) as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)


async def _resolve_activity_and_course(
    activity_uuid: str, db_session: AsyncSession
) -> tuple[Activity, Course, Organization]:
    statement = select(Activity).where(Activity.activity_uuid == activity_uuid)
    activity = (await db_session.execute(statement)).scalars().first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    statement = select(Course).where(Course.id == activity.course_id)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    statement = select(Organization).where(Organization.id == course.org_id)
    org = (await db_session.execute(statement)).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return activity, course, org


def _scorm_content_directory(course_uuid: str, activity_uuid: str) -> str:
    return f"courses/{course_uuid}/activities/{activity_uuid}/scorm"


async def upload_scorm_package(
    request: Request,
    activity_uuid: str,
    zip_file: UploadFile,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> Activity:
    """Extract and store a SCORM 1.2 package, then point the activity at it.

    Replaces any previously uploaded package for this activity — the whole
    scorm/ subdirectory is wiped first so a re-upload can't leave stale
    files from a differently-structured earlier package behind.
    """
    activity, course, org = await _resolve_activity_and_course(activity_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    header = await zip_file.read(4)
    await zip_file.seek(0)
    if not validate_scorm_zip(header):
        raise HTTPException(status_code=415, detail="File must be a ZIP package")

    with tempfile.TemporaryDirectory(prefix="lh_scorm_") as temp_dir:
        zip_path = os.path.join(temp_dir, "package.zip")
        with open(zip_path, "wb") as f:
            size = 0
            while chunk := await zip_file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SCORM_PACKAGE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Package too large. Maximum size is {MAX_SCORM_PACKAGE_SIZE / 1024 / 1024:.0f}MB",
                    )
                f.write(chunk)

        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        _safe_extract_zip(zip_path, extract_dir)

        manifest_path = os.path.join(extract_dir, "imsmanifest.xml")
        if not os.path.isfile(manifest_path):
            raise HTTPException(status_code=400, detail="Invalid SCORM package: missing imsmanifest.xml")

        try:
            with open(manifest_path, "rb") as f:
                root = ET.fromstring(f.read())
        except ParseError:
            raise HTTPException(status_code=400, detail="Invalid SCORM package: unreadable imsmanifest.xml")

        version = detect_scorm_version(root)
        if version != ScormVersionEnum.SCORM_12:
            raise HTTPException(
                status_code=400,
                detail="This package looks like SCORM 2004, which isn't supported. Please export as SCORM 1.2.",
            )

        scos = extract_scos_from_manifest(root, version)
        if not scos:
            raise HTTPException(status_code=400, detail="Invalid SCORM package: no launchable content found in imsmanifest.xml")

        entry = scos[0]
        entry_full_path = os.path.join(extract_dir, entry.launch_path)
        if not os.path.isfile(entry_full_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid SCORM package: manifest points at '{entry.launch_path}', which isn't in the package",
            )

        content_dir = _scorm_content_directory(course.course_uuid, activity_uuid)

        # Clear anything from a previous upload before writing the new tree —
        # done via the same storage abstraction every other activity type's
        # deletion path uses, so it's a no-op cleanly on both local and S3.
        delete_storage_directory(f"content/orgs/{org.org_uuid}/{content_dir}")

        for root_dir, _dirs, files in os.walk(extract_dir):
            rel_dir = os.path.relpath(root_dir, extract_dir)
            for filename in files:
                local_path = os.path.join(root_dir, filename)
                with open(local_path, "rb") as f:
                    file_binary = f.read()
                sub_directory = content_dir if rel_dir == "." else f"{content_dir}/{rel_dir.replace(os.sep, '/')}"
                await upload_content(
                    directory=sub_directory,
                    type_of_dir="orgs",
                    uuid=org.org_uuid,
                    file_binary=file_binary,
                    file_and_format=filename,
                    allowed_formats=None,
                )

        package_title = get_package_title(root)

    activity.content = {
        **(activity.content or {}),
        "scorm_version": version.value,
        "scorm_entry_point": entry.launch_path,
        "scorm_title": package_title or entry.title,
        "scorm_mastery_score": entry.mastery_score,
    }
    activity.update_date = str(datetime.now())
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity


async def serve_scorm_file(
    request: Request,
    activity_uuid: str,
    file_path: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> Response:
    activity, course, org = await _resolve_activity_and_course(activity_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    safe_path = sanitize_path(file_path)
    if not safe_path:
        raise HTTPException(status_code=400, detail="Invalid file path")

    content_dir = _scorm_content_directory(course.course_uuid, activity_uuid)
    body = await read_content_nested(
        directory=content_dir,
        type_of_dir="orgs",
        uuid=org.org_uuid,
        relative_path=safe_path,
    )
    media_type, _ = mimetypes.guess_type(safe_path)
    return Response(content=body, media_type=media_type or "application/octet-stream")


async def get_scorm_tracking(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> ScormTrackingDataRead:
    activity, course, _org = await _resolve_activity_and_course(activity_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    if isinstance(current_user, AnonymousUser) or isinstance(current_user, APITokenUser):
        raise HTTPException(status_code=401, detail="Authentication required")

    statement = select(ScormTrackingData).where(
        ScormTrackingData.activity_id == activity.id,
        ScormTrackingData.user_id == current_user.id,
    )
    row = (await db_session.execute(statement)).scalars().first()
    if not row:
        return ScormTrackingDataRead(activity_uuid=activity_uuid)

    result = ScormTrackingDataRead.model_validate(row)
    result.activity_uuid = activity_uuid
    return result


async def upsert_scorm_tracking(
    request: Request,
    activity_uuid: str,
    tracking_update: ScormTrackingDataUpdate,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> ScormTrackingDataRead:
    """Applied on every LMSCommit/LMSFinish from the SCORM API shim.

    session_time_seconds is what THIS session ran, not a cumulative value —
    it's added onto the row's total_time_seconds rather than overwriting it,
    matching cmi.core.session_time's semantics (content reports elapsed time
    for the current attempt; the LMS is what accumulates it).
    """
    activity, course, _org = await _resolve_activity_and_course(activity_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    if isinstance(current_user, AnonymousUser) or isinstance(current_user, APITokenUser):
        raise HTTPException(status_code=401, detail="Authentication required")

    statement = select(ScormTrackingData).where(
        ScormTrackingData.activity_id == activity.id,
        ScormTrackingData.user_id == current_user.id,
    )
    row = (await db_session.execute(statement)).scalars().first()

    now_str = str(datetime.now())
    if not row:
        row = ScormTrackingData(
            org_id=activity.org_id,
            course_id=course.id,
            activity_id=activity.id,
            user_id=current_user.id,
            creation_date=now_str,
        )

    update_data = tracking_update.model_dump(exclude_unset=True, exclude={"session_time_seconds"})
    for field, value in update_data.items():
        setattr(row, field, value.value if isinstance(value, ScormLessonStatus) else value)

    if tracking_update.session_time_seconds:
        row.session_time_seconds = tracking_update.session_time_seconds
        row.total_time_seconds = (row.total_time_seconds or 0) + tracking_update.session_time_seconds

    row.update_date = now_str

    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    if row.lesson_status in SCORM_COMPLETING_STATUSES:
        try:
            await add_activity_to_trail(request, current_user, activity_uuid, db_session)
        except HTTPException as e:
            # Already-complete or similar benign states shouldn't fail the
            # tracking write the learner is actively waiting on — the trail
            # step either already reflects completion or genuinely can't
            # (e.g. anonymous user, guarded above), neither of which should
            # surface as an error on what is otherwise a successful commit.
            logger.info("Trail update skipped for SCORM completion on %s: %s", activity_uuid, e.detail)

    result = ScormTrackingDataRead.model_validate(row)
    result.activity_uuid = activity_uuid
    return result


async def delete_scorm_package(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> Activity:
    """Instructor-only: remove the uploaded package and its content fields.

    Tracking data is deliberately left in place — a teacher who removes a
    package (e.g. to fix a broken export before re-uploading) shouldn't
    silently wipe out learners' recorded completions/scores for it. A fresh
    upload just points the activity at new content; existing tracking rows
    stay keyed to the same activity_id and remain visible in results.
    """
    activity, course, org = await _resolve_activity_and_course(activity_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    content_dir = _scorm_content_directory(course.course_uuid, activity_uuid)
    delete_storage_directory(f"content/orgs/{org.org_uuid}/{content_dir}")

    content = dict(activity.content or {})
    for key in ("scorm_version", "scorm_entry_point", "scorm_title", "scorm_mastery_score"):
        content.pop(key, None)
    activity.content = content
    activity.update_date = str(datetime.now())
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity


async def list_scorm_results(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[ScormResultRow]:
    """Instructor-only: every learner's tracking row for this activity, for
    the results table in the activity editor. UPDATE-gated, same bar as
    uploading the package — this is authoring/reporting, not something a
    learner should see about their classmates.
    """
    activity, course, _org = await _resolve_activity_and_course(activity_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = (
        select(ScormTrackingData, User)
        .join(User, User.id == ScormTrackingData.user_id)
        .where(ScormTrackingData.activity_id == activity.id)
        .order_by(User.first_name, User.last_name)
    )
    rows = (await db_session.execute(statement)).all()

    return [
        ScormResultRow(
            user_id=user.id,
            user_uuid=user.user_uuid,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            lesson_status=tracking.lesson_status,
            score_raw=tracking.score_raw,
            score_max=tracking.score_max,
            total_time_seconds=tracking.total_time_seconds,
            update_date=tracking.update_date,
        )
        for tracking, user in rows
    ]
