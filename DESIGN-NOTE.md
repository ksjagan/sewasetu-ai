# Sewa Setu AI Assistant — Design Note
**Department of Social Welfare, Government of Purvanchal**  
*Author: Bharat Digital Fellow (2026)*

---

### Executive Summary

Sewa Setu manages monthly Direct Benefit Transfer (DBT) pension disbursements (₹250/month) for eligible citizens aged 60 and above across six administrative blocks. While consumer chatbots hallucinate or fail when interacting with government workflows, this system provides two official, streamable HTTP Model Context Protocol (MCP) endpoints—one for applicants and one for block officers—backed by an authoritative headless service layer that preserves the portal as the sole system of record.

---

### Part 1: The Three Decisions That Mattered Most

#### 1. Authoritative Headless Service Layer (`PortalService`)
- **The Decision**: Rather than having MCP tool handlers duplicate SQL queries or execute custom logic, all operations (eligibility checks, age calculation in Indian Standard Time, duplicate locking, credentials creation, and audit logging) are channeled through a single authoritative Python service layer shared with the web portal.
- **Why It Mattered**: The Director's IT team feared that AI assistants would skip validations or create unverified records. By guaranteeing 100% logic parity, an AI assistant is constrained by the exact same statutory rules as the counter form. If an applicant is 59 years old, or submits an invalid IFSC, both the portal and the AI assistant refuse the application with identical deterministic reasons.

#### 2. Absolute Role & Endpoint Isolation (`/mcp/citizen` vs `/mcp/officer`)
- **The Decision**: Exposing two completely separate endpoints rather than a single unified endpoint with permissions flags. The citizen endpoint exposes only applicant tools (`get_scheme_information`, `check_eligibility`, `request_otp`, `verify_otp`, `submit_pension_application`, `check_application_status`, `withdraw_pending_application`). The officer endpoint exposes only review and decision tools (`get_officer_dashboard_summary`, `list_pending_applications`, `get_application_dossier`, `approve_pension_application`, `reject_pension_application`).
- **Why It Mattered**: Consumer LLMs are susceptible to prompt injection. If an officer approval tool were present in the tool catalog with an internal permission check, a clever citizen prompt could trick a small model into attempting an administrative bypass. Physical endpoint separation ensures that a citizen assistant literally cannot see, discover, or invoke officer tools. Furthermore, OAuth 2.1 token validation enforces a 403 Forbidden barrier if a citizen token touches the officer endpoint.

#### 3. Urgency-Based Queue Sorting & Audit-Backed Accountability
- **The Decision**: The officer MCP tools sort pending queues by urgency—oldest `submitted_at` first—and calculate days remaining before the 15-day statutory deemed-approval guarantee under the Purvanchal Right to Public Services Act (RTPS). Every decision requires an explicit, non-empty justification note recorded against the officer's username in the immutable `audit_log`.
- **Why It Mattered**: Block officers face high caseloads and risk allowing eligible widows' applications to lapse into automatic deemed approval without verification. By calculating SLA countdowns in the tool response, the AI assistant immediately guides the officer to applications at risk. Mandatory audit logging ensures full bureaucratic accountability.

---

### Part 2: The One Decision I Would Make Differently With More Time

#### Asynchronous Object Storage & Multimodal OCR Verification
- **Current Approach**: Documents are validated by extension, size (up to 5MB), and written to disk storage (`/var/sewasetu/uploads`). Document inspection returns base64 payloads to the officer.
- **What I Would Do Differently**: With additional time, I would decouple file storage to S3-compatible object storage (e.g. MinIO) with pre-signed upload URLs, and implement an asynchronous OCR/Vision verification pipeline. When a citizen uploads a Voter ID or birth certificate, a local Vision model would extract the printed DOB and name, cross-referencing them against the typed form fields before submission. This would eliminate clerical errors and prevent unreadable documents from ever entering the officer's review queue.

---

### Part 3: 3-Minute Loom Presentation Blueprint

| Time | Slide / Screen | Talking Points |
| :--- | :--- | :--- |
| **0:00 - 0:45** | **Architecture & Endpoints** (Face + Screen showing dual MCPs & Docker stack) | Introduce yourself as the Bharat Digital Fellow. Explain the Sonari block problem (citizens struggling with web forms, consumer AI failing). Show the two MCP servers (`/mcp/citizen` and `/mcp/officer`) over Streamable HTTP and the OAuth 2.1 token barrier. |
| **0:45 - 1:45** | **Persona Walkthrough** (Screen on `/eval-dashboard`) | Walk through the invented personas: Smt. Ratna Das (happy path via grandson), Sri Biren Bora (underage rejection), Smt. Mina Chetia (duplicate prevention), and the CSC operator withdrawal lifecycle. Show how each conversation was asserted against PostgreSQL ground truth. |
| **1:45 - 2:30** | **Officer Assistant & Evals Demo** (Screen on Officer review & SLA aging) | Show how the officer assistant surfaces cases nearing the 15-day RTPS statutory cutoff and requires justification notes written to `audit_log`. Demonstrate the 100% pass rate on `/eval-dashboard`. |
| **2:30 - 3:00** | **Learnings & Conclusion** (Face + Screen) | Share the key takeaway: building AI for elderly citizens requires strict schema pre-flight validations and complete role isolation. Mention the design choice you would evolve with more time (asynchronous OCR pipeline). |
