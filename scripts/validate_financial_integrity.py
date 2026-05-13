#!/usr/bin/env python3
"""
GridBot v2.5 - Final Financial Integrity Gate
Verifies that the codebase is free of floating-point arithmetic in critical paths.
"""

import os
import sys
from pathlib import Path

# Paths that MUST NOT use float for financial calculations
CRITICAL_PATHS = [
    "app/core/risk_manager.py",
    "app/core/precision_validator.py",
    "app/core/safety_validator.py",
    "app/services/trade_executor.py",
    "app/services/balance_service.py"
]

def check_file_integrity(file_path: Path) -> list:
    errors = []
    if not file_path.exists():
        return [f"File {file_path} not found"]
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        clean_line = line.split('#')[0].strip() # Ignore comments
        
        # Check for direct use of 'float' as a type or conversion
        if 'float(' in clean_line or ': float' in clean_line or '-> float' in clean_line:
            # Contextual ignore: check current and previous line
            prev_line = lines[i-1] if i > 0 else ""
            full_context = (prev_line + line).lower()
            
            # Exceptions: metric exports or math functions where Decimal is not usable
            safe_patterns = [
                'prometheus', 'gauge', 'counter', 'histogram', 'summary', 
                'math.', 'atr', '.set(float(', '.labels(', '.set(', 'prometheus_client'
            ]
            
            if any(p in full_context for p in safe_patterns):
                continue
            
            errors.append(f"Line {i+1}: Unsafe 'float' usage detected: {clean_line}")
            
    return errors

def main():
    print("--- GridBot Financial Integrity Gate ---")
    all_errors = {}
    
    root = Path(__file__).parent.parent
    
    for rel_path in CRITICAL_PATHS:
        print(f"Checking {rel_path}...")
        errors = check_file_integrity(root / rel_path)
        if errors:
            all_errors[rel_path] = errors
            
    if all_errors:
        print("\n[FAIL] Financial Integrity issues found:")
        for path, errors in all_errors.items():
            print(f"\nIn {path}:")
            for err in errors:
                print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[PASS] All critical paths are clear of unsafe float usage.")
        sys.exit(0)

if __name__ == "__main__":
    main()
