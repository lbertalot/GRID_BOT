#!/usr/bin/env python3
"""
Script simple para verificar métricas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prometheus_client import Counter, Gauge

# Crear métricas simples
test_counter = Counter('test_counter', 'Test counter')
test_gauge = Gauge('test_gauge', 'Test gauge')

# Incrementar métricas
test_counter.inc(10)
test_gauge.set(42.5)

print("✅ Métricas de prueba creadas:")
print(f"   Counter: {test_counter._value.get()}")
print(f"   Gauge: {test_gauge._value.get()}")

# Verificar que están en el registro
from prometheus_client import REGISTRY
print(f"\n📊 Métricas registradas: {len(REGISTRY._collector_to_names)}")

for metric in REGISTRY._collector_to_names:
    print(f"   - {metric}") 