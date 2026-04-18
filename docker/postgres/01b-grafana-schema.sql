-- Script 1b: Dar permisos de schema a grafana (ejecutar dentro de BD grafana)
\connect grafana
GRANT ALL ON SCHEMA public TO grafana;
GRANT CREATE ON SCHEMA public TO grafana;
ALTER DATABASE grafana OWNER TO grafana;
