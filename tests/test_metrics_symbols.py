import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.metrics import record_symbol_error


def test_record_symbol_error_does_not_crash():
    # No assertion on counters here; just ensure it doesn't raise
    record_symbol_error("TESTUSDT", "invalid_symbol")
