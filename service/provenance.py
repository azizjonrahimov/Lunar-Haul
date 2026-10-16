"""Provenance of a run (PLAN 5.6, research note Q6) and discovery of the data files the API serves.

A run record stores the code identity (engine semver, git sha, dirty flag, patch sha), the
environment identity (lock sha, python, platform), the input identity (scenario sha, mechanism,
options, seeds, policy-file shas) and the output identity (output sha). This module computes the
code/environment part and the policy shas; the scenario and output hashes live in worker.py.

Engine version string: ``3.0.0`` when HEAD carries the tag ``v3.0.0`` and the tree is clean, else the
PEP 440 local form ``3.0.0+g<sha7>[.dirty]``. The leaderboard ranks only runs whose engine_version has
no local part (that is PLAN's "git_dirty=false runs on tagged releases").

The repository has no lockfile, so the "lock" is a generated text: pyproject.toml followed by every
installed distribution as ``name==version``; its sha256 is lock_sha and the text is stored as a blob.
"""
from __future__ import annotations

import dataclasses
import glob
import json
import os
import platform as _platform
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .util import sha256_bytes, sha256_file

_lock = threading.Lock()
_cache: Dict[str, "Provenance"] = {}


@dataclass
class Provenance:
    engine_version: str
    git_sha: Optional[str]
    git_dirty: Optional[bool]
    patch_sha: Optional[str]
    patch: Optional[bytes]
    lock_sha: str
    lock: bytes
    python: str
    platform: str
    tagged: bool

    def columns(self) -> Dict[str, Any]:
        """The runs-table columns."""
        return {"engine_version": self.engine_version, "git_sha": self.git_sha,
                "git_dirty": None if self.git_dirty is None else int(self.git_dirty),
                "patch_sha": self.patch_sha, "lock_sha": self.lock_sha, "python": self.python,
                "platform": self.platform}

    def public(self) -> Dict[str, Any]:
        d = self.columns()
        d["git_dirty"] = self.git_dirty
        d["tagged"] = self.tagged
        return d


def _git(repo_root: str, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace")


def _head_from_files(repo_root: str) -> Optional[str]:
    """Fallback without a git binary: resolve .git/HEAD by hand."""
    try:
        with open(os.path.join(repo_root, ".git", "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            p = os.path.join(repo_root, ".git", *ref.split("/"))
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    return f.read().strip()
            packed = os.path.join(repo_root, ".git", "packed-refs")
            if os.path.isfile(packed):
                with open(packed, encoding="utf-8") as f:
                    for line in f:
                        if line.strip().endswith(" " + ref):
                            return line.split()[0]
            return None
        return head
    except OSError:
        return None


def _lock_text(repo_root: str) -> bytes:
    from importlib import metadata
    parts: List[str] = []
    pp = os.path.join(repo_root, "pyproject.toml")
    if os.path.isfile(pp):
        with open(pp, "rb") as f:
            parts.append("# pyproject.toml\n" + f.read().decode("utf-8", "replace"))
    dists = sorted({(d.metadata["Name"] or "").lower(): d.version for d in metadata.distributions()}.items())
    parts.append("# installed distributions\n" + "\n".join(f"{n}=={v}" for n, v in dists if n) + "\n")
    return "\n".join(parts).encode("utf-8")


def collect(repo_root: str, refresh: bool = False) -> Provenance:
    """Measure the code and environment identity of this process (cached per repo_root)."""
    with _lock:
        if not refresh and repo_root in _cache:
            return _cache[repo_root]
    from lunarsim import __version__ as engine_version
    sha = (_git(repo_root, "rev-parse", "HEAD") or "").strip() or _head_from_files(repo_root)
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
    dirty: Optional[bool] = None if status is None else bool(status.strip())
    patch: Optional[bytes] = None
    patch_sha: Optional[str] = None
    if dirty:
        text = _git(repo_root, "diff", "HEAD", "--no-color")
        if text:
            patch = text.encode("utf-8")
            patch_sha = sha256_bytes(patch)
    tags = (_git(repo_root, "tag", "--points-at", "HEAD") or "").split()
    tagged = (f"v{engine_version}" in tags) and dirty is False
    version = engine_version
    if not tagged:
        version += "+g" + (sha[:7] if sha else "unknown")
        if dirty:
            version += ".dirty"
    lock = _lock_text(repo_root)
    prov = Provenance(engine_version=version, git_sha=sha, git_dirty=dirty, patch_sha=patch_sha, patch=patch,
                      lock_sha=sha256_bytes(lock), lock=lock, python=_platform.python_version(),
                      platform=_platform.platform(), tagged=tagged)
    with _lock:
        _cache[repo_root] = prov
    return prov


# ---------------------------------------------------------------------------------------------------------
# data files: policies, outcome tables, driving tables, terrain
# ---------------------------------------------------------------------------------------------------------
def policy_dir(repo_root: str) -> str:
    return os.path.join(repo_root, "data", "policies")


def terrain_dir(repo_root: str) -> str:
    return os.path.join(repo_root, "data", "terrain")


def _safe_id(s: str) -> bool:
    return bool(s) and all(c.isalnum() or c in "-_." for c in s) and not s.startswith(".")


def list_policies(repo_root: str) -> List[Dict[str, Any]]:
    """Cards of every lunarsim-policy and lunarsim-landing-outcomes JSON under data/policies (no weights)."""
    out = []
    for path in sorted(glob.glob(os.path.join(policy_dir(repo_root), "*.json"))):
        name = os.path.basename(path)
        if name.endswith(".check.json"):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        fmt = doc.get("format")
        if fmt not in ("lunarsim-policy", "lunarsim-landing-outcomes"):
            continue
        card = {k: v for k, v in doc.items() if k not in ("layers", "episodes", "rows", "samples")}
        card["id"] = name[:-5]
        card["file"] = name
        card["bytes"] = os.path.getsize(path)
        card["sha256"] = sha256_file(path)
        out.append(card)
    return out


def load_policy(repo_root: str, pid: str) -> Optional[Tuple[Dict[str, Any], str, str]]:
    """(document, sha256, path) of data/policies/<pid>.json, or None."""
    if not _safe_id(pid):
        return None
    path = os.path.join(policy_dir(repo_root), pid + ".json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return doc, sha256_file(path), path


def list_terrain(repo_root: str) -> List[Dict[str, Any]]:
    out = []
    for meta in sorted(glob.glob(os.path.join(terrain_dir(repo_root), "*", "meta.json"))):
        try:
            with open(meta, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        if doc.get("format") != "lunarsim-terrain":
            continue
        folder = os.path.dirname(meta)
        out.append({"id": os.path.basename(folder), "name": doc.get("name"), "site_id": doc.get("site_id"),
                    "size_m": doc.get("size_m"), "layers": doc.get("layers"), "source": doc.get("source"),
                    "stats": doc.get("stats"), "meta_sha256": sha256_file(meta),
                    "files": sorted(os.listdir(folder))})
    return out


def load_terrain(repo_root: str, tid: str) -> Optional[Dict[str, Any]]:
    if not _safe_id(tid):
        return None
    folder = os.path.join(terrain_dir(repo_root), tid)
    meta = os.path.join(folder, "meta.json")
    if not os.path.isfile(meta):
        return None
    with open(meta, encoding="utf-8") as f:
        doc = json.load(f)
    sites_p = os.path.join(folder, "sites.json")
    sites = None
    if os.path.isfile(sites_p):
        with open(sites_p, encoding="utf-8") as f:
            sites = json.load(f)
    files = {}
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            files[name] = {"bytes": os.path.getsize(p), "sha256": sha256_file(p)}
    return {"id": tid, "meta": doc, "sites": sites, "files": files}


def terrain_file(repo_root: str, tid: str, name: str) -> Optional[str]:
    """Absolute path of one file of a terrain pack, or None (names are basenames only)."""
    if not (_safe_id(tid) and _safe_id(name)) or os.sep in name or "/" in name:
        return None
    p = os.path.join(terrain_dir(repo_root), tid, name)
    return p if os.path.isfile(p) else None


def policy_shas(sc, repo_root: str) -> Dict[str, str]:
    """sha256 of every data file the engine will read for this effective Scenario:
    landing-outcome tables per lander class, the driving table, the terrain meta and sites files.
    Keys are repo-relative paths. Missing files raise FileNotFoundError (the run could not execute)."""
    from lunarsim import phase3 as P3
    shas: Dict[str, str] = {}

    def add(path: str) -> None:
        full = path if os.path.isabs(path) else os.path.join(repo_root, path)
        if not os.path.isfile(full):
            full = P3._find(path)
        if not os.path.isfile(full):
            raise FileNotFoundError(path)
        rel = os.path.relpath(full, repo_root).replace(os.sep, "/") if not os.path.isabs(path) else full
        shas[rel] = sha256_file(full)

    if getattr(sc, "landing_model", None):
        lm = P3.LandingModel(sc.landing_model)
        for cls, rate in (sc.landings_per_year or {}).items():
            if rate and rate > 0:
                add(lm._file(cls))
    if getattr(sc, "autonomy_model", None):
        am = sc.autonomy_model
        add(P3.DEFAULT_DRIVING if am in ("driving-v1", None) else am)
    if getattr(sc, "terrain", None):
        add(os.path.join("data", "terrain", sc.terrain, "meta.json"))
        add(os.path.join("data", "terrain", sc.terrain, "sites.json"))
    return shas


def interpreter() -> Dict[str, str]:
    return {"executable": sys.executable, "version": sys.version.split()[0]}


def as_dict(p: Provenance) -> Dict[str, Any]:
    d = dataclasses.asdict(p)
    d.pop("patch", None)
    d.pop("lock", None)
    return d
