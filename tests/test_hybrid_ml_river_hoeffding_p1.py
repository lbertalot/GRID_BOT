"""River 0.21+: HoeffdingTreeClassifier está en river.tree (HybridMLEngine lo usa)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile

import pytest


def _has_real_tensorflow() -> bool:
    """True solo si hay TF real (no stub de coverage / ModuleType sin loader)."""
    try:
        spec = importlib.util.find_spec("tensorflow")
    except ValueError:
        # Stub en sys.modules con __spec__ is None (p.ej. tests cov Z4).
        return False
    if spec is None:
        return False
    mod = sys.modules.get("tensorflow")
    if mod is not None and getattr(mod, "__gridbot_stub__", False):
        return False
    return True


_HAS_TENSORFLOW = _has_real_tensorflow()


def test_hoeffding_tree_classifier_lives_in_river_tree() -> None:
    """Regresión: river.ensemble ya no expone HoeffdingTreeClassifier."""
    from river import ensemble

    assert getattr(ensemble, "HoeffdingTreeClassifier", None) is None

    from river.tree import HoeffdingTreeClassifier

    model = HoeffdingTreeClassifier(grace_period=10, tau=0.1, leaf_prediction="mc")
    assert model is not None


@pytest.mark.skipif(
    not _HAS_TENSORFLOW,
    reason="TensorFlow viene en requirements-ml; CI con requirements.txt no importa HybridMLEngine",
)
def test_hybrid_ml_engine_create_river_hoeffding_tree() -> None:
    from river.tree import HoeffdingTreeClassifier

    from app.services.hybrid_ml_engine import HybridMLEngine

    with tempfile.TemporaryDirectory(prefix="gridbot_hybrid_test_") as tmp:
        engine = HybridMLEngine(models_dir=tmp)
        engine.river_config.model_type = "HoeffdingTree"
        model = engine._create_river_model()
        assert isinstance(model, HoeffdingTreeClassifier)
