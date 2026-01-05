"""
Async wrapper for PyDAL operations.

Since PyDAL is synchronous and Quart is async, this module provides
utilities to run PyDAL operations in a thread pool executor to avoid
blocking the event loop.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import wraps
from typing import Any, Callable, TypeVar

from pydal import DAL

# Thread pool for database operations
# Pool size should match DB connection pool size
_db_executor: ThreadPoolExecutor | None = None

# Type variable for generic return types
T = TypeVar("T")


def get_executor(max_workers: int = 10) -> ThreadPoolExecutor:
    """
    Get or create the thread pool executor for database operations.

    Args:
        max_workers: Maximum number of worker threads

    Returns:
        ThreadPoolExecutor instance
    """
    global _db_executor
    if _db_executor is None:
        _db_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pydal_",
        )
    return _db_executor


def shutdown_executor() -> None:
    """Shutdown the thread pool executor."""
    global _db_executor
    if _db_executor is not None:
        _db_executor.shutdown(wait=True)
        _db_executor = None


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Run a synchronous function in the thread pool.

    This preserves context variables (like Flask's g object) by copying
    the context to the worker thread.

    Args:
        func: Synchronous function to run
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result of the function call

    Example:
        result = await run_sync(db_query_function, arg1, arg2)
    """
    loop = asyncio.get_event_loop()
    executor = get_executor()

    # Copy context to preserve Flask's g and other context variables
    ctx = copy_context()

    def run_with_context() -> T:
        return ctx.run(func, *args, **kwargs)

    return await loop.run_in_executor(executor, run_with_context)


def async_db_operation(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to convert a synchronous database function to async.

    The decorated function can be called with await and will execute
    in the thread pool without blocking the event loop.

    Example:
        @async_db_operation
        def get_user(user_id: int) -> dict:
            db = get_db()
            return db(db.users.id == user_id).select().first()

        # Later, in async code:
        user = await get_user(123)
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        return await run_sync(func, *args, **kwargs)

    return wrapper


class AsyncDAL:
    """
    Async wrapper around PyDAL operations.

    Provides async versions of common database operations.

    Example:
        async_db = AsyncDAL(db)

        # Query
        user = await async_db.select_first(
            db.auth_user,
            db.auth_user.email == "user@example.com"
        )

        # Insert
        user_id = await async_db.insert(db.auth_user, email="new@example.com", ...)

        # Update
        await async_db.update(db.auth_user, db.auth_user.id == 1, active=False)
    """

    __slots__ = ("_db",)

    def __init__(self, db: DAL) -> None:
        """
        Initialize async DAL wrapper.

        Args:
            db: PyDAL database instance
        """
        self._db = db

    @property
    def db(self) -> DAL:
        """Get underlying DAL instance."""
        return self._db

    async def select(
        self,
        table: Any,
        query: Any = None,
        *fields: Any,
        orderby: Any = None,
        limitby: tuple[int, int] | None = None,
        **kwargs: Any,
    ) -> list[Any]:
        """
        Async select query.

        Args:
            table: Table to select from
            query: Query condition
            *fields: Fields to select
            orderby: Order by clause
            limitby: Limit tuple (start, end)

        Returns:
            List of rows
        """

        def _select() -> list[Any]:
            if query is not None:
                q = self._db(query)
            else:
                q = self._db(table)

            return list(
                q.select(
                    *fields or table.ALL,
                    orderby=orderby,
                    limitby=limitby,
                    **kwargs,
                )
            )

        return await run_sync(_select)

    async def select_first(
        self,
        table: Any,
        query: Any,
        *fields: Any,
        **kwargs: Any,
    ) -> Any | None:
        """
        Async select first matching row.

        Args:
            table: Table to select from
            query: Query condition
            *fields: Fields to select

        Returns:
            First matching row or None
        """

        def _select_first() -> Any | None:
            return self._db(query).select(*fields or table.ALL, **kwargs).first()

        return await run_sync(_select_first)

    async def count(self, query: Any) -> int:
        """
        Async count query.

        Args:
            query: Query condition

        Returns:
            Count of matching rows
        """

        def _count() -> int:
            return self._db(query).count()

        return await run_sync(_count)

    async def insert(self, table: Any, **fields: Any) -> int:
        """
        Async insert operation.

        Args:
            table: Table to insert into
            **fields: Field values

        Returns:
            ID of inserted row
        """

        def _insert() -> int:
            row_id = table.insert(**fields)
            self._db.commit()
            return row_id

        return await run_sync(_insert)

    async def update(self, table: Any, query: Any, **fields: Any) -> int:
        """
        Async update operation.

        Args:
            table: Table to update
            query: Query condition
            **fields: Field values to update

        Returns:
            Number of updated rows
        """

        def _update() -> int:
            count = self._db(query).update(**fields)
            self._db.commit()
            return count

        return await run_sync(_update)

    async def delete(self, query: Any) -> int:
        """
        Async delete operation.

        Args:
            query: Query condition

        Returns:
            Number of deleted rows
        """

        def _delete() -> int:
            count = self._db(query).delete()
            self._db.commit()
            return count

        return await run_sync(_delete)

    async def commit(self) -> None:
        """Async commit transaction."""
        await run_sync(self._db.commit)

    async def rollback(self) -> None:
        """Async rollback transaction."""
        await run_sync(self._db.rollback)


# Context manager for async database operations
class AsyncDBContext:
    """
    Async context manager for database operations.

    Provides automatic commit/rollback on exit.

    Example:
        async with AsyncDBContext(db) as async_db:
            user_id = await async_db.insert(db.auth_user, ...)
            await async_db.insert(db.auth_user_roles, ...)
        # Automatically commits on success, rolls back on error
    """

    __slots__ = ("_async_db", "_committed")

    def __init__(self, db: DAL) -> None:
        self._async_db = AsyncDAL(db)
        self._committed = False

    async def __aenter__(self) -> AsyncDAL:
        return self._async_db

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is None:
            await self._async_db.commit()
            self._committed = True
        else:
            await self._async_db.rollback()
