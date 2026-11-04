"""Build the password-locked photo set for the slideshow.

Reads the images in one Google Drive folder (shared with a read-only service account), shrinks them to
screen size and encrypts each one with a key derived from PHOTOS_PASSWORD. Writes into OUT_DIR/photos/:
  meta.json   salt and iteration count (not secret)
  list.bin    the encrypted list of photo files (also proves the password is right)
  <n>.bin     each encrypted photo
Nothing here is committed: the workflow publishes OUT_DIR straight to GitHub Pages.

Environment: GDRIVE_SA_JSON (service account key), PHOTOS_FOLDER_ID, PHOTOS_PASSWORD.
For a local test, pass --local DIR to read images from a folder instead of Drive.
"""
import argparse
import base64
import io
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener  # iPhone photos (HEIC)
    register_heif_opener()
except ImportError:
    pass

MAX_SIDE = 1600
MAX_PHOTOS = 150
ITERATIONS = 250_000
API = "https://www.googleapis.com/drive/v3/files"


def drive_token(sa_json):
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    creds.refresh(Request())
    return creds.token


def drive_get(url, token):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + token}), timeout=120).read()


def drive_images(folder, token):
    files, page = [], ""
    while True:
        q = f"'{folder}' in parents and trashed = false and mimeType contains 'image/'"
        params = {"q": q, "fields": "nextPageToken,files(id,name)", "pageSize": 200, "orderBy": "createdTime desc",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if page:
            params["pageToken"] = page
        r = json.loads(drive_get(API + "?" + urllib.parse.urlencode(params), token))
        files += r.get("files", [])
        page = r.get("nextPageToken")
        if not page or len(files) >= MAX_PHOTOS:
            break
    for f in files[:MAX_PHOTOS]:
        yield f["name"], drive_get(f"{API}/{f['id']}?alt=media&supportsAllDrives=true", token)


def local_images(folder):
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                yield name, fh.read()


def shrink(data):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True)
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--local", help="read images from this folder instead of Google Drive")
    args = ap.parse_args()

    password = os.environ.get("PHOTOS_PASSWORD", "")
    if not password or not (args.local or (os.environ.get("GDRIVE_SA_JSON") and os.environ.get("PHOTOS_FOLDER_ID"))):
        print("Photos not set up (missing secrets); skipping.")
        return

    salt = secrets.token_bytes(16)
    key = AESGCM(PBKDF2HMAC(hashes.SHA256(), 32, salt, ITERATIONS).derive(password.encode()))
    seal = lambda data: (lambda iv: iv + key.encrypt(iv, data, None))(secrets.token_bytes(12))

    source = local_images(args.local) if args.local else drive_images(
        os.environ["PHOTOS_FOLDER_ID"], drive_token(os.environ["GDRIVE_SA_JSON"]))
    out = os.path.join(args.out_dir, "photos")
    os.makedirs(out, exist_ok=True)
    names = []
    for name, data in source:
        try:
            jpg = shrink(data)
        except Exception as e:  # a file Pillow cannot read; skip it rather than fail the whole update
            print(f"skipped {name}: {e}", file=sys.stderr)
            continue
        fn = f"{len(names)}.bin"
        with open(os.path.join(out, fn), "wb") as fh:
            fh.write(seal(jpg))
        names.append(fn)

    with open(os.path.join(out, "list.bin"), "wb") as fh:
        fh.write(seal(json.dumps(names).encode()))
    with open(os.path.join(out, "meta.json"), "w") as fh:
        json.dump({"salt": base64.b64encode(salt).decode(), "iterations": ITERATIONS}, fh)
    print(f"{len(names)} photos encrypted")


if __name__ == "__main__":
    main()
