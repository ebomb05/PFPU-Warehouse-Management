POWER FACTORY PRODUCTIONS WAREHOUSE MANAGER
STEP 4A - FOUNDATION RESTRUCTURE

WHAT CHANGED
- The single large app.py was split into:
  - pfpu_app/routes/
  - pfpu_app/services/
  - pfpu_app/database.py
  - pfpu_app/config.py
- Existing URLs and prototype behavior are intentionally preserved.
- Existing SQLite database and Excel copy are included.
- Old `uvicorn app:app` commands still work through a compatibility shim.
- New preferred launcher:
  start_pfpu_warehouse_manager.bat

WHAT DID NOT CHANGE YET
- No QR conversion yet.
- No new role/login system yet.
- No new location database model yet.
- No redesigned Command Center yet.
- Job numbering still behaves like the prototype in Step 4A.

TEST CHECKLIST
1. Double-click start_pfpu_warehouse_manager.bat
2. Dashboard opens.
3. Click Inventory.
4. Click Assets.
5. Click Jobs.
6. Open an existing job if present.
7. Click Scan Station.
8. Click Barcodes.
9. Click Export Excel and confirm a file downloads.
10. Stop the server with Ctrl+C in the black window.

IF ANYTHING FAILS
Send ChatGPT:
- the screen/page you were testing
- the last 20-30 lines from the black server window
Do not change code before we inspect the failure.
