# Seguridad y Divulgación Responsable

Gracias por ayudar a mantener seguro GridBot.

## Reporte de vulnerabilidades
- Enviar a: `security@gridbot.com`.
- Incluye: descripción, pasos de reproducción, impacto y versión.
- Tiempo de respuesta objetivo: 72 horas.

## Manejo de secretos
- No subir `.env` ni credenciales.
- Usar GitHub Secrets para CI/CD.
- Rotar claves comprometidas inmediatamente.

## Buenas prácticas
- Variables sensibles via entorno (no en código).
- Principio de mínimo privilegio.
- TLS 1.3 y firma HMAC para llamadas al exchange.

## Alcance
- Repositorio público, API FastAPI, workers Celery.
- Quedan fuera sistemas externos de terceros (p.ej., Binance).
