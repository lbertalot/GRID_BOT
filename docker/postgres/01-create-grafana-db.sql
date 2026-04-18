-- Script 1: Crear BD y usuario de Grafana (se ejecuta conectado a 'postgres')
CREATE DATABASE grafana;
CREATE USER grafana WITH PASSWORD 'grafana_pass';
GRANT ALL PRIVILEGES ON DATABASE grafana TO grafana;
ALTER USER grafana CREATEDB;
