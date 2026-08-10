"""TDD — simulacro A5 core (sin escribir Docs; assert PASS)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_simulacro_a5_core_pass():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "simulacro_ic_a5_paper.py"
    )
    spec = importlib.util.spec_from_file_location("simulacro_ic_a5_paper", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    evidence = mod._run()
    assert evidence["verdict"] == "PASS"
    assert evidence["steps"]["ic1_force_below_floor"]["pass"] is True
    assert evidence["steps"]["ic2_force_dd_flatten"]["pass"] is True
