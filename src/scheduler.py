import time
import schedule
from src.sources import sheets
from src.factory import create_content


def job_check_sheet():
    """
    Checks the Google Sheet for any rows with Status="Pending".
    Processes them one by one.
    """
    print(f"[{time.strftime('%H:%M:%S')}] Checking Google Sheet for new jobs...")

    # 1. Fetch
    try:
        jobs = sheets.get_pending_jobs()
    except Exception as e:
        print(f"Sheet connection error: {e}")
        return

    if not jobs:
        return

    print(f"Found {len(jobs)} pending jobs.")

    # 2. Process
    for job in jobs:
        topic = job.get("Topic")
        channel = job.get("Channel")
        row_id = job.get("_row_index")

        if not topic:
            print(f"Skipping row {row_id}: Missing Topic")
            continue

        print(f"--- Processing Job: '{topic}' for '{channel}' ---")

        # Mark as Processing
        sheets.update_job_status(row_id, "Processing")

        try:
            # Generate Content
            # Note: This is synchronous and might take minutes.
            # For massive scale, we'd use a queue (Celery/Redis), but for this MVP, sync is fine.
            output_path = create_content(topic, channel)

            if output_path:
                # Success
                # In a real scenario, we might upload source file to S3/Drive and put that link here.
                # For local, we just put the path.
                sheets.update_job_status(row_id, "Done", result_url=str(output_path))

                # Optional: Trigger Upload immediately?
                # uploader.upload_video(...)
            else:
                # Logic failure (no script, etc)
                sheets.update_job_status(
                    row_id, "Error", result_url="Generation returned None"
                )

        except Exception as e:
            print(f"Job Critical Failure: {e}")
            sheets.update_job_status(row_id, "Error", result_url=str(e))


def start_scheduler():
    # Schedule the check
    # Check every 1 minute
    schedule.every(1).minutes.do(job_check_sheet)

    print("Scheduler started. Running loop...")
    print("Press Ctrl+C to stop.")

    # Run once immediately on start
    job_check_sheet()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    start_scheduler()
