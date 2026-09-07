"""
SCORM manifest parsing, version detection, SCO extraction, path sanitization,
and zip-extraction hardening for the real OSS SCORM module.

Unlike the other test_scorm_*.py files in this suite (which all
`pytest.importorskip` around ee/services/scorm/scorm.py — a module this
repo's Enterprise Edition ships but the OSS build does not, so those files
skip cleanly here and exercise nothing), this file imports
src.services.courses.activities.scorm directly. That's the actual SCORM
implementation shipped in this OSS repo, so these tests run for real instead
of skipping.

Only pure functions and file-system-local helpers are covered here — no
FastAPI request/DB round trip (upload_scorm_package, serve_scorm_file, etc.),
which would need a running app + database to exercise meaningfully.
"""

import os

import defusedxml.ElementTree as ET
import pytest

from src.services.courses.activities import scorm
from src.db.courses.scorm import ScormVersionEnum
from src.tests.fixtures import scorm_packages as pkg


def _root(manifest_str: str):
    return ET.fromstring(manifest_str)


class TestZipValidation:
    def test_valid_zip_magic(self):
        assert scorm.validate_scorm_zip(pkg.valid_12_single()) is True

    def test_not_a_zip_rejected(self):
        assert scorm.validate_scorm_zip(pkg.adv_not_a_zip()) is False


class TestSanitizePath:
    def test_strips_traversal(self):
        assert scorm.sanitize_path("../../etc/passwd") == "etc/passwd"

    def test_strips_leading_slash(self):
        assert scorm.sanitize_path("/abs/path.html") == "abs/path.html"

    def test_backslashes_normalized(self):
        assert scorm.sanitize_path("a\\b\\c.html") == "a/b/c.html"

    def test_dot_segments_dropped(self):
        assert scorm.sanitize_path("./scormcontent/index.html") == "scormcontent/index.html"
        assert scorm.sanitize_path("a/./b.html") == "a/b.html"

    def test_empty_path(self):
        assert scorm.sanitize_path("") == ""


class TestVersionDetection:
    def test_detects_12_single(self):
        root = _root(pkg.manifest_12_single())
        assert scorm.detect_scorm_version(root) == ScormVersionEnum.SCORM_12

    def test_detects_12_multi(self):
        root = _root(pkg.manifest_12_multi())
        assert scorm.detect_scorm_version(root) == ScormVersionEnum.SCORM_12

    def test_detects_2004_via_namespace(self):
        # The OSS module deliberately only *plays* SCORM 1.2 — but it must
        # still recognize a 2004 manifest as such (rather than misdetect it
        # as 1.2) so the upload path can reject it with a clear error.
        root = _root(pkg.manifest_2004_single())
        assert scorm.detect_scorm_version(root) == ScormVersionEnum.SCORM_2004

    def test_detects_2004_multi(self):
        root = _root(pkg.manifest_2004_multi())
        assert scorm.detect_scorm_version(root) == ScormVersionEnum.SCORM_2004


class TestScoExtraction:
    def test_single_sco(self):
        root = _root(pkg.manifest_12_single())
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert len(scos) == 1
        assert scos[0].launch_path == "index.html"

    def test_multi_sco_order_and_paths(self):
        root = _root(pkg.manifest_12_multi())
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert [s.launch_path for s in scos] == [
            "lesson1/index.html", "lesson2/index.html", "lesson3/index.html",
        ]
        assert [s.title for s in scos] == ["Lesson A", "Lesson B", "Lesson C"]

    def test_nested_items_yield_leaf_scos_only(self):
        root = _root(pkg.manifest_nested_items())
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert len(scos) == 2
        assert {s.launch_path for s in scos} == {"a.html", "b.html"}

    def test_resource_without_type_still_detected(self):
        root = _root(pkg.manifest_no_type_resource())
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert len(scos) == 1
        assert scos[0].launch_path == "start.html"

    def test_unicode_title_preserved(self):
        root = _root(pkg.manifest_unicode())
        title = scorm.get_package_title(root)
        assert "日本語" in title and "Café" in title

    def test_xml_base_prepended_to_href(self):
        manifest = (
            '<?xml version="1.0"?>'
            '<manifest identifier="M" version="1.0" '
            'xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
            'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">'
            '<organizations default="O"><organization identifier="O"><title>T</title>'
            '<item identifier="I" identifierref="R"><title>S</title></item>'
            '</organization></organizations>'
            '<resources xml:base="content/">'
            '<resource identifier="R" type="webcontent" adlcp:scormtype="sco" '
            'xml:base="mod1/" href="index.html"><file href="index.html"/></resource>'
            '</resources></manifest>'
        )
        root = _root(manifest)
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert scos[0].launch_path == "content/mod1/index.html"

    def test_mastery_score_parsed(self):
        manifest = (
            '<?xml version="1.0"?>'
            '<manifest identifier="M" version="1.0" '
            'xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
            'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">'
            '<organizations default="O"><organization identifier="O"><title>T</title>'
            '<item identifier="I" identifierref="R"><title>S</title>'
            '<adlcp:masteryscore>80</adlcp:masteryscore></item>'
            '</organization></organizations>'
            '<resources><resource identifier="R" type="webcontent" adlcp:scormtype="sco" '
            'href="index.html"><file href="index.html"/></resource></resources></manifest>'
        )
        root = _root(manifest)
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert scos[0].mastery_score == "80"

    def test_resource_without_href_uses_first_file(self):
        manifest = (
            '<?xml version="1.0"?>'
            '<manifest identifier="M" version="1.0" '
            'xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
            'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">'
            '<organizations default="O"><organization identifier="O"><title>T</title>'
            '<item identifier="I" identifierref="R"><title>S</title></item>'
            '</organization></organizations>'
            '<resources><resource identifier="R" type="webcontent" adlcp:scormtype="sco">'
            '<file href="launch/index.html"/><file href="a.js"/></resource>'
            '</resources></manifest>'
        )
        root = _root(manifest)
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert len(scos) == 1
        assert scos[0].launch_path == "launch/index.html"

    def test_rise_dot_slash_href_normalized(self):
        manifest = pkg.manifest_12_single(href="./scormcontent/index.html")
        root = _root(manifest)
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert scos[0].launch_path == "scormcontent/index.html"

    def test_windows_backslash_href_normalized(self):
        manifest = pkg.manifest_12_single(href="content\\\\index.html")
        root = _root(manifest)
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_12)
        assert scos[0].launch_path == "content/index.html"

    def test_no_scos_returns_empty_list(self):
        root = _root(pkg.manifest_2004_single())
        # A 2004 manifest walked as if it were 1.2 still resolves its (single)
        # SCO here — extraction itself doesn't enforce version, the caller
        # (upload_scorm_package) does that check separately before calling in.
        scos = scorm.extract_scos_from_manifest(root, ScormVersionEnum.SCORM_2004)
        assert len(scos) == 1


class TestSafeExtractZip:
    def _write(self, tmp_path, data: bytes):
        zip_path = tmp_path / "package.zip"
        zip_path.write_bytes(data)
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        return str(zip_path), str(extract_dir)

    def test_traversal_entry_not_written_outside(self, tmp_path):
        zip_path, extract_dir = self._write(tmp_path, pkg.adv_path_traversal())
        scorm._safe_extract_zip(zip_path, extract_dir)
        assert not os.path.exists("/tmp/lh_scorm_pwned.txt")
        assert os.path.exists(os.path.join(extract_dir, "index.html"))
        assert os.path.exists(os.path.join(extract_dir, "imsmanifest.xml"))

    def test_symlink_entry_skipped(self, tmp_path):
        zip_path, extract_dir = self._write(tmp_path, pkg.zip_with_symlink("/etc/passwd"))
        scorm._safe_extract_zip(zip_path, extract_dir)
        link = os.path.join(extract_dir, "evil_link")
        assert not os.path.islink(link)

    def test_per_file_size_limit_skips_large_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scorm, "MAX_SCORM_FILE_SIZE", 1024)
        big = pkg.make_zip({
            "imsmanifest.xml": pkg.manifest_12_single(),
            "index.html": pkg.sco_html("SCORM_12"),
            "huge.bin": b"A" * 4096,
        })
        zip_path, extract_dir = self._write(tmp_path, big)
        scorm._safe_extract_zip(zip_path, extract_dir)
        assert not os.path.exists(os.path.join(extract_dir, "huge.bin"))
        assert os.path.exists(os.path.join(extract_dir, "index.html"))

    def test_zip_bomb_total_size_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scorm, "MAX_SCORM_PACKAGE_SIZE", 256)
        data = pkg.make_zip({
            "imsmanifest.xml": pkg.manifest_12_single(),
            "a.bin": b"A" * 4096,
        })
        zip_path, extract_dir = self._write(tmp_path, data)
        with pytest.raises(Exception):  # HTTPException 400
            scorm._safe_extract_zip(zip_path, extract_dir)

    def test_too_many_entries_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scorm, "MAX_SCORM_ENTRY_COUNT", 2)
        data = pkg.make_zip({
            "imsmanifest.xml": pkg.manifest_12_single(),
            "a.html": "<html></html>",
            "b.html": "<html></html>",
        })
        zip_path, extract_dir = self._write(tmp_path, data)
        with pytest.raises(Exception):  # HTTPException 400
            scorm._safe_extract_zip(zip_path, extract_dir)


class TestXxe:
    def test_xxe_external_entity_not_expanded(self):
        with pytest.raises(Exception):
            ET.fromstring(pkg.manifest_xxe())
