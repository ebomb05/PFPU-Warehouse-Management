# Power Factory Productions Warehouse Manager
## Project Bible — v0.1

### Mission
Build a fast, simple warehouse operations system that replaces spreadsheet-only inventory handling with asset tracking, job-based checkout, QR scanning, location control, repair status, audit support, and clear daily workflow.

### Core principles
- Keep Version 1 focused on warehouse operations.
- Every feature should save time, reduce mistakes, or make training easier.
- Scanning should be faster than typing wherever possible.
- Workers should be informed by the system, not blocked unnecessarily.
- Exceptions should be visible to the person doing the work and escalated upward.
- Support gradual conversion from quantity-only inventory to individually tracked assets.

### Today’s Command Center
Default landing page for all users:
- Jobs going out today
- Jobs returning today
- Jobs in prep
- Missing/not-scanned items
- Equipment conflicts
- Items in repair
- Quick scan
- Unresolved exceptions

### Default positions
- System Administrator
- General Manager
- Warehouse Manager
- Warehouse Crew
- Driver / Event Crew
- Repair / Maintenance
- Office / Sales

Rules:
- Users may have multiple positions.
- Permissions combine.
- Admins can create custom positions.
- Permissions are granular.
- Useful operational information should remain visible even when edit rights are restricted.

### Locations
Shelf format: `ROW.SECTION.HEIGHT`
Example: `001.002.003`

Rules:
- Create/edit/retire locations in-app.
- Photos are optional.
- Full warehouse map is not required for Version 1.
- Asset moves create history.
- Locations can be Shelf, Prep, Repair, Lost/Found, Vehicle, Job Site, or custom.
- QR codes are used for locations.
- A location cannot be retired while assets remain assigned.
- Multiple storage spots for one item type are allowed, e.g. `CABLE_DVI (A)` and `CABLE_DVI (B)`.

### IDs
Job IDs: `JOB-YYYY-####`
Asset IDs examples:
- `SPK-000001`
- `MIC-000001`
- `MIX-000001`
- `CAB-000001`
- `LGT-000001`
- `VID-000001`

### Asset states
- Available
- Reserved
- Prep
- Loaded
- Checked Out
- Returning
- Repair
- Missing
- Retired

### Repair statuses
- In Repair
- Needs Parts
- Dead
- Needs Replaced
- Out of Commission
- Retired

### Exceptions
Scanning issues should create exceptions rather than silently fail.
Examples:
- Wrong item
- Item not on job
- Already assigned elsewhere
- Damaged
- Quantity short
- Missing
- Still checked out

Finalizing a job checks for unresolved issues. Manager/Admin can finalize with exception when needed.

### Return / Prep workflow
1. Scan returned asset.
2. Confirm previous job.
3. Check next reservation.
4. If needed again soon, recommend Prep.
5. Otherwise return to warehouse location.
6. If damaged, send to Repair.

### Lost / Found
User scans a found item and sees:
- Asset identity
- Current status
- Last known job
- Expected location
- Next reservation
- Recommended destination

### Vehicles
Vehicle records support:
- Name/number
- License plate
- VIN optional
- Insurance information
- Insurance card photo
- Maintenance dates/history
- Notes
- Active/inactive

### Audit mode
Audit totals must include known assets that are:
- Checked out
- On jobs
- In repair
- In prep
- On vehicles

Only genuinely unaccounted-for assets are discrepancies.

### Photos
Photos are optional.
Use small thumbnails in lists and load full images only on detail pages.

### Version 1 scope
- Excel import/export
- Master items
- Individual assets
- QR generation
- Customers
- Jobs
- Reservations/conflicts
- Check-in/out
- Locations
- Prep
- Repair
- Exceptions
- Vehicles
- Lost/Found
- Audit
- Roles/permissions
- Today’s Command Center

Deferred:
- Full CAD warehouse map
- Health scoring
- Advanced container/tote intelligence
