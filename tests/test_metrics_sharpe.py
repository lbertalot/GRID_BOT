import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.metrics import compute_win_loss_and_sharpe


def test_compute_win_loss_and_sharpe():
    trades = [
        {"profit_loss": 10},
        {"profit_loss": -5},
        {"profit_loss": 3},
        {"profit_loss": 0},
    ]
    m = compute_win_loss_and_sharpe(trades)
    assert 0.0 <= m["win_ratio"] <= 1.0
    assert isinstance(m["sharpe"], float)
