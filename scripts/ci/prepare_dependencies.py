"""Connected CI tool preparation only; this context contains no repository code."""

import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path

lock = json.loads(Path("/opt/local-ci/image-lock.json").read_bytes())
archive = next(a for a in lock["quarto_assets"] if a["name"].endswith("linux-arm64.tar.gz"))
target = Path("/opt/quarto.tar.gz")
digest = hashlib.sha256()
total = 0
with urllib.request.urlopen(archive["url"], timeout=60) as response, target.open("xb") as output:
    while chunk := response.read(1024 * 1024):
        total += len(chunk)
        if total > archive["bytes"]:
            raise RuntimeError("Quarto artifact exceeds pinned size")
        output.write(chunk)
        digest.update(chunk)
if total != archive["bytes"] or "sha256:" + digest.hexdigest() != archive["digest"]:
    raise RuntimeError("Quarto artifact identity mismatch")
with tarfile.open(target) as bundle:
    bundle.extractall("/opt/quarto-unpack", filter="data")
roots = list(Path("/opt/quarto-unpack").iterdir())
if len(roots) != 1 or not (roots[0] / "bin/quarto").is_file():
    raise RuntimeError("unexpected pinned Quarto layout")
roots[0].rename("/opt/quarto")
target.unlink()
