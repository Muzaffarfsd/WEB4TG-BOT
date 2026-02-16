"""Shared database connection pool for all modules."""
import os
import logging
from typing import Optional
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("RAILWAY_DATABASE_URL") or os.environ.get("DATABASE_URL")

_connection_pool = None

MAX_CONN_RETRIES = 3


def get_connection_pool():
    """Get or create the shared connection pool."""
    global _connection_pool
    if _connection_pool is None and DATABASE_URL:
        try:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=15,
                dsn=DATABASE_URL
            )
            logger.info("Shared database connection pool created (1-15 connections)")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
    return _connection_pool


def close_pool():
    """Close all connections in the pool."""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_connection():
    """Context manager for getting a connection from the pool."""
    global _connection_pool
    conn = None
    pool_instance = None

    for attempt in range(1, MAX_CONN_RETRIES + 1):
        pool_instance = get_connection_pool()
        if not pool_instance:
            raise Exception("Database connection pool not available")

        try:
            conn = pool_instance.getconn()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"Pool getconn failed (attempt {attempt}/{MAX_CONN_RETRIES}): {e}")
            _connection_pool = None
            if attempt == MAX_CONN_RETRIES:
                raise
            continue

        try:
            test_cur = conn.cursor()
            test_cur.execute("SELECT 1")
            test_cur.close()
            break
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"Connection health check failed (attempt {attempt}/{MAX_CONN_RETRIES}): {e}")
            try:
                conn.close()
            except Exception:
                pass
            try:
                pool_instance.putconn(conn, close=True)
            except Exception:
                pass
            conn = None
            _connection_pool = None
            if attempt == MAX_CONN_RETRIES:
                raise Exception(f"Failed to get healthy database connection after {MAX_CONN_RETRIES} attempts")

    if conn is None:
        raise Exception("Failed to get database connection")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            current_pool = get_connection_pool()
            if current_pool:
                current_pool.putconn(conn)
        except Exception:
            pass


@contextmanager
def get_cursor(dict_cursor=False):
    """Context manager for getting a cursor with automatic connection handling."""
    with get_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
        finally:
            cursor.close()


def execute_query(query: str, params: Optional[tuple] = None, fetch: bool = False, dict_cursor: bool = False):
    """Execute a query and optionally fetch results."""
    with get_cursor(dict_cursor=dict_cursor) as cursor:
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        return None


def execute_one(query: str, params: Optional[tuple] = None, dict_cursor: bool = False):
    """Execute a query and fetch one result."""
    with get_cursor(dict_cursor=dict_cursor) as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def is_available() -> bool:
    """Check if database is available."""
    return DATABASE_URL is not None and get_connection_pool() is not None
