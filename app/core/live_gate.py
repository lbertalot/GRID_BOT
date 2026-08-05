"""Live gate dual signoff (ADR-007).

The first real dollar requires two human signatures (CEO + Desk Lead) on a
versioned, auditable artifact plus a fully checked go-live checklist. This
module only *reads* that artifact; it can never create or approve one.

Design rules:
- Fail-closed: a missing, unreadable, ambiguous or partially signed artifact
  means ``signed=False``. There is no code path where an error grants live.
- No secrets: the exported status carries checklist counters, roles, signer
  display names, timestamps and the config hash written by humans in the
  artifact. Never env values, never absolute paths.
- Stdlib only: this module is imported by the mode snapshot on hot paths.

Artifact discovery (first match wins):
1. ``LIVE_GATE_PATH`` — explicit file (absolute, or relative to the repo root).
2. ``LIVE_GATE_DIR`` — directory holding ``LIVE_GATE_<YYYYMMDD>.md|json``
   (default ``Docs/gates``). The newest filename wins.

``LIVE_GATE_TEMPLATE.md`` is committed for auditability and is always rejected
as a gate, so the repository itself can never arm live trading.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os

LIVE_GATE_PATH_ENV = "LIVE_GATE_PATH"
LIVE_GATE_DIR_ENV = "LIVE_GATE_DIR"
DEFAULT_GATE_DIR = "Docs/gates"
TEMPLATE_MARKER = "TEMPLATE"

# Roles that must both sign. Two signatures, never one (ADR-007).
REQUIRED_ROLES: Tuple[str, ...] = ("ceo", "desk_lead")
_ROLE_FIELDS = {"ceo": "ceo_signoff", "desk_lead": "desk_lead_signoff"}

# A gate artifact is a short human document; anything bigger is not a gate and
# is refused instead of parsed (cheap DoS guard on a read-only endpoint).
MAX_GATE_FILE_BYTES = 512 * 1024
MAX_SIGNER_LEN = 120

_GATE_NAME_RE = re.compile(r"^LIVE_GATE_\d{8}\.(md|json)$", re.IGNORECASE)
_CHECKLIST_RE = re.compile(r"^\s*[-*]\s*\[(?P<mark>[ xX])\]\s*(?P<item>\S.*)$")
_SIGNOFF_RE = re.compile(
    r"^\s*[-*]?\s*(?P<field>ceo_signoff|desk_lead_signoff)\s*[:=]\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
_CONFIG_HASH_RE = re.compile(
    r"^\s*[-*]?\s*config_hash\s*[:=]\s*(?P<value>.+)$", re.IGNORECASE
)
_FIELD_RE = r'{name}\s*[:=]\s*(?:"(?P<quoted>[^"]*)"|(?P<bare>[^",;]+))'
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

_PLACEHOLDER_TOKENS = (
    "TBD",
    "TODO",
    "PENDING",
    "PENDIENTE",
    "XXX",
    "N/A",
    "NONE",
    "NULL",
    "FIRMA AQUI",
    "SIGN HERE",
    "NOMBRE",
    "FULANO",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return _CONTROL_CHARS_RE.sub("", str(value)).strip()


def _is_placeholder(signer: str) -> bool:
    if len(signer) < 3:
        return True
    if "<" in signer or ">" in signer:
        return True
    if not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", signer):
        return True
    upper = signer.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _valid_iso_timestamp(raw: str) -> bool:
    candidate = raw.strip()
    if not candidate:
        return False
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _resolve_gate_file() -> Tuple[Optional[Path], List[str]]:
    """Locate the gate artifact without ever raising."""
    reasons: List[str] = []
    explicit = os.getenv(LIVE_GATE_PATH_ENV, "").strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = _repo_root() / path
        if not path.is_file():
            return None, ["gate_file_missing"]
        if TEMPLATE_MARKER in path.name.upper():
            return None, ["gate_file_is_template"]
        return path, reasons

    configured_dir = os.getenv(LIVE_GATE_DIR_ENV, "").strip() or DEFAULT_GATE_DIR
    gate_dir = Path(configured_dir)
    if not gate_dir.is_absolute():
        gate_dir = _repo_root() / gate_dir
    if not gate_dir.is_dir():
        return None, ["gate_file_missing"]

    candidates = [
        entry
        for entry in gate_dir.iterdir()
        if entry.is_file()
        and _GATE_NAME_RE.match(entry.name)
        and TEMPLATE_MARKER not in entry.name.upper()
    ]
    if not candidates:
        return None, ["gate_file_missing"]
    # Filenames are date-stamped, so lexicographic max is the most recent gate.
    return max(candidates, key=lambda entry: entry.name.upper()), reasons


def _read_gate_text(path: Path) -> Tuple[Optional[str], List[str]]:
    try:
        size = path.stat().st_size
    except OSError:
        return None, ["gate_file_unreadable"]
    if size > MAX_GATE_FILE_BYTES:
        return None, ["gate_file_too_large"]
    try:
        mode = path.stat().st_mode
    except OSError:
        return None, ["gate_file_unreadable"]
    if mode & 0o002:
        # World-writable means anyone on the host could forge a signature.
        return None, ["gate_file_insecure_permissions"]
    try:
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeDecodeError):
        return None, ["gate_file_unreadable"]


def _parse_signoff_blob(rest: str) -> Dict[str, str]:
    signoff: Dict[str, str] = {}
    for name in ("signer", "timestamp"):
        match = re.search(_FIELD_RE.format(name=name), rest, re.IGNORECASE)
        if match:
            signoff[name] = _clean(match.group("quoted") or match.group("bare"))
    return signoff


def _parse_markdown(text: str) -> Dict[str, Any]:
    checklist: List[bool] = []
    signoffs: Dict[str, Dict[str, str]] = {}
    config_hash = ""

    for line in text.splitlines():
        checklist_match = _CHECKLIST_RE.match(line)
        if checklist_match:
            checklist.append(checklist_match.group("mark").lower() == "x")
            continue
        signoff_match = _SIGNOFF_RE.match(line)
        if signoff_match:
            field = signoff_match.group("field").lower()
            signoffs[field] = _parse_signoff_blob(signoff_match.group("rest"))
            continue
        if not config_hash:
            hash_match = _CONFIG_HASH_RE.match(line)
            if hash_match:
                config_hash = _clean(hash_match.group("value")).strip("`\"'")

    return {"checklist": checklist, "signoffs": signoffs, "config_hash": config_hash}


def _parse_json(text: str) -> Dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("gate artifact must be a JSON object")

    raw_checklist = payload.get("checklist", [])
    checklist: List[bool] = []
    if isinstance(raw_checklist, dict):
        checklist = [bool(value) for value in raw_checklist.values()]
    elif isinstance(raw_checklist, list):
        for entry in raw_checklist:
            if isinstance(entry, dict):
                done = entry.get("done", entry.get("checked", entry.get("complete")))
                checklist.append(bool(done))
            else:
                checklist.append(bool(entry))

    signoffs: Dict[str, Dict[str, str]] = {}
    for field in _ROLE_FIELDS.values():
        raw = payload.get(field)
        if isinstance(raw, dict):
            signoffs[field] = {
                "signer": _clean(raw.get("signer")),
                "timestamp": _clean(raw.get("timestamp")),
            }
        elif raw:
            # A bare value cannot carry signer + timestamp: keep it invalid.
            signoffs[field] = {"signer": _clean(raw), "timestamp": ""}

    return {
        "checklist": checklist,
        "signoffs": signoffs,
        "config_hash": _clean(payload.get("config_hash")),
    }


def _evaluate_signoffs(
    signoffs: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[str]]:
    signers: List[Dict[str, str]] = []
    reasons: List[str] = []

    for role in REQUIRED_ROLES:
        raw = signoffs.get(_ROLE_FIELDS[role]) or {}
        signer = _clean(raw.get("signer"))[:MAX_SIGNER_LEN]
        timestamp = _clean(raw.get("timestamp"))
        if not signer and not timestamp:
            reasons.append(f"missing_signature:{role}")
            continue
        if _is_placeholder(signer):
            reasons.append(f"placeholder_signer:{role}")
            continue
        if not timestamp:
            reasons.append(f"missing_timestamp:{role}")
            continue
        if not _valid_iso_timestamp(timestamp):
            reasons.append(f"invalid_timestamp:{role}")
            continue
        signers.append({"role": role, "signer": signer, "timestamp": timestamp})

    return signers, reasons


def _empty_status(reasons: List[str]) -> Dict[str, Any]:
    return {
        "signed": False,
        "signers": [],
        "checklist_complete": False,
        "checklist_done": 0,
        "checklist_total": 0,
        "gate_file": None,
        "config_hash": None,
        "reasons": reasons,
    }


def get_live_gate_status() -> Dict[str, Any]:
    """Read-only, fail-closed view of the live gate artifact.

    Returns a JSON-serialisable dict. ``gate_file`` is the file *name* only:
    absolute paths are deployment detail and never leave the process.
    """
    try:
        path, reasons = _resolve_gate_file()
        if path is None:
            return _empty_status(reasons or ["gate_file_missing"])

        text, read_reasons = _read_gate_text(path)
        if text is None:
            status = _empty_status(read_reasons or ["gate_file_unreadable"])
            status["gate_file"] = path.name
            return status

        try:
            parsed = (
                _parse_json(text)
                if path.suffix.lower() == ".json"
                else _parse_markdown(text)
            )
        except Exception:
            status = _empty_status(["gate_file_unparsable"])
            status["gate_file"] = path.name
            return status

        checklist: List[bool] = parsed["checklist"]
        checklist_total = len(checklist)
        checklist_done = sum(1 for done in checklist if done)
        checklist_complete = checklist_total > 0 and checklist_done == checklist_total

        signers, reasons = _evaluate_signoffs(parsed["signoffs"])
        if checklist_total == 0:
            reasons.append("checklist_empty")
        elif not checklist_complete:
            reasons.append("checklist_incomplete")

        config_hash = _clean(parsed.get("config_hash"))[:MAX_SIGNER_LEN] or None
        if not config_hash:
            # Non-blocking per ADR-007, but the auditor must see it.
            reasons.append("config_hash_missing")

        # "Signed" means the whole artifact is valid: two signatures AND every
        # checklist item ticked. A half-done checklist is not a signed gate.
        signed = len(signers) == len(REQUIRED_ROLES) and checklist_complete

        return {
            "signed": signed,
            "signers": signers,
            "checklist_complete": checklist_complete,
            "checklist_done": checklist_done,
            "checklist_total": checklist_total,
            "gate_file": path.name,
            "config_hash": config_hash,
            "reasons": reasons,
        }
    except Exception:
        # Never let a gate read error propagate as "allowed".
        return _empty_status(["gate_status_error"])


def gate_allows_real() -> bool:
    """True only when both signatures are valid and the checklist is complete."""
    status = get_live_gate_status()
    return bool(status["signed"]) and bool(status["checklist_complete"])
