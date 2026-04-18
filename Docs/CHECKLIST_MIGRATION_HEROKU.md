# Checklist – Migración Heroku a Neon + Upstash

Usar este checklist al ejecutar el [Plan de migración](./MIGRATION_HEROKU_FREE_TIER.md).

---

## Fase 0 – Prerrequisitos

- [ ] Cuenta Neon creada
- [ ] Cuenta Upstash creada
- [ ] Heroku CLI instalado y `heroku login` hecho
- [ ] Nombre de la app Heroku anotado: `HEROKU_APP=grid-bot-ia` (o el que corresponda)

---

## Fase 1 – Recursos externos

- [ ] Neon: proyecto creado, connection string (Pooled o Direct) copiado
- [ ] Neon: URL guardada en variable local (no en repo): `NEON_DATABASE_URL`
- [ ] Upstash: base Redis creada, URL copiada
- [ ] Upstash: URL guardada en variable local: `UPSTASH_REDIS_URL`
- [ ] Ambas URLs verificadas (postgresql:// y rediss://)

---

## Fase 2 – Backup Heroku

- [ ] `heroku pg:backups:capture -a $HEROKU_APP` ejecutado
- [ ] `heroku pg:backups:download -a $HEROKU_APP` ejecutado (opcional si no migras datos)
- [ ] `latest.dump` guardado en lugar seguro (opcional)

---

## Fase 3 – Restaurar en Neon (si aplica)

- [ ] `pg_restore -d "$NEON_DATABASE_URL" --no-owner --no-acl -v latest.dump` ejecutado
- [ ] Tablas/datos comprobados en Neon
- [ ] Opcional: `alembic upgrade head` contra Neon

---

## Fase 4 – Configurar Heroku

- [ ] `heroku config:set DATABASE_URL="$NEON_DATABASE_URL" -a $HEROKU_APP`
- [ ] `heroku config:set REDIS_URL="$UPSTASH_REDIS_URL" -a $HEROKU_APP`
- [ ] `heroku config:set CELERY_BROKER_URL="$UPSTASH_REDIS_URL" -a $HEROKU_APP`
- [ ] `heroku config:set CELERY_RESULT_BACKEND="$UPSTASH_REDIS_URL" -a $HEROKU_APP`
- [ ] `heroku config -a $HEROKU_APP` revisado (DATABASE_URL y REDIS_URL son las nuevas)

---

## Fase 5 – Verificación

- [ ] `heroku run alembic upgrade head -a $HEROKU_APP` (si no restauraste dump)
- [ ] `heroku restart -a $HEROKU_APP`
- [ ] `heroku logs --tail -a $HEROKU_APP` sin errores de DB/Redis
- [ ] `curl https://$HEROKU_APP.herokuapp.com/health` responde OK
- [ ] Celery/workers (si aplica): tareas se encolan y ejecutan

---

## Fase 6 – Retirar add-ons (solo cuando todo esté estable)

- [ ] `heroku addons:destroy heroku-postgresql:essential-0 -a $HEROKU_APP`
- [ ] `heroku addons:destroy heroku-redis:premium-0 -a $HEROKU_APP`
- [ ] Facturación Heroku comprobada (add-ons ya no aparecen)

---

## Notas

- No commitear `NEON_DATABASE_URL` ni `UPSTASH_REDIS_URL`.
- Si algo falla después de Fase 4, hacer rollback con las URLs anteriores antes de destruir add-ons.
