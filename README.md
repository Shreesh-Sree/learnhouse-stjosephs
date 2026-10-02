<p align="center">
  <a href="https://lms.stjosephsplacements.in">
    <img src=".github/images/learnhouse-github.png" alt="LearnHouse St. Joseph's Edition" width="600" />
  </a>
</p>

<h3 align="center">LearnHouse LMS — St. Joseph's Group of Institutions Enterprise Edition</h3>

> **St. Joseph's Production Deployment & Enterprise Fork** of [learnhouse/learnhouse](https://github.com/learnhouse/learnhouse).  
> Fully enhanced with **Multi-Tenancy**, **Enterprise Edition (EE) features**, **Local GPU AI (SGLang Qwen 3.8 27B & Claude Gateways)**, **Firecrawl Web Intelligence & Educational Curation**, **Safe Exam Browser (SEB) lockdown**, **ERP Integrations (OpenEduCat / ERPNext)**, and **Strict Security & Superadmin Isolation**.

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg?style=flat" alt="License" /></a>
  <a href="https://lms.stjosephsplacements.in"><img src="https://img.shields.io/badge/Production-lms.stjosephsplacements.in-1d63ed.svg?style=flat" alt="Production Portal" /></a>
  <a href="https://admin.stjosephsplacements.in"><img src="https://img.shields.io/badge/Superadmin-admin.stjosephsplacements.in-indigo.svg?style=flat" alt="Superadmin Portal" /></a>
  <a href="https://github.com/Shreesh-Sree/learnhouse-stjosephs"><img src="https://img.shields.io/badge/Python-FastAPI%203.12-3776AB.svg?style=flat&logo=python&logoColor=white" alt="FastAPI" /></a>
  <a href="https://github.com/Shreesh-Sree/learnhouse-stjosephs"><img src="https://img.shields.io/badge/Frontend-Next.js%2014-black.svg?style=flat&logo=nextdotjs&logoColor=white" alt="Next.js" /></a>
  <a href="https://github.com/Shreesh-Sree/learnhouse-stjosephs"><img src="https://img.shields.io/badge/Database-PostgreSQL%2018%20%2B%20pgvector-4169E1.svg?style=flat&logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
</p>

---

## 🏛️ Deployment & Architecture Overview

This repository powers the centralized Learning Management System at **St. Joseph's Group of Institutions** (`stjosephsplacements.in`). It is deployed via Docker Compose with dedicated sub-services, database engines, and hardware acceleration:

```
                                  [ Cloudflare Tunnel / SSL ]
                                               │
                                               ▼
                                      [ Nginx Reverse Proxy ]
                                 (Port 80/443 SSL Termination)
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
         lms.stjosephsplacements.in                       admin.stjosephsplacements.in
         (Next.js App / Client Portal)                   (Isolated Superadmin Console)
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               │
                                               ▼
                                   [ LearnHouse API (FastAPI) ]
                                          (Port :8200)
                                               │
                 ┌─────────────────────────────┼─────────────────────────────┐
                 ▼                             ▼                             ▼
       [ PostgreSQL 18 + pgvector ]     [ Valkey / Redis 7 ]       [ ClickHouse Analytics ]
              (Port :5432)                 (Cache / RateLimit)          (Port :8123 / :9000)
                 │                             │                             │
                 └─────────────────────────────┼─────────────────────────────┘
                                               │
                                               ▼
                              [ Local AI & Intelligence Cluster ]
                         ├─ SGLang Local GPU (Qwen 3.8 27B / 262k context)
                         ├─ SJGI LiteLLM Claude Gateways (Sonnet 4.6 / Opus 4.6)
                         ├─ Firecrawl Service (:3092) for Web & Video Curation
                         └─ OpenEduCat ERP (erp.stjosephsplacements.in)
```

---

## 🚀 Key Institutional Additions & Enhancements

### 1. 🏢 Multi-Tenancy & Isolated Superadmin Security
- **Domain-Enforced Superadmin (`admin.stjosephsplacements.in`)**:
  - Superadmin routes (`/admin/*`) on any non-admin domain or tenant are intercepted and redirected via HTTP 307 directly to `https://admin.stjosephsplacements.in`.
  - Middleware proxy rules strictly isolate multi-tenant customer and student traffic from administrative tools.
  - Automatic tenant routing: authenticated students/teachers landing on the apex domain are directed directly to their organization workspace (`/dash`) instead of generic hubs.
- **Enterprise Edition (EE) Controllers Unlocked**:
  - Full multi-organization tenancy (`LEARNHOUSE_TENANCY=multi`).
  - White-labeling support with institutional logos, themes, and customized student login headers.
  - Multi-provider SSO / OIDC integration ready for Zitadel centralized identity.

### 2. 🧠 Local GPU AI & Enhanced Course Authoring Tools
- **Dedicated SGLang & LiteLLM Integration**:
  - AI services connect natively to the local high-throughput SGLang cluster running `qwen3.8-27b` with a massive 262k context window.
  - Seamless fallback and BYOK routing to Claude Sonnet 4.6 and Opus 4.6 via the SJGI LiteLLM cluster.
  - Strict bi-directional AI guardrails: inbound injection defense, real-time token sanitization, and sliding-window stream leak prevention.
- **Firecrawl Web & Video Research Engine**:
  - Integrated `search_web`, `find_video`, `search_educational_resources`, and `fetch_page_content`.
  - Automated video discovery: locates verified, live YouTube instructional videos and embeds them cleanly without hallucinated URLs.
  - Educational resource curation: pulls clean, structured markdown tutorials and code examples from GeeksforGeeks, W3Schools, and official documentation to generate realistic quizzes and lessons.

### 3. 🛡️ Exam Integrity & Classroom Lockdown
- **Safe Exam Browser (SEB) Enforcement**:
  - Configurable per-exam lockdown with cryptographic header-hash checks.
  - Auto-generated, downloadable `.seb` client configuration files and proctor quit passwords.
- **Proctoring & Anti-Cheating**:
  - Server-enforced countdown timers with deterministic auto-submit.
  - Question pool randomization and randomized answer choices per student attempt.
  - Periodic webcam snapshot auditing (instructor-only access).
  - Campus IP range allowlisting that fails closed.

### 4. 📊 Assessment, Grading & Academic Workflows
- **Group & Peer Evaluations**:
  - Collaborative group assignments with shared team submissions and consolidated grading.
  - Advisory double-blind peer review system.
  - Rubric-based scoring matrices with criteria breakdowns and bonus/deduction tracking.
- **Integrity & Auditing**:
  - Native in-house code and text similarity check without sending student data to third-party APIs.
  - Student question-flagging workflow with instructor review inbox.
  - Multi-hop prerequisite cycle detection preventing cyclic course dependencies ($A \to B \to C \to A$).

### 5. 🔗 College ERP & Institutional Ecosystem
- **OpenEduCat & ERPNext Bidirectional Sync**:
  - Automated roster and student profile ingestion from `erp.stjosephsplacements.in`.
  - Dual ingestion support for gradebook exports and course enrollments.
- **Interoperability**:
  - LTI 1.1 Tool Provider support for external LMS integration.
  - QTI 1.2 question-bank import (Canvas / Blackboard / Respondus compatible).
  - Native SCORM 1.2 package player.
  - Dynamic ICS calendar feeds for assignment milestones and live training sessions.

---

## 🛠️ Stack & Infrastructure Details

| Layer | Component | Notes |
|---|---|---|
| **Frontend** | Next.js 14, React 18, TailwindCSS, Radix UI | SSR + static generation with responsive dark/light UI |
| **Backend** | Python 3.12, FastAPI, SQLModel, Pydantic v2 | High-performance asynchronous REST API |
| **Primary DB** | PostgreSQL 18 with `pgvector` | High-dimensional embeddings and relational storage |
| **Cache & Bus** | Valkey / Redis 7 Alpine | Rate-limiting, session store, background task dispatch |
| **Analytics** | ClickHouse 24.2 + Tinybird Adapter | Real-time event streaming and course audit logs |
| **Collab** | Hocuspocus, Yjs, WebSockets | Real-time collaborative whiteboard and rich-text editing |
| **AI Runtime** | SGLang GPU + LiteLLM Gateway | Local 27B parameter inference + Bedrock/Claude models |
| **Scraping** | Firecrawl Local Instance (:3092) | Clean markdown extraction and video search |

---

## 🏃 Self-Hosting & Production Operations

### Environment Configuration
The application is configured using `/data/production/lms/.env`. Key environment variables:

```bash
# Domain & Routing
LEARNHOUSE_DOMAIN=lms.stjosephsplacements.in
LEARNHOUSE_TENANCY=multi
LEARNHOUSE_COOKIE_DOMAIN=.stjosephsplacements.in
NEXT_PUBLIC_LEARNHOUSE_DOMAIN=lms.stjosephsplacements.in
NEXT_PUBLIC_LEARNHOUSE_MULTI_ORG=true

# Database & Cache
LEARNHOUSE_SQL_CONNECTION_STRING=postgresql://learnhouse:***@lms-db:5432/learnhouse
LEARNHOUSE_REDIS_CONNECTION_STRING=redis://lms-redis:6379/0
CLICKHOUSE_URL=http://lms-clickhouse:8123

# AI & LLM Services
LEARNHOUSE_AI_PROVIDER=openai-compatible
LEARNHOUSE_AI_BASE_URL=http://host.docker.internal:8888/v1
LEARNHOUSE_AI_MODEL_STANDARD=qwen3.8-27b
LEARNHOUSE_STUDENT_AI_BYOK=True

# Institutional ERP
LEARNHOUSE_OPENEDUCAT_ENABLED=True
LEARNHOUSE_OPENEDUCAT_URL=https://erp.stjosephsplacements.in
```

### Docker Compose Commands

```bash
# Check container status
docker compose ps

# View service logs in real time
docker compose logs -f lms-app

# Restart backend after configuration changes
docker compose restart lms-app

# Run database migrations
docker compose exec lms-app alembic upgrade head
```

---

## 🧪 Testing & Verification

All additions in this fork are verified against a live production environment:
- **Pytest Suite:** 5,730+ passed tests covering API endpoints, SSRF guards, cycle detection, and assessment logic.
- **Frontend Typecheck:** Full Next.js production build (`next build`) type-checks cleanly with zero errors.
- **Playwright E2E:** Automated end-to-end smoke tests validating authentication, SEB lockdown, course creation, and AI course generation.

---

## 📄 License & Attribution

- **Base Project:** Copyright (c) [LearnHouse Authors](https://github.com/learnhouse/learnhouse), licensed under [AGPL-3.0](LICENSE).
- **Institutional Fork & Enhancements:** Developed and maintained for the **St. Joseph's Group of Institutions Placement & Training Cell** by [@Shreesh-Sree](https://github.com/Shreesh-Sree) and the AI engineering team.
