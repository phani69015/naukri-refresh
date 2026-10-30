"""Minimal Naukri client: log in and re-upload the resume to refresh the profile."""
import random
import re
import string

import requests

LOGIN_URL = "https://www.naukri.com/central-login-services/v1/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
DASHBOARD_URL = "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/dashboard"
FILE_UPLOAD_URL = "https://filevalidation.naukri.com/file"
RESUME_URL = "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/profiles/{profile_id}/advResume"

STATIC_JS_BASE = "https://static.naukimg.com/s/5/105/j/"
FALLBACK_MNJ_VERSIONS = ("_v323", "_v299")  # tried only if discovery fails

APP_JS_RE = re.compile(r'src="((?:https?:)?//static\.naukimg\.com/s/5/105/j/app_v\d+\.min\.js)"')
MNJ_VERSION_RE = re.compile(r'\bmnj\s*:\s*"(_v\d+)"')
FORM_KEY_RES = (
    re.compile(r'key:"initUploader".*?d\s*=\s*"([A-Za-z0-9]+)"', re.DOTALL),
    re.compile(r'd\s*=\s*"([A-Za-z0-9]{10,})"'),
)

TIMEOUT = 30
HEADERS = {
    "accept": "application/json",
    "appid": "105",
    "clientid": "d3skt0p",
    "systemid": "jobseeker",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}


class NaukriError(Exception):
    pass


class NaukriClient:
    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._http = requests.Session()
        self._http.headers.update(HEADERS)
        self._token = None

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", TIMEOUT)
        res = self._http.request(method, url, **kwargs)
        if not res.ok:
            raise NaukriError(f"{method} {url} -> {res.status_code}: {res.text[:300]}")
        return res

    def _auth_headers(self, **extra) -> dict:
        return {"authorization": f"Bearer {self._token}", "systemid": "Naukri", **extra}

    def login(self) -> None:
        self._request(
            "POST", LOGIN_URL,
            json={"username": self._username, "password": self._password},
            headers={"content-type": "application/json", "referer": "https://www.naukri.com/nlogin/login"},
        )
        self._token = self._http.cookies.get("nauk_at")
        if not self._token:
            raise NaukriError("Login gave no token (wrong credentials, or Naukri asked for OTP/MFA)")

    def _profile_id(self) -> str:
        data = self._request("GET", DASHBOARD_URL, headers=self._auth_headers()).json()
        pid = data.get("profileId") or data.get("dashBoard", {}).get("profileId")
        if not pid:
            raise NaukriError("Profile id not found in dashboard response")
        return pid

    def _form_key(self) -> str:
        """The resume uploader's formKey lives in Naukri's mnj JS bundle, whose version changes."""
        html = self._request("GET", PROFILE_URL, headers=self._auth_headers()).text
        urls = []
        app = APP_JS_RE.search(html)
        if app:
            app_url = "https:" + app.group(1) if app.group(1).startswith("//") else app.group(1)
            version = MNJ_VERSION_RE.search(self._request("GET", app_url).text)
            if version:
                urls.append(f"{STATIC_JS_BASE}mnj{version.group(1)}.min.js")
        urls += [f"{STATIC_JS_BASE}mnj{v}.min.js" for v in FALLBACK_MNJ_VERSIONS]

        for url in dict.fromkeys(urls):
            res = self._http.get(url, timeout=TIMEOUT)
            if not res.ok:
                continue
            for pattern in FORM_KEY_RES:
                match = pattern.search(res.text)
                if match:
                    return match.group(1)
        raise NaukriError("formKey not found in Naukri JS bundle")

    def refresh_resume(self, filename: str, pdf: bytes) -> str:
        """Upload the PDF as the profile's resume. Returns the profile id."""
        if not pdf.startswith(b"%PDF"):
            raise NaukriError("Resume is not a PDF")
        if not self._token:
            self.login()

        profile_id = self._profile_id()
        form_key = self._form_key()
        file_key = "U" + "".join(random.choices(string.ascii_letters + string.digits, k=13))

        upload = self._request(
            "POST", FILE_UPLOAD_URL,
            files={"file": (filename, pdf, "application/pdf")},
            data={"formKey": form_key, "fileName": filename, "uploadCallback": "true", "fileKey": file_key},
            headers={"origin": "https://www.naukri.com", "referer": "https://www.naukri.com/", "systemid": "fileupload"},
        )
        try:
            body = upload.json()
            if body and file_key not in body:
                file_key = next(iter(body))  # Naukri sometimes remaps the key
        except ValueError:
            pass

        self._request(
            "POST", RESUME_URL.format(profile_id=profile_id),
            json={"textCV": {"formKey": form_key, "fileKey": file_key}},
            headers=self._auth_headers(**{
                "content-type": "application/json",
                "origin": "https://www.naukri.com",
                "referer": "https://www.naukri.com/mnjuser/profile",
                "systemid": "105",
                "x-http-method-override": "PUT",
            }),
        )
        return profile_id
