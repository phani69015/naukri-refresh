"""AWS Lambda entry point. Trigger daily with an EventBridge schedule.

Environment variables:
  NAUKRI_USERNAME, NAUKRI_PASSWORD  required
  RESUME_PATH                       optional, default "resume.pdf" (bundled in the zip)
"""
import logging
import os
from datetime import datetime, timezone

from naukri import NaukriClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    with open(os.environ.get("RESUME_PATH", "resume.pdf"), "rb") as f:
        pdf = f.read()

    # A fresh filename each day so the upload always registers as a new resume.
    filename = f"resume_{datetime.now(timezone.utc):%d_%B_%Y}.pdf".lower()

    client = NaukriClient(os.environ["NAUKRI_USERNAME"], os.environ["NAUKRI_PASSWORD"])
    client.login()
    profile_id = client.refresh_resume(filename, pdf)  # raises on failure -> Lambda marks run failed
    logger.info("Profile %s refreshed as %s", profile_id, filename)
    return {"status": "ok", "profile_id": profile_id, "file": filename}
