"""Descarga de tablas completas de StatCan y metadatos de frescura (WDS)."""
from __future__ import annotations

import json
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www150.statcan.gc.ca"
HEADERS = {"User-Agent": "statcan-labour-lab/0.1"}


def pid8(pid: str | int) -> str:
    """'14-10-0287-03' -> '14100287' (los 8 digitos del productId)."""
    digits = re.sub(r"\D", "", str(pid))
    if len(digits) < 8:
        raise ValueError(f"productId invalido: {pid}")
    return digits[:8]


def _request(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, data=data, headers={**HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def download_table(pid: str, cache_dir: Path, local_dir: Path | None = None, refresh: bool = False) -> Path:
    """Baja el zip de la tabla completa y deja el CSV (sin BOM) en cache_dir."""
    p = pid8(pid)
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"{p}.csv"
    if csv_path.exists() and not refresh:
        return csv_path

    zname = f"{p}-eng.zip"
    zpath = cache_dir / zname
    if local_dir is not None:  # modo pruebas: zips ya generados en disco
        shutil.copy(local_dir / zname, zpath)
    else:
        zpath.write_bytes(_request(f"{BASE}/n1/tbl/csv/{zname}"))

    with zipfile.ZipFile(zpath) as zf, zf.open(f"{p}.csv") as src, open(csv_path, "wb") as dst:
        first = src.read(1024 * 1024)
        if first.startswith(b"\xef\xbb\xbf"):
            first = first[3:]
        dst.write(first)
        shutil.copyfileobj(src, dst)
    zpath.unlink()
    return csv_path


def cube_metadata(pids: list[str]) -> list[dict]:
    """Titulo, rango de fechas y hora de release de cada tabla via WDS."""
    body = json.dumps([{"productId": int(pid8(p))} for p in pids]).encode()
    raw = _request(f"{BASE}/t1/wds/rest/getCubeMetadata", data=body, headers={"Content-Type": "application/json"})
    out = []
    for item in json.loads(raw):
        obj = item.get("object") or {}
        out.append(
            {
                "productId": obj.get("productId"),
                "title": obj.get("cubeTitleEn"),
                "start": obj.get("cubeStartDate"),
                "end": obj.get("cubeEndDate"),
                "release": obj.get("releaseTime"),
                "status": item.get("status"),
            }
        )
    return out
