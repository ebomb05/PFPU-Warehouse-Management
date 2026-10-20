
# PFPU Warehouse Manager — Project State

## Project Information

Project: PFPU Warehouse Manager  
Customer: Power Factory Productions  
Repository: https://github.com/ebomb05/PFPU-Warehouse-Management  
Branch: main  
Current checkpoint: a510b18  
Development version: 0.1.0

## Technology

- Python / FastAPI
- Jinja2 templates
- SQLite database
- Windows server deployment
- PyInstaller executable
- Inno Setup installer
- QR-based asset and location tracking

## Development Environment

Project directory:
C:\PFPU_Warehouse_Manager_4A

Development URL:
http://127.0.0.1:8000

Production data:
C:\ProgramData\Power Factory Productions\Warehouse Manager

Development workflow:
1. Inspect existing implementation before changing code.
2. Make small, controlled edits in VS Code.
3. Compile and test.
4. Browser-test operational changes.
5. Run git diff --check.
6. Commit and push stable checkpoints.

## Completed Features

- Core application and authentication
- Roles and permissions
- Inventory and item master
- Tracked asset generation
- Inventory quantity generation limits
- Asset QR codes and print queue
- Warehouse locations and location QR codes
- Rapid Location Assignment
- Asset Detail and Scan Station
- Customers, jobs, job packs, and vehicles
- Job Pull/PREP
- Vehicle loading
- Truck-level dispatch
- Job-level return to warehouse
- Global Inspection Station
- Return inspection routing to Shelf, PREP, or Repair
- Asset movement history and employee attribution
- Windows installer and startup task foundations
- PFPU branding

## Critical Workflow Decisions

Physical asset workflow:

Shelf → Pull/PREP → Truck → Job Site → Inspection → Shelf/PREP/Repair

Rules:

- Pull/PREP requires individual asset scans.
- Loading requires individual asset scans.
- Dispatch is one action per truck, not individual asset scans.
- Returning a job is one action that moves checked-out assets to INSPECTION.
- Trucks become operationally available immediately on return.
- Inspection requires individual asset scans.
- The global Inspection Station identifies the originating job automatically.
- Never guess an asset's storage location.
- Repair does not have to finish before a job can be completed.
- Completed jobs must remain in searchable history.
- Inventory asset generation must never exceed quantity owned.
- Multiple future jobs may reserve the same vehicle if schedules permit.

## Current Development Priority

### 1. Complete Job

Implement explicit job completion after all equipment is accounted for.

- Validate job state.
- Prevent completion with unresolved equipment.
- Record who completed the job.
- Record completion timestamp.
- Preserve job history.

### 2. Completed Job History

- Separate completed jobs from active operations.
- Search and view historical jobs.
- Preserve equipment and operational records.

## Remaining Roadmap

1. Complete Job and Job History
2. Needs Attention dashboard
3. Repair history and operational polish
4. Universal Excel/CSV import improvements
5. Tester feedback and UX improvements
6. Physical scanner and printer validation
7. Tablet/kiosk workflow
8. Installer, updater, backup and restore hardening
9. Admin activity and accountability reporting
10. Security and release testing
11. Detailed README and deployment documentation
12. PFPU v1.0 release candidate

## Known Follow-Up Items

- Admin password recovery utility
- Server-ready check before opening browser
- Vehicle scheduling conflict/turnaround validation
- Missing storage location handling
- Asset retirement policy and history
- Search and navigation improvements
- Completed repair search
- Printer-specific label dimensions
- Universal import column mapping
- Hardware workflow testing

## Development Rules

- Use VS Code unless Windows PowerShell is explicitly required.
- Prefer whole-file replacement for large changes.
- Prefer exact manual section replacement for small changes.
- Avoid complicated automated regex replacements.
- Diagnose problems before changing code.
- Do not remove existing permissions or safety checks.
- Keep job workflows separate from general Scan Station operations.
- Test before each Git checkpoint.

## Current Session

Last stable commit:
a510b18 — Enforce tracked asset inventory limits

Next task:
Inspect job status, job schema, and existing job history before implementing Complete Job.

Working tree at session start:
Clean.

## Session Handoff Instructions

When resuming development:

1. Read this document.
2. Check git status --short.
3. Check git log -1 --oneline.
4. Confirm application imports.
5. Review the current development priority.
6. Continue with small, tested changes.
7. Update this document at the end of the session.
