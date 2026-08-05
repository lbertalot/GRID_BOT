# Paper window L0 — config freeze

Fuente de política: monorepo `Docs/squad/desk-policy-l0.md` §2.4.

## Archivos
- `grid_config_paper_l0.json` — candidato a freeze (mid/min/max/qty en `null` hasta congelar).
- `scripts/freeze_paper_l0_config.py` — fija el mid, escribe rango ±5% y `config_hash`.
- `grid_config_paper_l0.hash` — aparece tras `--write`.

## Cómo congelar (antes de arrancar la ventana)
```bash
# 1. Obtener mid spot ETHUSDT (feed del bot o ticker paper)
# 2. Dry-run
python3.11 scripts/freeze_paper_l0_config.py --mid <PRECIO>
# 3. Persistir
python3.11 scripts/freeze_paper_l0_config.py --mid <PRECIO> --write
# 4. Apuntar el bot a esta config y registrar el hash en el ledger S10
```

## Parámetros fijos (no negociables en la ventana)
| Parámetro | Valor |
|-----------|-------|
| Símbolo | ETHUSDT solo |
| Desplegado | USD 200 |
| Niveles | 10 × USD 20 |
| Spacing | 100 bps |
| Rango | ±5% |
| Modo | PAPER (`force_real_mode=false`) |

## Rechazos
- Spacing < 40 bps
- Notional/nivel < USD 15
- Editar la config a mitad de ventana (rompe `config_is_frozen()` del ledger S10)

**Paper-only. No habilita live.**
