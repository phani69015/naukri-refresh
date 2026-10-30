import pytest
import responses

import naukri
from naukri import NaukriClient, NaukriError

APP_JS = "https://static.naukimg.com/s/5/105/j/app_v470.min.js"
MNJ_JS = naukri.STATIC_JS_BASE + "mnj_v400.min.js"


def mock_happy_path():
    responses.post(naukri.LOGIN_URL, json={}, headers={"Set-Cookie": "nauk_at=tok; Path=/"})
    responses.get(naukri.DASHBOARD_URL, json={"dashBoard": {"profileId": "P1"}})
    responses.get(naukri.PROFILE_URL, body=f'<script src="{APP_JS}"></script>')
    responses.get(APP_JS, body='_c={app:"_v470",mnj:"_v400"}')
    responses.get(MNJ_JS, body='key:"initUploader",x,d="ABCDEF123456"')
    responses.post(naukri.FILE_UPLOAD_URL, json={})
    responses.post(naukri.RESUME_URL.format(profile_id="P1"), json={})


@responses.activate
def test_refresh_resume_full_flow():
    mock_happy_path()
    client = NaukriClient("u", "p")
    client.login()
    assert client.refresh_resume("r.pdf", b"%PDF-1") == "P1"

    final = responses.calls[-1].request
    assert final.headers["x-http-method-override"] == "PUT"
    assert final.headers["authorization"] == "Bearer tok"
    assert b'"formKey": "ABCDEF123456"' in final.body


@responses.activate
def test_login_without_token_fails():
    responses.post(naukri.LOGIN_URL, json={})
    with pytest.raises(NaukriError, match="no token"):
        NaukriClient("u", "p").login()


@responses.activate
def test_rejects_non_pdf():
    with pytest.raises(NaukriError, match="not a PDF"):
        NaukriClient("u", "p").refresh_resume("r.pdf", b"nope")


@responses.activate
def test_http_error_raises():
    responses.post(naukri.LOGIN_URL, status=403, body="blocked")
    with pytest.raises(NaukriError, match="403"):
        NaukriClient("u", "p").login()
