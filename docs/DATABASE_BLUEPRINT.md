# PFPU Warehouse Manager
## Database Blueprint — v0.1

### Core tables
- users
- positions
- permissions
- user_positions
- position_permissions
- customers
- master_items
- assets
- locations
- asset_location_history
- jobs
- job_requirements
- job_assets
- reservations
- exceptions
- repair_records
- vehicles
- job_vehicles
- scan_events
- audits
- audit_scans
- photos

### Key fields

#### master_items
- id
- category
- manufacturer
- model
- description
- original_quantity
- tracked_quantity
- untracked_quantity
- default_location_id
- active
- source_excel_row
- notes

#### assets
- id
- asset_code
- master_item_id
- serial_number
- qr_value
- state
- current_location_id
- current_job_id
- photo_thumbnail
- active
- created_at
- updated_at

#### locations
- id
- code
- name
- type
- row_number
- section_number
- height_number
- parent_location_id
- photo
- active
- notes

#### jobs
- id
- job_code
- customer_id
- job_name
- venue
- out_datetime
- return_datetime
- status
- total_price
- pricing_notes
- notes
- created_by
- created_at
- updated_at

#### repair_records
- id
- asset_id
- status
- issue
- notes
- parts_needed
- opened_by
- opened_at
- updated_by
- updated_at
- closed_at

#### vehicles
- id
- name
- vehicle_number
- license_plate
- vin
- insurance_provider
- insurance_policy
- insurance_expiration
- insurance_card_photo
- last_maintenance_date
- next_maintenance_date
- active
- notes

### Database rules
1. Asset codes are unique.
2. Job codes are unique.
3. Active shelf codes are unique.
4. Every asset move creates history.
5. Locations with assigned assets cannot be retired until assets are reassigned.
6. Checked-out, prep, repair, and vehicle assets count as accounted-for during audits.
7. Exceptions stay in history after resolution.
8. Access is permission-based, not hard-coded page-by-page.
