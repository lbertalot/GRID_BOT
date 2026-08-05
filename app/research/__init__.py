"""Research utilities: TQS mínimo (T+Q sin NLP) y Monte Carlo reproducible."""

from app.research.klines_utils import (
    closes_from_binance_klines,
    simple_returns_from_closes,
)
from app.research.monte_carlo_paths import (
    MonteCarloDrawdownStudy,
    max_drawdown_from_simple_returns,
    monte_carlo_max_drawdown_study,
)
from app.research.monte_carlo_shocks import (
    MonteCarloShockConfig,
    apply_multiplicative_return_shocks,
)
from app.research.promotion_gate import (
    AfterCostBacktestSnapshot,
    PromotionGateConfig,
    PromotionGateResult,
    evaluate_promotion_gate,
)
from app.research.tqs_minimal import TqsSnapshot, build_tqs_snapshot

__all__ = [
    "AfterCostBacktestSnapshot",
    "MonteCarloDrawdownStudy",
    "MonteCarloShockConfig",
    "PromotionGateConfig",
    "PromotionGateResult",
    "TqsSnapshot",
    "apply_multiplicative_return_shocks",
    "build_tqs_snapshot",
    "closes_from_binance_klines",
    "evaluate_promotion_gate",
    "max_drawdown_from_simple_returns",
    "monte_carlo_max_drawdown_study",
    "simple_returns_from_closes",
]
