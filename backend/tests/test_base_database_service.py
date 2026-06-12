"""
Regression tests for BaseDatabaseService connection lifecycle (audit B-2).

Historically get_connection() returned a raw connection and callers used
``with conn:`` which only manages the transaction, never closing the
connection. get_connection is now a context manager that closes the
connection in a finally block while preserving the old commit-on-success /
rollback-on-exception transaction semantics.
"""

import sqlite3

import pytest

from app.services.base_database_service import BaseDatabaseService


@pytest.fixture
def service(tmp_path):
    """A BaseDatabaseService on a fresh temporary database."""
    return BaseDatabaseService(db_path=str(tmp_path / "base.db"))


@pytest.fixture
def service_with_table(service):
    """Service with a simple table to exercise reads/writes."""
    with service.get_connection() as conn:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    return service


class TestConnectionLifecycle:
    def test_connection_is_closed_after_with_block(self, service):
        with service.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)

        # B-2: the connection must actually be closed once the block exits
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_connection_is_closed_after_exception(self, service):
        with pytest.raises(ValueError):
            with service.get_connection() as conn:
                raise ValueError("boom")

        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_commit_on_success_semantics_preserved(self, service_with_table):
        # Callers previously relied on ``with conn:`` committing for them;
        # the context manager must keep doing that.
        with service_with_table.get_connection() as conn:
            conn.execute("INSERT INTO items (name) VALUES (?)", ("kept",))
            # no explicit conn.commit()

        with service_with_table.get_connection() as conn:
            rows = conn.execute("SELECT name FROM items").fetchall()
        assert [row[0] for row in rows] == ["kept"]

    def test_rollback_on_exception_semantics_preserved(self, service_with_table):
        with pytest.raises(RuntimeError):
            with service_with_table.get_connection() as conn:
                conn.execute("INSERT INTO items (name) VALUES (?)", ("dropped",))
                raise RuntimeError("abort transaction")

        with service_with_table.get_connection() as conn:
            rows = conn.execute("SELECT name FROM items").fetchall()
        assert rows == []


class TestHelpersStillWork:
    """The execute_* helpers must keep their existing return semantics."""

    def test_execute_insert_and_query(self, service_with_table):
        row_id = service_with_table.execute_insert(
            "INSERT INTO items (name) VALUES (?)", ("a",)
        )
        assert row_id == 1

        row = service_with_table.execute_query(
            "SELECT name FROM items WHERE id = ?", (1,), fetch_one=True
        )
        assert row["name"] == "a"

        rows = service_with_table.execute_query(
            "SELECT name FROM items", fetch_all=True
        )
        assert len(rows) == 1

    def test_execute_update_delete(self, service_with_table):
        service_with_table.execute_insert("INSERT INTO items (name) VALUES (?)", ("a",))
        assert (
            service_with_table.execute_update_delete(
                "UPDATE items SET name = ? WHERE id = ?", ("b", 1)
            )
            is True
        )
        assert (
            service_with_table.execute_update_delete(
                "DELETE FROM items WHERE id = ?", (999,)
            )
            is False
        )

    def test_error_swallowing_unchanged(self, service_with_table):
        # Errors must still be swallowed into None/False (audit decision:
        # do not change this in the B-2 pass).
        assert service_with_table.execute_query("SELECT * FROM no_such_table") is None
        assert (
            service_with_table.execute_insert("INSERT INTO nope VALUES (1)", ()) is None
        )
        assert service_with_table.execute_update_delete("DELETE FROM nope", ()) is False
