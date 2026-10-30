# naukri-refresh

Daily Naukri profile refresh: logs in and re-uploads your resume so recruiters see a recently updated profile.

## Deploy (AWS Lambda, Python 3.12)
1. Upload your resume to Google Drive, share as "Anyone with the link" (viewer).
2. `./build.sh` -> `build/function.zip`
3. Create a Lambda, handler `handler.lambda_handler`, timeout 60s, upload the zip.
4. Env vars: `NAUKRI_USERNAME`, `NAUKRI_PASSWORD`, `RESUME_DRIVE_URL`, `RESUME_NAME` (e.g. `Phanendra_CV` -> `Phanendra_CV_30-10-2026.pdf`).
5. EventBridge schedule, e.g. `cron(30 3 * * ? *)`.
6. Strictly once a day: Lambda > Configuration > Asynchronous invocation > Retry attempts = 0.
   (The code already never retries or loops, and returns normally on failure.)

## Caveats
- Naukri blocks many datacenter IPs and may demand OTP; a failed run raises, so check CloudWatch.
- Unofficial API; may break when Naukri changes its site.

## Test
`python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest`
