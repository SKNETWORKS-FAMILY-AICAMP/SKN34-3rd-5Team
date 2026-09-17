from contextlib import nullcontext
from datetime import date, datetime, time, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from baseball.query_repository import (
    BaseballQueryRepository,
    BaseballQueryResultTooLargeError,
)


class BaseballQueryRepositoryTest(SimpleTestCase):
    def _execute(
        self,
        rows,
        response_bytes=1048576,
        max_rows=2,
        columns=("value",),
        sql='SELECT value FROM "TEAM"',
        params=None,
    ):
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.description = [SimpleNamespace(name=name) for name in columns]
        cursor.fetchall.return_value = rows
        connection = Mock()
        connection.cursor.return_value = cursor
        config = {"baseball_readonly": {"USER": "reader", "PASSWORD": "secret"}}
        with (
            patch("baseball.query_repository.connections", {"baseball_readonly": connection}),
            patch("baseball.query_repository.transaction.atomic", return_value=nullcontext()),
            patch("baseball.query_repository.settings.DATABASES", config),
            patch("baseball.query_repository.settings.BASEBALL_QUERY_TIMEOUT_MS", 3000),
            patch("baseball.query_repository.settings.BASEBALL_QUERY_LOCK_TIMEOUT_MS", 1000),
            patch("baseball.query_repository.settings.BASEBALL_QUERY_MAX_RESPONSE_BYTES", response_bytes),
        ):
            result = BaseballQueryRepository().execute_readonly(
                sql, params or {}, max_rows
            )
        return result, cursor

    def test_result_is_limited_and_json_safe(self):
        rows = [
            (date(2026, 9, 14),),
            (time(12, 30),),
            (datetime(2026, 9, 14, tzinfo=timezone.utc),),
        ]
        result, cursor = self._execute(rows)
        self.assertEqual(result["rows"], [["2026-09-14"], ["12:30:00"]])
        self.assertTrue(result["truncated"])
        self.assertEqual(cursor.execute.call_args_list[0].args[0], "SET TRANSACTION READ ONLY")
        self.assertIn("LIMIT 3", cursor.execute.call_args_list[-1].args[0])

    def test_decimal_keeps_precision_and_duplicate_column_names_survive(self):
        result, _ = self._execute(
            [(Decimal("1.2300"), Decimal("2.3400"))],
            max_rows=2,
            columns=("value", "value"),
        )
        self.assertEqual(result["columns"], ["value", "value"])
        self.assertEqual(result["rows"], [["1.2300", "2.3400"]])

    def test_response_size_truncates_by_row_and_rejects_oversized_first_row(self):
        result, _ = self._execute([("a" * 20,), ("b" * 200,)], response_bytes=100)
        self.assertEqual(len(result["rows"]), 1)
        self.assertTrue(result["truncated"])
        with self.assertRaises(BaseballQueryResultTooLargeError):
            self._execute([("x" * 500,)], response_bytes=100)

    def test_response_size_rejects_oversized_columns_with_no_rows(self):
        with self.assertRaises(BaseballQueryResultTooLargeError):
            self._execute([], response_bytes=100, columns=("x" * 500,))

    def test_percent_is_only_escaped_when_named_parameters_use_driver_binding(self):
        _, cursor = self._execute(
            [],
            sql='SELECT id % 2 FROM "TEAM" WHERE team_name_ko LIKE \'%홈%\'',
        )
        self.assertEqual(len(cursor.execute.call_args_list[-1].args), 1)
        self.assertIn("id % 2", cursor.execute.call_args_list[-1].args[0])

        _, cursor = self._execute(
            [],
            sql=(
                'SELECT \'%(literal)s\', id % 2 FROM "TEAM" '
                'WHERE team_name_ko LIKE \'%홈%\' AND id = %(team_id)s'
            ),
            params={"team_id": 1},
        )
        query, params = cursor.execute.call_args_list[-1].args
        self.assertIn("'%%(literal)s'", query)
        self.assertIn("id %% 2", query)
        self.assertIn("LIKE '%%홈%%'", query)
        self.assertIn("%(team_id)s", query)
        self.assertEqual(params, {"team_id": 1})
