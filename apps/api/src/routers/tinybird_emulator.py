import os
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, Response, Query, HTTPException, status
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v0", tags=["tinybird_emulator"])

CLICKHOUSE_URL = os.environ.get("CLICKHOUSE_URL", "http://lms-clickhouse:8123").rstrip("/")
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "LearnHouseAnalytics2026!")

EVENTS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_name LowCardinality(String),
    timestamp DateTime,
    org_id Int64,
    user_id Int64,
    session_id String,
    properties String,
    source LowCardinality(String),
    ip String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (org_id, event_name, timestamp)
TTL timestamp + INTERVAL 365 DAY;
"""

_client: httpx.AsyncClient | None = None


def get_ch_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        auth = (CLICKHOUSE_USER, CLICKHOUSE_PASSWORD) if CLICKHOUSE_PASSWORD else None
        _client = httpx.AsyncClient(
            base_url=CLICKHOUSE_URL,
            auth=auth,
            timeout=30.0,
        )
    return _client


async def init_clickhouse_schema() -> bool:
    """Initialize ClickHouse events table if not exists."""
    try:
        client = get_ch_client()
        resp = await client.post("/", content=EVENTS_TABLE_SCHEMA.encode("utf-8"))
        if resp.status_code == 200:
            logger.info("ClickHouse events table initialized successfully")
            return True
        else:
            logger.warning("Failed to initialize ClickHouse events table (%s): %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        logger.warning("Could not connect to ClickHouse to initialize schema: %s", e)
        return False


def _normalize_event(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw event dictionary into ClickHouse table schema format."""
    event_name = str(item.get("event_name") or "unknown")
    ts = item.get("timestamp")
    if not ts:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts = str(ts).replace("T", " ").split(".")[0].replace("Z", "")

    try:
        org_id = int(item.get("org_id") or 0)
    except (ValueError, TypeError):
        org_id = 0

    try:
        user_id = int(item.get("user_id") or 0)
    except (ValueError, TypeError):
        user_id = 0

    session_id = str(item.get("session_id") or "")
    props = item.get("properties")
    if isinstance(props, (dict, list)):
        properties_str = json.dumps(props)
    elif isinstance(props, str):
        properties_str = props
    else:
        properties_str = "{}"

    source = str(item.get("source") or "api")
    ip = str(item.get("ip") or "")

    return {
        "event_name": event_name,
        "timestamp": ts,
        "org_id": org_id,
        "user_id": user_id,
        "session_id": session_id,
        "properties": properties_str,
        "source": source,
        "ip": ip,
    }


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_events(
    request: Request,
    name: str = Query("events", description="Datasource name"),
):
    """
    Tinybird Events API emulator: accepts JSON or NDJSON and forwards to ClickHouse.
    """
    body_bytes = await request.body()
    if not body_bytes:
        return {"successful_rows": 0, "quarantined_rows": 0}

    events_to_insert: list[dict[str, Any]] = []

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            parsed = json.loads(body_bytes.decode("utf-8"))
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        events_to_insert.append(_normalize_event(item))
            elif isinstance(parsed, dict):
                events_to_insert.append(_normalize_event(parsed))
        except Exception as exc:
            logger.warning("Tinybird emulator failed to parse JSON body: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
    else:
        # Try line-by-line NDJSON or fallback to JSON
        text = body_bytes.decode("utf-8", errors="replace").strip()
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    events_to_insert.append(_normalize_event(item))
            except Exception:
                pass

    if not events_to_insert:
        return {"successful_rows": 0, "quarantined_rows": 0}

    # Prepare JSONEachRow payload for ClickHouse
    ndjson_body = "\n".join(json.dumps(ev) for ev in events_to_insert) + "\n"

    client = get_ch_client()
    try:
        # Sanitize datasource name to prevent SQL injection
        safe_table = name.replace("`", "").replace(";", "").strip() or "events"
        resp = await client.post(
            f"/?query=INSERT+INTO+{safe_table}+FORMAT+JSONEachRow",
            content=ndjson_body.encode("utf-8"),
        )
        if resp.status_code >= 400:
            logger.error("ClickHouse ingest error (%s): %s", resp.status_code, resp.text[:400])
            raise HTTPException(status_code=502, detail=f"ClickHouse ingest failed: {resp.text[:200]}")
    except httpx.HTTPError as exc:
        logger.error("Failed to connect to ClickHouse during event ingest: %s", exc)
        raise HTTPException(status_code=502, detail="ClickHouse connection error")

    return {"successful_rows": len(events_to_insert), "quarantined_rows": 0}


@router.post("/sql")
async def execute_sql_post(request: Request, q: str | None = Query(None)):
    """
    Tinybird Query API emulator (POST): executes ClickHouse SQL queries and returns JSON.
    """
    query = q
    if not query:
        body_bytes = await request.body()
        if body_bytes:
            content_type = request.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                try:
                    data = json.loads(body_bytes.decode("utf-8"))
                    query = data.get("q") or data.get("sql")
                except Exception:
                    pass
            elif "application/x-www-form-urlencoded" in content_type:
                form = await request.form()
                query = form.get("q") or form.get("sql")
            
            if not query:
                # Raw text/sql query in body
                query = body_bytes.decode("utf-8", errors="replace")

    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Missing SQL query")

    return await _run_clickhouse_query(query)


@router.get("/sql")
async def execute_sql_get(q: str = Query(..., description="SQL query")):
    """
    Tinybird Query API emulator (GET): executes ClickHouse SQL query from parameter `q`.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Missing SQL query")
    return await _run_clickhouse_query(q)


async def _run_clickhouse_query(sql: str) -> Response:
    query_str = sql.strip()

    # If query is a SELECT or WITH, ensure it has FORMAT JSON
    upper_query = query_str.upper()
    if (upper_query.startswith("SELECT") or upper_query.startswith("WITH")) and "FORMAT " not in upper_query:
        query_str = query_str + " FORMAT JSON"

    client = get_ch_client()
    try:
        resp = await client.post("/", content=query_str.encode("utf-8"))
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
        )
    except httpx.HTTPError as exc:
        logger.error("ClickHouse query error: %s", exc)
        raise HTTPException(status_code=502, detail=f"ClickHouse query failed: {exc}")


@router.get("/datasources/{name}")
async def get_datasource(name: str):
    """Tinybird datasource inspection endpoint."""
    return {
        "name": name,
        "engine": "MergeTree",
        "status": "ok",
    }


@router.get("/ping")
async def ping():
    """Health check for Tinybird emulator."""
    return {"status": "ok", "backend": "clickhouse"}
