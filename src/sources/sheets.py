import gspread
import os
import json

# Setup:
# 1. Enable Google Drive API and Google Sheets API.
# 2. Create Service Account -> Download JSON -> rename to credentials.json
# 3. Share the Target Sheet with the Service Account Email.

CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "YouTube-Automation-Control-Panel"


def get_db_connection():
    """Authenticates and returns the Sheet object."""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: {CREDENTIALS_FILE} not found.")
        return None

    try:
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sh = gc.open(SHEET_NAME)
        return sh.sheet1
    except Exception as e:
        print(f"Error connecting to Sheets: {e}")
        return None


def get_pending_jobs():
    """
    Reads rows where 'Status' column is 'Pending'.
    Assumes columns: ID, Topic, Channel, Status, ResultURL
    """
    sheet = get_db_connection()
    if not sheet:
        return []

    try:
        # Get all records
        records = sheet.get_all_records()
        pending = []

        # Note: get_all_records returns list of dicts. Keys match header row.
        for i, row in enumerate(records):
            if row.get("Status") == "Pending":
                # Store the row index (i+2 usually, 1 for header, 0-index list)
                row["_row_index"] = i + 2
                pending.append(row)

        return pending
    except Exception as e:
        print(f"Error reading pending jobs: {e}")
        return []


def update_job_status(row_index, status, result_url=""):
    """Updates the status of a job."""
    sheet = get_db_connection()
    if not sheet:
        return

    try:
        # Assuming:
        # Col 4 is Status
        # Col 5 is ResultURL
        # This is brittle; finding column index by name is better but Slower.
        # Hardcoding for MVP.
        sheet.update_cell(row_index, 4, status)
        if result_url:
            sheet.update_cell(row_index, 5, result_url)

        print(f"Updated row {row_index} to {status}")
    except Exception as e:
        print(f"Error updating job: {e}")


if __name__ == "__main__":
    # Test
    jobs = get_pending_jobs()
    print(f"Pending jobs: {jobs}")
