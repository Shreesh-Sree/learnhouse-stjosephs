#!/usr/bin/env python3
"""Unified Student Roster Ingestion for St. Joseph's Group of Institutions.

Dual provisions college students into:
  1. LearnHouse LMS (PostgreSQL: User, UserOrganization, Role=User)
  2. OpenEduCat College ERP (Odoo 17: op.student, op.student.course)
Optionally dispatches welcome credentials via Stalwart Mail (SMTP Port 465 SSL).

Usage:
  python3 scripts/import_student_roster.py --csv scripts/sample_batch_2026.csv [--send-emails] [--dry-run]
"""

import csv
import sys
import os
import argparse
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from uuid import uuid4
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import urllib3
from argon2 import PasswordHasher

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RosterImport")

# Database Configuration (LMS)
DB_HOST = os.environ.get("DB_HOST", "172.26.0.2")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "learnhouse")
DB_USER = os.environ.get("DB_USER", "learnhouse")
DB_PASS = os.environ.get("DB_PASSWORD", "LearnHouseDB_Pass2026!")

# OpenEduCat ERP Configuration
OPENEDUCAT_URL = os.environ.get("OPENEDUCAT_URL", "https://erp.stjosephsplacements.in").rstrip("/")
OPENEDUCAT_DB = os.environ.get("OPENEDUCAT_DB", "openeducat")
OPENEDUCAT_USER = os.environ.get("OPENEDUCAT_USER", "admin")
OPENEDUCAT_PASSWORD = os.environ.get("OPENEDUCAT_PASSWORD", "Admin@StJosephs2026!")

# SMTP Mail Server
SMTP_HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "notifications@stjosephsplacements.in")
SMTP_PASS = os.environ.get("SMTP_PASS", "Placements@sjgi#2026")
DEFAULT_STUDENT_PASS = "Student@SJGI2026!"

DEPT_COURSE_MAP = {
    "CSE": "BE-CSE",
    "CS": "BE-CSE",
    "IT": "BTECH-IT",
    "AIDS": "BTECH-AIDS",
    "AI&DS": "BTECH-AIDS",
    "AI-DS": "BTECH-AIDS",
    "ADS": "BTECH-AIDS",
    "ECE": "BE-ECE",
    "EEE": "BE-EEE",
    "MECH": "BE-MECH",
    "ME": "BE-MECH",
}

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
    )


def openeducat_jsonrpc(service: str, method: str, *args, timeout: float = 10.0):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": service,
            "method": method,
            "args": list(args),
        },
        "id": 1,
    }
    endpoint = f"{OPENEDUCAT_URL}/jsonrpc"
    resp = requests.post(endpoint, json=payload, timeout=timeout, verify=False)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        err = data["error"].get("data", {}).get("message") or data["error"].get("message")
        raise RuntimeError(f"OpenEduCat error: {err}")
    return data.get("result")


def get_openeducat_uid():
    return openeducat_jsonrpc(
        "common",
        "authenticate",
        OPENEDUCAT_DB,
        OPENEDUCAT_USER,
        OPENEDUCAT_PASSWORD,
        {},
    )


def sync_student_to_openeducat(uid: int, student: dict, dry_run: bool = False) -> bool:
    reg_no = student["register_number"].strip()
    full_name = student["student_name"].strip()
    email = student["college_email"].strip().lower()
    mobile = student.get("mobile_no", "").strip()

    dept = student.get("department", "CSE").strip().upper()
    course_code = DEPT_COURSE_MAP.get(dept, "BE-CSE")
    batch_code = f"{course_code}-2026"

    parts = full_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    if dry_run:
        logger.info("[DRY RUN] Would upsert OpenEduCat Student: %s (%s, Course %s)", reg_no, full_name, course_code)
        return True

    try:
        # Check if student exists
        existing = openeducat_jsonrpc(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.student",
            "search_read",
            [["|", ("gr_no", "=", reg_no), ("email", "=", email)]],
            {"fields": ["id", "name", "gr_no", "email"]},
        )

        if existing:
            student_id = existing[0]["id"]
            update_vals = {
                "name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
            }
            if mobile:
                update_vals["mobile"] = mobile
            if not existing[0].get("gr_no"):
                update_vals["gr_no"] = reg_no

            openeducat_jsonrpc(
                "object",
                "execute_kw",
                OPENEDUCAT_DB,
                uid,
                OPENEDUCAT_PASSWORD,
                "op.student",
                "write",
                [[student_id], update_vals],
            )
            logger.info("Updated OpenEduCat Student %s (%s, ID %s)", full_name, reg_no, student_id)
        else:
            student_vals = {
                "name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "gr_no": reg_no,
                "email": email,
                "gender": "m",
            }
            if mobile:
                student_vals["mobile"] = mobile

            student_id = openeducat_jsonrpc(
                "object",
                "execute_kw",
                OPENEDUCAT_DB,
                uid,
                OPENEDUCAT_PASSWORD,
                "op.student",
                "create",
                [student_vals],
            )
            logger.info("Created OpenEduCat Student %s (%s, ID %s)", full_name, reg_no, student_id)

        # Link to Course & Batch
        courses = openeducat_jsonrpc(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.course",
            "search_read",
            [[("code", "=", course_code)]],
            {"fields": ["id"]},
        )
        course_id = courses[0]["id"] if courses else None

        batches = openeducat_jsonrpc(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.batch",
            "search_read",
            [[("code", "=", batch_code)]],
            {"fields": ["id"]},
        )
        batch_id = batches[0]["id"] if batches else None

        if course_id:
            enrollments = openeducat_jsonrpc(
                "object",
                "execute_kw",
                OPENEDUCAT_DB,
                uid,
                OPENEDUCAT_PASSWORD,
                "op.student.course",
                "search_read",
                [[("student_id", "=", student_id), ("course_id", "=", course_id)]],
                {"fields": ["id"]},
            )
            if not enrollments:
                enroll_vals = {
                    "student_id": student_id,
                    "course_id": course_id,
                    "roll_number": reg_no,
                }
                if batch_id:
                    enroll_vals["batch_id"] = batch_id

                openeducat_jsonrpc(
                    "object",
                    "execute_kw",
                    OPENEDUCAT_DB,
                    uid,
                    OPENEDUCAT_PASSWORD,
                    "op.student.course",
                    "create",
                    [enroll_vals],
                )
                logger.info("Enrolled student %s in course %s (batch %s)", reg_no, course_code, batch_code)

        return True

    except Exception as e:
        logger.error("OpenEduCat request error for %s: %s", reg_no, e)
        return False


def sync_student_to_lms(conn, student: dict, hashed_pw: str, dry_run: bool = False) -> bool:
    reg_no = student["register_number"].strip()
    email = student["college_email"].strip().lower()
    full_name = student["student_name"].strip()
    parts = full_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    username = reg_no.lower()

    if dry_run:
        logger.info("[DRY RUN] Would upsert LMS User: %s (%s)", email, username)
        return True

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM \"user\" WHERE email = %s OR username = %s;", (email, username))
        existing = cur.fetchone()

        now_iso = datetime.now(timezone.utc).isoformat()
        now_str = str(datetime.now())

        if existing:
            user_id = existing["id"]
            cur.execute(
                """
                UPDATE "user"
                SET first_name = %s, last_name = %s, update_date = %s
                WHERE id = %s;
                """,
                (first_name, last_name, now_str, user_id),
            )
            logger.info("Updated LMS User ID %s (%s)", user_id, email)
        else:
            user_uuid = f"user_{uuid4()}"
            cur.execute(
                """
                INSERT INTO "user" (
                    username, first_name, last_name, email, password,
                    user_uuid, email_verified, email_verified_at, failed_login_attempts,
                    is_superadmin, creation_date, update_date, details, profile
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, true, %s, 0,
                    false, %s, %s, '{}', '{}'
                ) RETURNING id;
                """,
                (username, first_name, last_name, email, hashed_pw, user_uuid, now_iso, now_str, now_str),
            )
            user_id = cur.fetchone()["id"]
            logger.info("Created LMS User ID %s (%s)", user_id, email)

        # Link to organization 1 with Student User role (id=4)
        cur.execute(
            """
            INSERT INTO userorganization (user_id, org_id, role_id, creation_date, update_date)
            VALUES (%s, 1, 4, %s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (user_id, now_str, now_str),
        )

    conn.commit()
    return True


def send_welcome_email(student: dict, dry_run: bool = False) -> bool:
    email = student["college_email"].strip()
    name = student["student_name"].strip()
    reg_no = student["register_number"].strip()

    if dry_run:
        logger.info("[DRY RUN] Would send welcome email to %s", email)
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Welcome to St. Joseph's Placement & Training Cell Portal"
    msg["From"] = f"St. Joseph's Placements <{SMTP_USER}>"
    msg["To"] = email

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <div style="background: #1e3a8a; padding: 15px; border-radius: 6px; text-align: center; color: white;">
          <h2 style="margin: 0;">St. Joseph's Group of Institutions</h2>
          <p style="margin: 5px 0 0 0; font-size: 14px;">Placements and Training Cell</p>
        </div>
        <p>Dear <strong>{name}</strong> (Register No: <code>{reg_no}</code>),</p>
        <p>Your institutional portal access has been provisioned for the <strong>2026 Campus Placement Season</strong>.</p>
        <div style="background: #f8fafc; padding: 15px; border-radius: 6px; margin: 15px 0;">
          <h4 style="margin-top: 0;">Your Unified Login Credentials:</h4>
          <p style="margin: 4px 0;"><strong>LMS Portal:</strong> <a href="https://learn.stjosephsplacements.in">https://learn.stjosephsplacements.in</a></p>
          <p style="margin: 4px 0;"><strong>OpenEduCat College ERP:</strong> <a href="https://erp.stjosephsplacements.in">https://erp.stjosephsplacements.in</a></p>
          <p style="margin: 4px 0;"><strong>Username:</strong> <code>{reg_no.lower()}</code> or <code>{email}</code></p>
          <p style="margin: 4px 0;"><strong>Default Password:</strong> <code>{DEFAULT_STUDENT_PASS}</code></p>
        </div>
        <p>Please log in immediately to complete mandatory placement assessments and verify your academic profile.</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #777;">St. Joseph's Placements & Training Cell &bull; Old Mahabalipuram Road, Chennai</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=5) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [email], msg.as_string())
        logger.info("Sent welcome email to %s", email)
        return True
    except Exception as e:
        logger.warning("Failed to send welcome email to %s: %s", email, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Import student roster into LearnHouse LMS & OpenEduCat ERP")
    parser.add_argument("--csv", required=True, help="Path to student roster CSV file")
    parser.add_argument("--send-emails", action="store_true", help="Send welcome credentials via SMTP")
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without committing changes")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        logger.error("CSV file not found: %s", args.csv)
        sys.exit(1)

    students = []
    with open(args.csv, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("register_number") and row.get("college_email"):
                students.append(row)

    logger.info("Loaded %d students from %s", len(students), args.csv)
    if not students:
        logger.warning("No valid student rows found.")
        sys.exit(0)

    # Hash default student password once
    hashed_pw = ph.hash(DEFAULT_STUDENT_PASS)

    lms_conn = None
    openeducat_uid = None
    if not args.dry_run:
        lms_conn = get_db_connection()
        openeducat_uid = get_openeducat_uid()
        if not openeducat_uid:
            logger.error("Could not authenticate with OpenEduCat ERP. Aborting.")
            sys.exit(1)

    success_erp = 0
    success_lms = 0
    success_email = 0

    try:
        for s in students:
            # 1. OpenEduCat ERP Sync
            if sync_student_to_openeducat(openeducat_uid, s, dry_run=args.dry_run):
                success_erp += 1

            # 2. LMS Sync
            if sync_student_to_lms(lms_conn, s, hashed_pw, dry_run=args.dry_run):
                success_lms += 1

            # 3. Email Dispatch
            if args.send_emails:
                if send_welcome_email(s, dry_run=args.dry_run):
                    success_email += 1

    finally:
        if lms_conn:
            lms_conn.close()

    logger.info("=== IMPORT SUMMARY ===")
    logger.info("Total Students Processed: %d", len(students))
    logger.info("OpenEduCat Student Profiles: %d/%d", success_erp, len(students))
    logger.info("LearnHouse LMS Accounts Provisioned: %d/%d", success_lms, len(students))
    if args.send_emails:
        logger.info("Welcome Emails Dispatched: %d/%d", success_email, len(students))
    logger.info("======================")


if __name__ == "__main__":
    main()
