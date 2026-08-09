"""Unit tests for the live gate dual signoff (ADR-007, slice S4).

Fail-closed by design: anything ambiguous about the gate artifact must keep the
system away from ``real_armed``. No network, no real secrets, no signed gates
committed to git.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.live_gate import (
    LIVE_GATE_DIR_ENV,
    LIVE_GATE_PATH_ENV,
    gate_allows_real,
    get_live_gate_status,
)
from app.core.trading_mode import compute_effective_mode, get_trading_mode_snapshot

CEO = "Leandro Bertalot"
DESK = "Desk Lead Paper"
TS_CEO = "2026-09-05T14:00:00-03:00"
TS_DESK = "2026-09-05T14:05:00-03:00"

CHECKLIST_ITEMS = [
    "Dashboard verde",
    "Risk engine con limites",
    "Mode clarity expuesto",
    "Tear sheet paper >= 3 semanas",
    "Secrets fuera de git",
]


def _md_gate(
    *,
    ceo: bool = True,
    desk: bool = True,
    done_items: int = len(CHECKLIST_ITEMS),
    config_hash: str = "sha256:0f1e2d3c4b5a",
) -> str:
    lines = ["# LIVE GATE 2026-09-05", "", f"- config_hash: {config_hash}", ""]
    lines.append("## Checklist")
    for idx, item in enumerate(CHECKLIST_ITEMS):
        mark = "x" if idx < done_items else " "
        lines.append(f"- [{mark}] {item}")
    lines += ["", "## Signoffs"]
    if ceo:
        lines.append(f'- ceo_signoff: signer="{CEO}" timestamp="{TS_CEO}"')
    if desk:
        lines.append(f'- desk_lead_signoff: signer="{DESK}" timestamp="{TS_DESK}"')
    return "\n".join(lines) + "\n"


def _json_gate(
    *,
    ceo: bool = True,
    desk: bool = True,
    done_items: int = len(CHECKLIST_ITEMS),
) -> str:
    payload = {
        "config_hash": "sha256:0f1e2d3c4b5a",
        "checklist": [
            {"item": item, "done": idx < done_items}
            for idx, item in enumerate(CHECKLIST_ITEMS)
        ],
    }
    if ceo:
        payload["ceo_signoff"] = {"signer": CEO, "timestamp": TS_CEO}
    if desk:
        payload["desk_lead_signoff"] = {"signer": DESK, "timestamp": TS_DESK}
    return json.dumps(payload, indent=2)


def _write_gate(tmp_path, content: str, name: str = "LIVE_GATE_20260905.md"):
    gate_dir = tmp_path / "gates"
    gate_dir.mkdir(exist_ok=True)
    path = gate_dir / name
    path.write_text(content, encoding="utf-8")
    return gate_dir, path


@pytest.fixture
def gate_env(monkeypatch, tmp_path):
    """Isolate gate discovery and mode flags from the developer environment."""
    gate_dir = tmp_path / "gates"
    gate_dir.mkdir(exist_ok=True)
    monkeypatch.delenv(LIVE_GATE_PATH_ENV, raising=False)
    monkeypatch.setenv(LIVE_GATE_DIR_ENV, str(gate_dir))
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    return gate_dir


def _arm_real_flags(monkeypatch):
    monkeypatch.setenv("FORCE_REAL_MODE", "true")
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")


# ── Gate artifact absence ─────────────────────────────────────────────────────


def test_missing_gate_file_is_not_signed(gate_env):
    status = get_live_gate_status()
    assert status["signed"] is False
    assert status["checklist_complete"] is False
    assert status["gate_file"] is None
    assert status["signers"] == []
    assert "gate_file_missing" in status["reasons"]
    assert gate_allows_real() is False


def test_forced_real_without_gate_is_real_blocked(gate_env, monkeypatch):
    _arm_real_flags(monkeypatch)
    snap = get_trading_mode_snapshot()
    assert snap["live_gate_signed"] is False
    assert snap["effective_mode"] == "real_blocked"


# ── Single signature is never enough ──────────────────────────────────────────


def test_only_ceo_signature_is_not_signed(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, _md_gate(desk=False))
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert [s["role"] for s in status["signers"]] == ["ceo"]
    assert "missing_signature:desk_lead" in status["reasons"]
    assert gate_allows_real() is False
    assert get_trading_mode_snapshot()["effective_mode"] == "real_blocked"


def test_only_desk_lead_signature_is_not_signed(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, _md_gate(ceo=False))
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert [s["role"] for s in status["signers"]] == ["desk_lead"]
    assert "missing_signature:ceo" in status["reasons"]
    assert gate_allows_real() is False


# ── Checklist must be complete ────────────────────────────────────────────────


def test_both_signatures_with_incomplete_checklist_is_not_signed(
    gate_env, monkeypatch, tmp_path
):
    _write_gate(tmp_path, _md_gate(done_items=len(CHECKLIST_ITEMS) - 1))
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert status["checklist_complete"] is False
    assert status["checklist_done"] == len(CHECKLIST_ITEMS) - 1
    assert status["checklist_total"] == len(CHECKLIST_ITEMS)
    assert "checklist_incomplete" in status["reasons"]
    assert gate_allows_real() is False
    assert get_trading_mode_snapshot()["effective_mode"] == "real_blocked"


def test_gate_without_checklist_items_is_not_signed(gate_env, monkeypatch, tmp_path):
    content = (
        "# LIVE GATE 2026-09-05\n\n"
        f'- ceo_signoff: signer="{CEO}" timestamp="{TS_CEO}"\n'
        f'- desk_lead_signoff: signer="{DESK}" timestamp="{TS_DESK}"\n'
    )
    _write_gate(tmp_path, content)
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "checklist_empty" in status["reasons"]
    assert gate_allows_real() is False


# ── Happy path: two signatures + full checklist ───────────────────────────────


@pytest.mark.parametrize("fmt", ["md", "json"])
def test_complete_gate_allows_real(gate_env, monkeypatch, tmp_path, fmt):
    if fmt == "md":
        _write_gate(tmp_path, _md_gate(), name="LIVE_GATE_20260905.md")
    else:
        _write_gate(tmp_path, _json_gate(), name="LIVE_GATE_20260905.json")
    _arm_real_flags(monkeypatch)

    status = get_live_gate_status()
    assert status["signed"] is True
    assert status["checklist_complete"] is True
    assert sorted(s["role"] for s in status["signers"]) == ["ceo", "desk_lead"]
    assert status["reasons"] == []
    assert gate_allows_real() is True

    snap = get_trading_mode_snapshot()
    assert snap["live_gate_signed"] is True
    assert snap["effective_mode"] == "real_armed"


def test_signed_gate_still_paper_when_flags_not_armed(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, _md_gate())
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    assert get_trading_mode_snapshot()["effective_mode"] == "paper"


def test_emergency_stop_overrides_signed_gate(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, _md_gate())
    _arm_real_flags(monkeypatch)
    monkeypatch.setenv("EMERGENCY_STOP", "true")
    assert gate_allows_real() is True
    assert get_trading_mode_snapshot()["effective_mode"] == "real_blocked"


# ── Fail-closed parsing ───────────────────────────────────────────────────────


def test_corrupt_json_gate_fails_closed(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, "{ not json at all ", name="LIVE_GATE_20260905.json")
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_unparsable" in status["reasons"]
    assert gate_allows_real() is False
    assert get_trading_mode_snapshot()["effective_mode"] == "real_blocked"


def test_binary_gate_file_fails_closed(gate_env, monkeypatch):
    path = gate_env / "LIVE_GATE_20260905.md"
    path.write_bytes(b"\xff\xfe\x00\x00binario no decodificable\x80")
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_unreadable" in status["reasons"]
    assert gate_allows_real() is False


def test_placeholder_signer_is_rejected(gate_env, monkeypatch, tmp_path):
    content = _md_gate().replace(f'signer="{CEO}"', 'signer="<NOMBRE CEO>"')
    _write_gate(tmp_path, content)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "placeholder_signer:ceo" in status["reasons"]


def test_invalid_timestamp_is_rejected(gate_env, monkeypatch, tmp_path):
    content = _md_gate().replace(f'timestamp="{TS_DESK}"', 'timestamp="ayer"')
    _write_gate(tmp_path, content)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "invalid_timestamp:desk_lead" in status["reasons"]


def test_oversized_gate_file_fails_closed(gate_env, monkeypatch):
    path = gate_env / "LIVE_GATE_20260905.md"
    path.write_text("x" * (600 * 1024), encoding="utf-8")
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_too_large" in status["reasons"]


def test_template_is_never_a_valid_gate(monkeypatch):
    """The committed template must never arm live, even if it is the only file."""
    monkeypatch.delenv(LIVE_GATE_PATH_ENV, raising=False)
    monkeypatch.delenv(LIVE_GATE_DIR_ENV, raising=False)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert status["gate_file"] is None
    assert gate_allows_real() is False


def test_explicit_template_path_is_rejected(monkeypatch):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template = os.path.join(repo_root, "Docs", "gates", "LIVE_GATE_TEMPLATE.md")
    assert os.path.isfile(template), "la plantilla auditable debe estar en el repo"
    monkeypatch.setenv(LIVE_GATE_PATH_ENV, template)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_is_template" in status["reasons"]
    assert gate_allows_real() is False


def test_newest_gate_file_wins(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, _md_gate(), name="LIVE_GATE_20260905.md")
    _write_gate(tmp_path, _md_gate(desk=False), name="LIVE_GATE_20260930.md")
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["gate_file"] == "LIVE_GATE_20260930.md"
    assert status["signed"] is False


# ── No sensitive data leaks ───────────────────────────────────────────────────


def test_status_does_not_leak_absolute_paths(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, _md_gate())
    status = get_live_gate_status()
    assert status["gate_file"] == "LIVE_GATE_20260905.md"
    assert str(tmp_path) not in json.dumps(status)


def test_snapshot_does_not_leak_secrets(gate_env, monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEY", "fake-api-key-for-tests")
    monkeypatch.setenv("BINANCE_API_SECRET", "fake-secret-for-tests")
    _write_gate(tmp_path, _md_gate())
    blob = json.dumps(get_trading_mode_snapshot())
    assert "fake-api-key-for-tests" not in blob
    assert "fake-secret-for-tests" not in blob


# ── compute_effective_mode backwards compatibility ────────────────────────────


def test_compute_effective_mode_gate_kwarg_defaults_to_unsigned():
    """Omitting the kwarg means "gate not verified", so never real_armed."""
    defaulted = compute_effective_mode(
        paper_trading=False,
        force_real_mode=True,
        trading_enabled=True,
        emergency_stop=False,
    )
    assert defaulted == "real_blocked"

    blocked = compute_effective_mode(
        paper_trading=False,
        force_real_mode=True,
        trading_enabled=True,
        emergency_stop=False,
        live_gate_signed=False,
    )
    assert blocked == "real_blocked"

    armed = compute_effective_mode(
        paper_trading=False,
        force_real_mode=True,
        trading_enabled=True,
        emergency_stop=False,
        live_gate_signed=True,
    )
    assert armed == "real_armed"


def test_force_real_over_paper_still_needs_gate():
    assert (
        compute_effective_mode(
            paper_trading=True,
            force_real_mode=True,
            trading_enabled=True,
            emergency_stop=False,
            live_gate_signed=False,
        )
        == "real_blocked"
    )


# ── Read-only, authenticated endpoint ─────────────────────────────────────────

FAKE_API_KEY = "fake-api-key-for-tests"


@pytest.fixture
def auth_headers(monkeypatch):
    monkeypatch.setenv("API_KEY", FAKE_API_KEY)
    return {"Authorization": f"Bearer {FAKE_API_KEY}"}


def test_live_status_endpoint_requires_auth(gate_env, auth_headers, client):
    """Gate detail (signer identities, pending controls) is not public recon."""
    assert client.get("/api/gates/live-status").status_code == 401
    assert (
        client.get(
            "/api/gates/live-status", headers={"Authorization": "Bearer wrong-key"}
        ).status_code
        == 401
    )
    assert client.get("/api/gates/live-status", headers=auth_headers).status_code == 200


def test_live_status_endpoint_contract(
    gate_env, monkeypatch, tmp_path, client, auth_headers
):
    _write_gate(tmp_path, _md_gate())
    resp = client.get("/api/gates/live-status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"timestamp", "gate"}
    gate = body["gate"]
    assert set(gate) == {
        "signed",
        "signers",
        "checklist_complete",
        "checklist_done",
        "checklist_total",
        "gate_file",
        "config_hash",
        "reasons",
    }
    assert gate["signed"] is True
    assert gate["gate_file"] == "LIVE_GATE_20260905.md"
    assert all(set(s) == {"role", "signer", "timestamp"} for s in gate["signers"])


def test_live_status_endpoint_payload_has_no_secrets(
    gate_env, monkeypatch, tmp_path, client, auth_headers
):
    monkeypatch.setenv("BINANCE_API_SECRET", "fake-secret-for-tests")
    monkeypatch.setenv("SECRET_KEY", "fake-secret-key-for-tests")
    _write_gate(tmp_path, _md_gate())

    raw = client.get("/api/gates/live-status", headers=auth_headers).text
    for leaked in (
        FAKE_API_KEY,
        "fake-secret-for-tests",
        "fake-secret-key-for-tests",
        str(tmp_path),
    ):
        assert leaked not in raw

    body = client.get("/api/gates/live-status", headers=auth_headers).json()

    def _keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from _keys(value)
        elif isinstance(node, list):
            for value in node:
                yield from _keys(value)

    forbidden = ("api_key", "apikey", "secret", "token", "password", "private")
    for key in _keys(body):
        assert not any(bad in key.lower() for bad in forbidden), key


def test_live_status_endpoint_is_read_only(gate_env, client, auth_headers):
    """There is no way to sign, approve or bypass the gate over HTTP."""
    assert (
        client.post("/api/gates/live-status", headers=auth_headers).status_code == 405
    )
    assert (
        client.put("/api/gates/live-status", headers=auth_headers).status_code == 405
    )


# ── COV-1.1: edge branches to ≥90% ────────────────────────────────────────────


def test_short_and_digit_only_signers_are_placeholders(gate_env, tmp_path):
    content = (
        "# LIVE GATE\n\n"
        "- [x] item\n"
        '- ceo_signoff: signer="AB" timestamp="2026-09-05T14:00:00Z"\n'
        '- desk_lead_signoff: signer="12345" timestamp="2026-09-05T14:05:00Z"\n'
    )
    _write_gate(tmp_path, content)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "placeholder_signer:ceo" in status["reasons"]
    assert "placeholder_signer:desk_lead" in status["reasons"]


def test_missing_timestamp_with_signer_is_rejected(gate_env, tmp_path):
    content = (
        "# LIVE GATE\n\n"
        "- [x] item\n"
        f'- ceo_signoff: signer="{CEO}" timestamp="{TS_CEO}"\n'
        f'- desk_lead_signoff: signer="{DESK}"\n'
    )
    _write_gate(tmp_path, content)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "missing_timestamp:desk_lead" in status["reasons"]


def test_iso_timestamp_with_z_suffix_accepted(gate_env, monkeypatch, tmp_path):
    content = (
        "# LIVE GATE\n\n"
        "- config_hash: sha256:abc\n"
        "- [x] Dashboard verde\n"
        '- ceo_signoff: signer="Leandro Bertalot" timestamp="2026-09-05T17:00:00Z"\n'
        '- desk_lead_signoff: signer="Desk Lead Paper" timestamp="2026-09-05T17:05:00z"\n'
    )
    _write_gate(tmp_path, content)
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is True
    assert gate_allows_real() is True


def test_explicit_relative_gate_path(monkeypatch, tmp_path):
    gate_dir = tmp_path / "Docs" / "gates"
    gate_dir.mkdir(parents=True)
    path = gate_dir / "LIVE_GATE_20260905.md"
    path.write_text(_md_gate(), encoding="utf-8")
    monkeypatch.setattr("app.core.live_gate._repo_root", lambda: tmp_path)
    monkeypatch.setenv(LIVE_GATE_PATH_ENV, "Docs/gates/LIVE_GATE_20260905.md")
    monkeypatch.delenv(LIVE_GATE_DIR_ENV, raising=False)
    status = get_live_gate_status()
    assert status["gate_file"] == path.name
    assert status["signed"] is True


def test_explicit_missing_gate_path(monkeypatch, tmp_path):
    missing = tmp_path / "nope" / "LIVE_GATE_20990101.md"
    monkeypatch.setenv(LIVE_GATE_PATH_ENV, str(missing))
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_missing" in status["reasons"]


def test_gate_dir_not_a_directory(monkeypatch, tmp_path):
    not_dir = tmp_path / "not_a_dir"
    not_dir.write_text("x", encoding="utf-8")
    monkeypatch.delenv(LIVE_GATE_PATH_ENV, raising=False)
    monkeypatch.setenv(LIVE_GATE_DIR_ENV, str(not_dir))
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_missing" in status["reasons"]


def test_world_writable_gate_rejected(gate_env, monkeypatch):
    path = gate_env / "LIVE_GATE_20260905.md"
    path.write_text(_md_gate(), encoding="utf-8")
    path.chmod(0o666)
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_insecure_permissions" in status["reasons"]
    assert gate_allows_real() is False


def test_json_non_object_fails_closed(gate_env, monkeypatch, tmp_path):
    _write_gate(tmp_path, "[1, 2, 3]", name="LIVE_GATE_20260905.json")
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_file_unparsable" in status["reasons"]


def test_json_checklist_dict_and_bare_signoff(gate_env, monkeypatch, tmp_path):
    payload = {
        "config_hash": "sha256:dict-check",
        "checklist": {"a": True, "b": True},
        "ceo_signoff": CEO,  # bare string → invalid (no timestamp)
        "desk_lead_signoff": {"signer": DESK, "timestamp": TS_DESK},
    }
    _write_gate(tmp_path, json.dumps(payload), name="LIVE_GATE_20260905.json")
    status = get_live_gate_status()
    assert status["checklist_total"] == 2
    assert status["signed"] is False
    assert any("ceo" in r for r in status["reasons"])


def test_json_checklist_bare_bool_entries(gate_env, monkeypatch, tmp_path):
    payload = {
        "config_hash": "sha256:bools",
        "checklist": [True, True, False],
        "ceo_signoff": {"signer": CEO, "timestamp": TS_CEO},
        "desk_lead_signoff": {"signer": DESK, "timestamp": TS_DESK},
    }
    _write_gate(tmp_path, json.dumps(payload), name="LIVE_GATE_20260905.json")
    status = get_live_gate_status()
    assert status["checklist_total"] == 3
    assert status["checklist_done"] == 2
    assert status["signed"] is False
    assert "checklist_incomplete" in status["reasons"]


def test_stat_oserror_fails_closed(gate_env, monkeypatch):
    """OSError while resolving/reading the gate must never arm live."""
    from pathlib import Path
    from unittest.mock import patch

    path = gate_env / "LIVE_GATE_20260905.md"
    path.write_text(_md_gate(), encoding="utf-8")
    monkeypatch.setenv(LIVE_GATE_PATH_ENV, str(path))

    with patch.object(Path, "stat", side_effect=OSError("simulated")):
        status = get_live_gate_status()
        assert status["signed"] is False
        assert status["reasons"]
        assert gate_allows_real() is False


def test_read_gate_size_stat_oserror(gate_env):
    from pathlib import Path
    from unittest.mock import patch

    from app.core.live_gate import _read_gate_text

    path = gate_env / "LIVE_GATE_20260905.md"
    path.write_text(_md_gate(), encoding="utf-8")
    with patch.object(Path, "stat", side_effect=OSError("size")):
        text, reasons = _read_gate_text(path)
    assert text is None
    assert "gate_file_unreadable" in reasons


def test_read_gate_mode_stat_oserror(gate_env):
    from pathlib import Path
    from unittest.mock import patch

    from app.core.live_gate import _read_gate_text

    path = gate_env / "LIVE_GATE_20260905.md"
    path.write_text(_md_gate(), encoding="utf-8")
    real = Path.stat
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(self, *args, **kwargs)
        raise OSError("mode unreadable")

    with patch.object(Path, "stat", flaky):
        text, reasons = _read_gate_text(path)
    assert text is None
    assert "gate_file_unreadable" in reasons


def test_outer_exception_fails_closed(monkeypatch):
    def boom():
        raise RuntimeError("unexpected")

    monkeypatch.setattr("app.core.live_gate._resolve_gate_file", boom)
    status = get_live_gate_status()
    assert status["signed"] is False
    assert "gate_status_error" in status["reasons"]
    assert gate_allows_real() is False


def test_valid_iso_timestamp_empty_and_bad(monkeypatch):
    from app.core.live_gate import _valid_iso_timestamp

    assert _valid_iso_timestamp("") is False
    assert _valid_iso_timestamp("   ") is False
    assert _valid_iso_timestamp("2026-09-05T14:00:00Z") is True
    assert _valid_iso_timestamp("not-a-date") is False


def test_config_hash_missing_reason_non_blocking(gate_env, monkeypatch, tmp_path):
    content = "\n".join(
        line for line in _md_gate().splitlines() if "config_hash" not in line.lower()
    )
    _write_gate(tmp_path, content + "\n")
    _arm_real_flags(monkeypatch)
    status = get_live_gate_status()
    assert status["signed"] is True  # hash missing is non-blocking
    assert "config_hash_missing" in status["reasons"]
    assert gate_allows_real() is True
