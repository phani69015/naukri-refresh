import pytest
import responses

import drive
import handler
import naukri
from tests.test_naukri import mock_happy_path

LINK = "https://drive.google.com/file/d/abc_123-X/view?usp=sharing"


@pytest.mark.parametrize("link", [LINK, "https://drive.google.com/open?id=abc_123-X"])
def test_file_id(link):
    assert drive.file_id_from_link(link) == "abc_123-X"


def test_bad_link():
    with pytest.raises(drive.DriveError):
        drive.file_id_from_link("https://example.com/x")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("NAUKRI_USERNAME", "u")
    monkeypatch.setenv("NAUKRI_PASSWORD", "p")
    monkeypatch.setenv("RESUME_DRIVE_URL", LINK)


@responses.activate
def test_success_makes_one_attempt():
    responses.get(drive.DOWNLOAD_URL.format(file_id="abc_123-X"), body=b"%PDF-1")
    mock_happy_path()
    assert handler.lambda_handler({}, None)["status"] == "ok"
    logins = [c for c in responses.calls if c.request.url == naukri.LOGIN_URL]
    assert len(logins) == 1


@responses.activate
def test_failure_returns_without_retry():
    responses.get(drive.DOWNLOAD_URL.format(file_id="abc_123-X"), body=b"%PDF-1")
    responses.post(naukri.LOGIN_URL, status=403, body="blocked")
    assert handler.lambda_handler({}, None) == {"status": "failed"}
    assert len(responses.calls) == 2  # one download, one login; nothing repeated
