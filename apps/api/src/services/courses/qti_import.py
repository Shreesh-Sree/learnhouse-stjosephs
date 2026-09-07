"""QTI question-bank import: parse an uploaded QTI 1.2 file (or a zip of
them) into the editor's `blockQuiz` shape and land it as a new activity.

SCOPE DECISION (see PENDING_FEATURES.md for the full writeup):

- **QTI 1.2 only** — the classic `<questestinterop>` XML format most legacy
  quiz tools (Canvas's QTI export, Blackboard, ExamView, Respondus) still
  produce. The newer QTI 2.x/3.x XML schema (`<assessmentItem>`,
  `<simpleChoice>`, different namespaces entirely) is a different format,
  not a version bump, and is NOT parsed here.
- **Multiple-choice only** (including true/false, which is just a
  two-option multiple-choice under the hood) — both single-answer and
  select-all-that-apply. Essay, short-answer/fill-in-blank, matching, and
  ordering items are recognised and SKIPPED (reported back by identifier
  and reason), not silently dropped or mis-imported as something they are
  not.
- The import lands as ONE NEW activity (a custom content page with a single
  `blockQuiz` block holding every successfully parsed question) in a
  chapter the caller picks — reusing the exact block shape
  `services/ai/quiz.py`'s `_to_block_quiz` already produces, so the result
  is immediately visible and editable in the normal course editor
  afterward. There is no separate "question bank" store independent of
  course content; importing IS authoring a quiz activity.

Namespace-agnostic local-tag matching and defusedxml (XXE protection)
deliberately mirror services/courses/activities/scorm.py's approach to the
same two problems (a real-world QTI export commonly declares the
`http://www.imsglobal.org/xsd/ims_qtiasiv1p2` namespace, inconsistently
across authoring tools) rather than introducing a second convention.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Optional
from uuid import uuid4

import defusedxml.ElementTree as ET
from defusedxml.ElementTree import ParseError
from fastapi import HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import ActivityCreate, ActivitySubTypeEnum, ActivityTypeEnum
from src.db.courses.chapters import Chapter
from src.db.courses.courses import Course
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.services.courses.activities.activities import create_activity
from sqlmodel import select

# --- Package limits (in-memory decompression only — no disk extraction,
# so the concerns are purely "don't let one upload exhaust RAM") ---------
MAX_QTI_ZIP_SIZE = 20 * 1024 * 1024
MAX_QTI_ENTRY_SIZE = 20 * 1024 * 1024
MAX_QTI_ENTRY_COUNT = 500
MAX_QTI_COMPRESSION_RATIO = 100


# ---------------------------------------------------------------------------
# Namespace-agnostic XML helpers (see module docstring)
# ---------------------------------------------------------------------------


def _local_tag(elem) -> str:
    tag = elem.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _iter_local(elem, tagname: str):
    for node in elem.iter():
        if _local_tag(node) == tagname:
            yield node


def _find_local(elem, tagname: str):
    for node in _iter_local(elem, tagname):
        return node
    return None


def _text_of(elem) -> str:
    """Concatenated text of every <mattext> under ``elem`` (an item's
    <material> may carry more than one, e.g. plain-text + HTML variants —
    the first is representative enough for a quiz prompt/option)."""
    mattext = _find_local(elem, "mattext")
    if mattext is None or mattext.text is None:
        return ""
    return mattext.text.strip()


@dataclass
class ParsedAnswer:
    text: str
    correct: bool


@dataclass
class ParsedQuestion:
    identifier: str
    question: str
    response_type: str  # "single" | "multiple"
    answers: list[ParsedAnswer] = field(default_factory=list)


@dataclass
class SkippedItem:
    identifier: str
    reason: str


def _parse_item(item) -> tuple[Optional[ParsedQuestion], Optional[str]]:
    """Returns (parsed, None) on success, or (None, skip_reason)."""
    identifier = item.get("ident") or item.get("identifier") or "unknown"

    presentation = _find_local(item, "presentation")
    if presentation is None:
        return None, "no <presentation> element"

    material = _find_local(presentation, "material")
    question_text = _text_of(material) if material is not None else ""

    response_lid = _find_local(presentation, "response_lid")
    if response_lid is None:
        # Not a choice-based item: essay (response_str with no render_choice),
        # fill-in-blank, matching (response_grp), ordering, etc.
        return None, "not a multiple-choice item (no response_lid/render_choice)"

    render_choice = _find_local(response_lid, "render_choice")
    if render_choice is None:
        return None, "not a multiple-choice item (no render_choice)"

    response_ident = response_lid.get("ident") or ""
    cardinality = (response_lid.get("rcardinality") or "Single").strip().lower()
    response_type = "multiple" if cardinality == "multiple" else "single"

    labels: dict[str, str] = {}
    for label in _iter_local(render_choice, "response_label"):
        label_ident = label.get("ident")
        if not label_ident:
            continue
        label_material = _find_local(label, "material")
        labels[label_ident] = _text_of(label_material) if label_material is not None else ""

    if not labels:
        return None, "no answer options found"

    # Determine which option ids are correct. A <respcondition> marks its
    # referenced option(s) correct when it awards a positive score — the
    # conventional QTI 1.2 authoring pattern (Canvas, Respondus, ExamView
    # all export this shape): one respcondition per correct choice (or one
    # with an <and> of several, for a select-all-that-apply item), each
    # containing a <setvar action="Set|Add" varname="SCORE">positive</setvar>.
    resprocessing = _find_local(item, "resprocessing")
    correct_ids: set[str] = set()
    if resprocessing is not None:
        for respcondition in _iter_local(resprocessing, "respcondition"):
            setvars = list(_iter_local(respcondition, "setvar"))
            awards_points = False
            for setvar in setvars:
                raw = (setvar.text or "").strip()
                try:
                    awards_points = float(raw) > 0
                except ValueError:
                    # A non-numeric setvar value (rare, malformed export) is
                    # treated as "this branch matters" rather than ignored —
                    # failing to import real correct answers is worse than
                    # occasionally importing an extra one a human can uncheck.
                    awards_points = bool(raw)
                if awards_points:
                    break
            if not setvars or not awards_points:
                continue
            for varequal in _iter_local(respcondition, "varequal"):
                # varequal's respident should match this response_lid, but
                # some exports omit it on a single-response item — accept
                # either an explicit match or an absent respident.
                respident = varequal.get("respident")
                if respident and response_ident and respident != response_ident:
                    continue
                value = (varequal.text or "").strip()
                if value:
                    correct_ids.add(value)

    if not correct_ids:
        return None, "no correct answer could be determined from resprocessing"

    answers = [
        ParsedAnswer(text=text, correct=(label_ident in correct_ids))
        for label_ident, text in labels.items()
    ]
    if not any(a.correct for a in answers):
        return None, "resprocessing referenced an option id not present in render_choice"

    # The answer key wins over the declared cardinality, same rule
    # services/ai/quiz.py's _to_block_quiz applies to AI-generated quizzes.
    if sum(1 for a in answers if a.correct) >= 2:
        response_type = "multiple"

    return (
        ParsedQuestion(
            identifier=identifier,
            question=question_text or "(no question text)",
            response_type=response_type,
            answers=answers,
        ),
        None,
    )


def parse_qti_items(xml_bytes: bytes) -> tuple[list[ParsedQuestion], list[SkippedItem]]:
    """Parse every <item> in one QTI 1.2 XML document, namespace-agnostic.

    Never raises for a malformed individual item — only a document that
    fails to parse as XML at all raises ParseError, which the caller
    surfaces as a 400.
    """
    root = ET.fromstring(xml_bytes)
    questions: list[ParsedQuestion] = []
    skipped: list[SkippedItem] = []
    for item in _iter_local(root, "item"):
        parsed, reason = _parse_item(item)
        if parsed is not None:
            questions.append(parsed)
        else:
            identifier = item.get("ident") or item.get("identifier") or "unknown"
            skipped.append(SkippedItem(identifier=identifier, reason=reason or "unknown error"))
    return questions, skipped


def _extract_xml_payloads(filename: str, content: bytes) -> list[bytes]:
    """Return the raw bytes of every XML document to parse: the file itself
    if it's a single QTI XML, or every `.xml` entry inside it if it's a zip
    (an IMS Content Package commonly bundles one XML per item or per
    assessment alongside a manifest this importer does not need to read —
    every `.xml` entry is scanned for <item> elements directly, manifest
    included, since a stray non-QTI XML entry simply yields zero items).
    """
    if content[:4] == b"PK\x03\x04" or content[:4] == b"PK\x05\x06":
        if len(content) > MAX_QTI_ZIP_SIZE:
            raise HTTPException(status_code=400, detail="QTI package exceeds the size limit")
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                infolist = zf.infolist()
                if len(infolist) > MAX_QTI_ENTRY_COUNT:
                    raise HTTPException(status_code=400, detail="QTI package has too many entries")
                uncompressed_total = sum(i.file_size for i in infolist)
                if uncompressed_total > MAX_QTI_ZIP_SIZE:
                    raise HTTPException(status_code=400, detail="QTI package uncompressed size exceeds the limit")
                if len(content) > 0 and uncompressed_total > len(content) * MAX_QTI_COMPRESSION_RATIO:
                    raise HTTPException(status_code=400, detail="QTI package has a suspicious compression ratio")

                payloads = []
                for info in infolist:
                    if not info.filename.lower().endswith(".xml"):
                        continue
                    if info.file_size > MAX_QTI_ENTRY_SIZE:
                        continue
                    payloads.append(zf.read(info))
                return payloads
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Could not read this file as a zip archive")
    else:
        if len(content) > MAX_QTI_ZIP_SIZE:
            raise HTTPException(status_code=400, detail="QTI file exceeds the size limit")
        return [content]


def build_block_quiz(questions: list[ParsedQuestion]) -> dict:
    """Stamp the ids the editor's `blockQuiz` node expects — same shape and
    same id convention as services/ai/quiz.py's `_to_block_quiz`, so an
    imported quiz is indistinguishable from an AI-generated or hand-authored
    one once it lands in the editor."""
    return {
        "quizId": f"quiz_{uuid4()}",
        "questions": [
            {
                "question_id": f"question_{uuid4()}",
                "question": q.question,
                "type": "multiple_choice",
                "response_type": q.response_type,
                "answers": [
                    {
                        "answer_id": f"answer_{uuid4()}",
                        "answer": a.text,
                        "correct": a.correct,
                    }
                    for a in q.answers
                ],
            }
            for q in questions
        ],
    }


async def import_qti_to_course(
    request: Request,
    course_uuid: str,
    chapter_id: int,
    filename: str,
    content: bytes,
    activity_name: Optional[str],
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """Parse the upload, create one new activity holding every successfully
    parsed question, and return an import report. RBAC is enforced by
    ``create_activity`` itself (CREATE on the chapter's course) — this
    function's own check is narrower: that ``chapter_id`` actually belongs
    to ``course_uuid``, so the URL's course and the chapter a caller happens
    to have rights on can never silently diverge (not itself a privilege
    escalation — create_activity checks the chapter's REAL course either
    way — but a caller passing a chapter_id from a different course than
    the one named in the URL is a bug, not a valid request, and should 404
    rather than quietly import into the wrong course).
    """
    course = (await db_session.execute(
        select(Course).where(Course.course_uuid == course_uuid)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    chapter = (await db_session.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )).scalars().first()
    if not chapter or chapter.course_id != course.id:
        raise HTTPException(status_code=404, detail="Chapter not found in this course")

    payloads = _extract_xml_payloads(filename, content)
    if not payloads:
        raise HTTPException(status_code=400, detail="No XML content found in the upload")

    all_questions: list[ParsedQuestion] = []
    all_skipped: list[SkippedItem] = []
    parse_errors = 0
    for payload in payloads:
        try:
            questions, skipped = parse_qti_items(payload)
        except ParseError:
            parse_errors += 1
            continue
        all_questions.extend(questions)
        all_skipped.extend(skipped)

    if not all_questions:
        raise HTTPException(
            status_code=400,
            detail=(
                "No importable multiple-choice questions were found in this file "
                f"({len(all_skipped)} item(s) skipped, {parse_errors} XML document(s) unparsable)."
            ),
        )

    block_quiz = build_block_quiz(all_questions)
    doc_content = {"type": "doc", "content": [{"type": "blockQuiz", "attrs": block_quiz}]}

    name = activity_name.strip() if activity_name and activity_name.strip() else f"Imported quiz ({filename})"
    activity = await create_activity(
        request,
        ActivityCreate(
            name=name,
            chapter_id=chapter_id,
            activity_type=ActivityTypeEnum.TYPE_CUSTOM,
            activity_sub_type=ActivitySubTypeEnum.SUBTYPE_CUSTOM,
            content=doc_content,
            published=False,
        ),
        current_user,
        db_session,
    )

    return {
        "activity_uuid": activity.activity_uuid,
        "questions_imported": len(all_questions),
        "questions_skipped": [{"identifier": s.identifier, "reason": s.reason} for s in all_skipped],
        "xml_parse_errors": parse_errors,
    }
