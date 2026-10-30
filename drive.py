"""Download a public ("anyone with the link") Google Drive file."""
import re

import requests

FILE_ID_RES = (
    re.compile(r"/file/d/([\w-]+)"),
    re.compile(r"[?&]id=([\w-]+)"),
)
DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id={file_id}"


class DriveError(Exception):
    pass


def file_id_from_link(link: str) -> str:
    for pattern in FILE_ID_RES:
        match = pattern.search(link)
        if match:
            return match.group(1)
    raise DriveError("Could not find a file id in the Drive link")


def download(link: str, timeout: int = 30) -> bytes:
    res = requests.get(DOWNLOAD_URL.format(file_id=file_id_from_link(link)), timeout=timeout)
    if not res.ok:
        raise DriveError(f"Drive download failed: {res.status_code}")
    return res.content
