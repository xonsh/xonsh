#!/usr/bin/xonsh
import io
import sys
import tempfile
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import zipfile

$RAISE_SUBPROC_ERROR = True

ARTIFACTS_URL = f"https://api.cirrus-ci.com/v1/artifact/build/{$CIRRUS_BUILD_ID}/docs/upload.zip"
DEST_REPO_URL = f"https://{$GITHUB_TOKEN}@github.com/xonsh/xonsh-docs.git"


branch_name = 'gh-pages' if $CIRRUS_TAG else 'dev'


with tempfile.TemporaryDirectory() as td:
    cd @(td)

    with urlopen(ARTIFACTS_URL) as resp:
        zipdata = resp.read()

    with zipfile.ZipFile(io.BytesIO(zipdata)) as zf:
        # nl = zf.namelist()
        # print(f"Found {len(nl)} files from build:", *nl)
        zf.extractall()

    # At this point, docs/_build/html should contain what we need to copy into
    # the destination repo

    ![git clone -b @(branch_name) --depth 1 @(DEST_REPO_URL) dest]
    cp -R docs/_build/html dest/

    # TODO: Commit & push
    cd dest
    git status