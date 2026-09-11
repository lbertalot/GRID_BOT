"""TDD — veredicto cierre Fase 0. Read-only, no firma."""

from decimal import Decimal

from app.core.fase0_close_checklist import fase0_close_verdict


def test_fase0_iterate_if_a2_or_negative_pnl_or_few_cycles():
    out = fase0_close_verdict(
        a2_fail=True,
        pnl_net=Decimal("-0.9767"),
        closed_cycles=19,
    )
    assert out["verdict"] == "ITERATE"
    assert out["promote_paper"] is False
    assert out["promote_live"] is False
    assert out["firma_humana_pendiente"] is True
    assert out["human_signature"] is None
    assert "A2_rojo" in out["reasons"]
    assert "pnl_neto_negativo" in out["reasons"]
    assert "ciclos_insuficientes" in out["reasons"]


def test_fase0_never_promote_paper_even_if_green_inputs():
    out = fase0_close_verdict(
        a2_fail=False,
        pnl_net=Decimal("1.00"),
        closed_cycles=200,
        min_cycles=120,
    )
    assert out["promote_paper"] is False
    assert out["promote_live"] is False
    assert out["firma_humana_pendiente"] is True
    assert out["verdict"] == "REVIEW"
