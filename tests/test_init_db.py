"""Unit tests for app.db.init_db — no real Postgres.

Paper-first · mocks asyncpg / SQLAlchemy · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import importlib
import runpy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.db.init_db as init_db_mod


# ── constants ────────────────────────────────────────────────────────────────


def test_create_tables_sql_marks_alembic_as_source_of_truth():
    assert "Alembic" in init_db_mod.CREATE_TABLES_SQL


def test_insert_initial_data_sql_contains_seed_keys():
    sql = init_db_mod.INSERT_INITIAL_DATA_SQL
    assert "grid_config" in sql
    assert "asset_limits" in sql
    assert "system_config" in sql
    assert "performance_metrics" in sql
    assert "BTCUSDT" in sql
    assert "max_daily_loss" in sql


# ── DATABASE_URL rewrite (import-time) ───────────────────────────────────────


def test_database_url_rewrites_postgres_scheme_on_reload(monkeypatch):
    """postgres:// → postgresql:// happens at module import time."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://griduser:gridpass@db:5432/gridbot",
    )
    reloaded = importlib.reload(init_db_mod)
    try:
        assert reloaded.DATABASE_URL.startswith("postgresql://")
        assert not reloaded.DATABASE_URL.startswith("postgres://")
        assert "griduser:gridpass@db:5432/gridbot" in reloaded.DATABASE_URL
    finally:
        # Restore default / ambient URL for sibling tests
        monkeypatch.delenv("DATABASE_URL", raising=False)
        importlib.reload(init_db_mod)


def test_database_url_keeps_postgresql_scheme_on_reload(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@localhost:5432/gridbot",
    )
    reloaded = importlib.reload(init_db_mod)
    try:
        assert reloaded.DATABASE_URL == "postgresql://u:p@localhost:5432/gridbot"
    finally:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        importlib.reload(init_db_mod)


# ── init_database (async) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_database_success():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"table_name": "grid_config"},
            {"table_name": "trades"},
        ]
    )
    conn.close = AsyncMock()

    with patch.object(init_db_mod.asyncpg, "connect", new_callable=AsyncMock) as connect:
        connect.return_value = conn
        await init_db_mod.init_database()

    connect.assert_awaited_once_with(init_db_mod.DATABASE_URL)
    conn.execute.assert_awaited_once_with(init_db_mod.INSERT_INITIAL_DATA_SQL)
    conn.fetch.assert_awaited_once()
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_database_raises_and_logs_on_connect_error():
    with patch.object(
        init_db_mod.asyncpg,
        "connect",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await init_db_mod.init_database()


@pytest.mark.asyncio
async def test_init_database_raises_when_execute_fails():
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=OSError("insert failed"))
    conn.close = AsyncMock()

    with patch.object(init_db_mod.asyncpg, "connect", new_callable=AsyncMock) as connect:
        connect.return_value = conn
        with pytest.raises(OSError, match="insert failed"):
            await init_db_mod.init_database()

    conn.close.assert_not_awaited()


# ── init_db (sync) ───────────────────────────────────────────────────────────


def test_init_db_success():
    conn = MagicMock()
    engine = MagicMock()
    # context managers: connect() and begin()
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    engine.begin.return_value.__enter__.return_value = conn
    engine.begin.return_value.__exit__.return_value = False

    with patch.object(init_db_mod, "create_engine", return_value=engine) as create_eng:
        assert init_db_mod.init_db() is True

    create_eng.assert_called_once_with(init_db_mod.DATABASE_URL)
    assert conn.execute.call_count == 2
    first_sql = str(conn.execute.call_args_list[0].args[0])
    second_sql = str(conn.execute.call_args_list[1].args[0])
    assert "SELECT 1" in first_sql
    assert "CREATE TABLE IF NOT EXISTS trades" in second_sql


def test_init_db_returns_false_on_error():
    with patch.object(
        init_db_mod,
        "create_engine",
        side_effect=RuntimeError("engine down"),
    ):
        assert init_db_mod.init_db() is False


# ── check_database_connection ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_database_connection_success():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()

    with patch.object(init_db_mod.asyncpg, "connect", new_callable=AsyncMock) as connect:
        connect.return_value = conn
        assert await init_db_mod.check_database_connection() is True

    connect.assert_awaited_once_with(init_db_mod.DATABASE_URL)
    conn.execute.assert_awaited_once_with("SELECT 1")
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_database_connection_failure():
    with patch.object(
        init_db_mod.asyncpg,
        "connect",
        new_callable=AsyncMock,
        side_effect=ConnectionError("refused"),
    ):
        assert await init_db_mod.check_database_connection() is False


# ── main() retry loop ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_main_connects_immediately_and_inits():
    with (
        patch.object(
            init_db_mod,
            "check_database_connection",
            new_callable=AsyncMock,
            return_value=True,
        ) as check,
        patch.object(
            init_db_mod,
            "init_database",
            new_callable=AsyncMock,
        ) as init,
        patch.object(init_db_mod.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        await init_db_mod.main()

    check.assert_awaited_once()
    init.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_retries_then_succeeds():
    # Fail twice, then succeed on 3rd attempt
    outcomes = [False, False, True]

    async def _check():
        return outcomes.pop(0)

    with (
        patch.object(
            init_db_mod,
            "check_database_connection",
            new_callable=AsyncMock,
            side_effect=_check,
        ) as check,
        patch.object(
            init_db_mod,
            "init_database",
            new_callable=AsyncMock,
        ) as init,
        patch.object(init_db_mod.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        await init_db_mod.main()

    assert check.await_count == 3
    assert sleep.await_count == 2
    sleep.assert_awaited_with(2)
    init.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_exhausts_retries_without_init():
    with (
        patch.object(
            init_db_mod,
            "check_database_connection",
            new_callable=AsyncMock,
            return_value=False,
        ) as check,
        patch.object(
            init_db_mod,
            "init_database",
            new_callable=AsyncMock,
        ) as init,
        patch.object(init_db_mod.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        await init_db_mod.main()

    assert check.await_count == 30
    assert sleep.await_count == 30
    init.assert_not_awaited()


# ── __main__ entry ───────────────────────────────────────────────────────────


def test_script_entry_invokes_asyncio_run():
    """Cubre `if __name__ == '__main__': asyncio.run(main())` sin DB real."""
    path = Path(init_db_mod.__file__).resolve()
    with patch("asyncio.run") as run_mock:
        runpy.run_path(str(path), run_name="__main__")
    run_mock.assert_called_once()
    # El argumento debe ser una coroutine de main()
    assert run_mock.call_args.args[0].__name__ == "main"
    run_mock.call_args.args[0].close()
