# PFPU Warehouse Manager
## Development Roadmap

### Step 1 — Location + access foundation
**COMPLETE**
- `ROW.SECTION.HEIGHT`
- QR-based locations/assets
- Dynamic locations
- Safe location retirement
- Flexible roles/positions
- Multiple positions per user

### Step 2 — IDs + statuses + roles
**COMPLETE**
- Job IDs
- Asset IDs
- Asset states
- Repair statuses
- Seven default positions
- Custom positions

### Step 3 — Architecture + documentation
**CURRENT**
Deliverables:
- Project Bible
- Database blueprint
- Roadmap

### Step 4 — Application foundation
- Power Factory Productions branding
- Clean project structure
- Database migration foundation
- Shared navigation/layout
- Today’s Command Center shell
- Preserve Excel import

### Step 5 — Inventory + locations
- Master items
- Asset creation
- QR generation
- Location creation/editing
- Optional location photos
- Movement/history
- Safe retirement

### Step 6 — Customers + jobs
- Customer database
- Job creation
- Equipment requirements
- Pricing
- Reservations
- Conflict detection

### Step 7 — Scan operations
- Check-out
- Check-in
- Prep
- Vehicle load/unload
- Lost/Found
- Exceptions
- Finalize checks

### Step 8 — Repair + audit
- Repair queue
- Audit mode
- Accounted-for offsite assets
- Discrepancy reports

### Step 9 — Permissions + production polish
- Position editor
- Permission matrix
- User management
- Export
- Backup/restore
- Windows launcher
- Network deployment testing


---

# Release-First Development Plan — October 2026

## Objective

Deliver PFPU Warehouse Manager v1.0.0 to Power Factory Productions as soon as the essential warehouse workflows are dependable.

The software developer retains ownership of the application and plans to provide one year of post-delivery support.

During that support period, development will continue through controlled updates, bug fixes, and new features.

## Current Development Checkpoint

- Last completed feature: Completed Job History and Equipment Movement Tracking
- Git commit: `13b1d43`
- Current target: v1.0.0 Initial Production Release

## Required Before v1.0.0

### Inventory Import

- [ ] Excel/CSV inventory import
- [ ] Import preview and validation
- [ ] Duplicate detection
- [ ] Quantity-only import support
- [ ] Verify imported inventory totals

### Backup and Restore

- [ ] Database backup
- [ ] Restore from backup
- [ ] Backup verification
- [ ] Preserve uploaded files and application data
- [ ] Pre-update backups

### Software Updates

- [ ] Application version and release metadata
- [ ] Administrator-only update controls
- [ ] Check for approved releases
- [ ] Separate Windows updater process
- [ ] Update package verification
- [ ] Stop and restart application safely
- [ ] Preserve database and uploaded files
- [ ] Apply database migrations
- [ ] Verify application health after updating
- [ ] Document recovery procedure

### Release-Blocking Testing

- [ ] Full job lifecycle regression test
- [ ] Inventory quantity consistency checks
- [ ] Permissions and security checks
- [ ] Equipment movement history verification
- [ ] Inspection and repair safety checks
- [ ] Basic multi-user testing
- [ ] Fix critical defects

### Windows Delivery

- [ ] Clean Windows installation test
- [ ] Startup and restart verification
- [ ] Local network access test
- [ ] Installer upgrade test
- [ ] Administrator setup instructions
- [ ] v1.0.0 release build and Git tag

## Post-Release Roadmap

### v1.0.x — Maintenance

- Bug fixes
- Reliability improvements
- Warehouse feedback
- Minor usability fixes

### v1.1 — Dashboard

- Needs Attention indicators
- Needs Tracking
- Missing Locations
- Repair alerts
- Operational priorities

### v1.2 — Repairs and Audits

- Repair history improvements
- Repair resolution workflow
- Inventory audit improvements
- Checked-out equipment audit handling

### v1.3 — User Experience

- Navigation and tablet layout improvements
- Scanner input improvements
- Customer and vehicle form improvements
- Job pack improvements
- Reporting and export enhancements

## Release Principles

1. Do not overwrite the production database during updates.
2. Preserve warehouse records, uploaded photos, and configuration.
3. Back up production data before every update.
4. Test new versions before deploying them to PFP.
5. Require administrator approval for updates.
6. Keep database migrations versioned and tested.
7. Do not delay v1.0 for nonessential enhancements.
8. Continue development during the planned one-year support period.

## Immediate Development Order

1. Backup and restore
2. Inventory import
3. Software update system
4. Release-blocking testing
5. Windows v1.0.0 release

**Development strategy: Ship a dependable working product first, then improve it through supported updates.**