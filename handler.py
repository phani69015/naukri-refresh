"""AWS Lambda entry point. Trigger once a day with an EventBridge schedule.

Runs exactly one attempt per invocation: no retries, no loops. On any failure it
logs the error and returns normally, so Lambda's async-retry never re-runs it.

Environment variables (all required):
  NAUKRI_USERNAME, NAUKRI_PASSWORD
  RESUME_DRIVE_URL   Google Drive share link, access "Anyone with the link"
"""
import logging
import os
from datetime import datetime, timezone

import drive
from naukri import NaukriClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    try:
        pdf = drive.download(os.environ["RESUME_DRIVE_URL"])
        # A fresh filename each day so the upload registers as a new resume.
        filename = f"Phanendra_CV_{datetime.now(timezone.utc):%d-%m-%Y}.pdf"

        client = NaukriClient(os.environ["NAUKRI_USERNAME"], os.environ["NAUKRI_PASSWORD"])
        client.login()
        profile_id = client.refresh_resume(filename, pdf)
    except Exception:
        logger.exception("Profile refresh failed; not retrying")
        return {"status": "failed"}

    logger.info("Profile %s refreshed as %s", profile_id, filename)
    return {"status": "ok", "profile_id": profile_id, "file": filename}
