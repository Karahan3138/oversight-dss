"""Downloads the Pyodide 0.26.4 runtime files the page needs into web/pyodide_files.

The page serves Pyodide from its own folder (no CDN). Wheels in the Pyodide release are stored
uncompressed; they are repacked with deflate to keep the page small, and the SHA-256 values in
pyodide-lock.json are updated to match.

Usage: python web/fetch_pyodide.py [target folder]
"""
import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.request
import zipfile

VERSION = "0.26.4"
URL = f"https://github.com/pyodide/pyodide/releases/download/{VERSION}/pyodide-{VERSION}.tar.bz2"
CORE = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
PACKAGES = ["numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl",
            "scipy-1.12.0-cp312-cp312-pyodide_2024_0_wasm32.whl",
            "openblas-0.3.26.zip",
            "clarabel-0.7.1-cp37-abi3-pyodide_2024_0_wasm32.whl"]


def repack(data):
    """Same archive members, deflate-compressed."""
    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info.filename), compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def main(target):
    os.makedirs(target, exist_ok=True)
    wanted = set(CORE + PACKAGES)
    got = {}
    print("downloading", URL)
    with urllib.request.urlopen(URL) as resp, tarfile.open(fileobj=resp, mode="r|bz2") as tar:
        for member in tar:
            name = os.path.basename(member.name)
            if member.isfile() and name in wanted:
                got[name] = tar.extractfile(member).read()
                print("  ", name, len(got[name]))
    missing = wanted - set(got)
    if missing:
        sys.exit(f"missing in release: {sorted(missing)}")
    lock = json.loads(got["pyodide-lock.json"])
    by_file = {p["file_name"]: p for p in lock["packages"].values()}
    for name in PACKAGES:
        data = repack(got[name])
        by_file[name]["sha256"] = hashlib.sha256(data).hexdigest()
        open(os.path.join(target, name), "wb").write(data)
    for name in CORE[:-1]:
        open(os.path.join(target, name), "wb").write(got[name])
    json.dump(lock, open(os.path.join(target, "pyodide-lock.json"), "w"))
    print("written to", target)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyodide_files"))
