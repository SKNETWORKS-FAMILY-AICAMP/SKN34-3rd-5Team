import json
import re
from collections import Counter

from django.apps import apps
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, OperationalError, connections, transaction
from sqlglot import exp, parse_one
from sqlglot.tokens import TokenType, Tokenizer


class BaseballQueryError(Exception):
    """LLM 호출자에게 노출해도 되는 야구 조회 오류."""


class BaseballQueryConfigurationError(BaseballQueryError):
    pass


class BaseballQueryTimeoutError(BaseballQueryError):
    pass


class BaseballQueryLockTimeoutError(BaseballQueryError):
    pass


class BaseballQueryExecutionError(BaseballQueryError):
    pass


class BaseballQueryAccessDeniedError(BaseballQueryError):
    pass


class BaseballQueryResultTooLargeError(BaseballQueryError):
    pass


class BaseballQueryRepository:
    connection_alias = "baseball_readonly"

    @staticmethod
    def models():
        return tuple(apps.get_app_config("baseball").get_models())

    def get_schema(self) -> dict:
        tables = []
        for model in self.models():
            columns = []
            for field in model._meta.fields:
                column = {
                    "name": field.column,
                    "type": field.db_type(connections["default"]),
                    "nullable": field.null,
                    "primary_key": field.primary_key,
                }
                if field.is_relation:
                    column["references"] = {
                        "table": field.related_model._meta.db_table,
                        "column": field.target_field.column,
                    }
                columns.append(column)
            table = model._meta.db_table
            tables.append({"name": table, "quoted_name": f'"{table}"', "columns": columns})
        return {"schema": "public", "tables": tables}

    def execute_readonly(self, sql: str, params: dict, max_rows: int) -> dict:
        config = settings.DATABASES[self.connection_alias]
        if not config.get("USER") or not config.get("PASSWORD"):
            raise BaseballQueryConfigurationError(
                "야구 조회 전용 DB 계정이 설정되지 않았습니다."
            )

        # 이미 검증한 AST를 PostgreSQL SQL로 다시 출력해 주석과 끝 세미콜론을 제거한다.
        statement = parse_one(sql, read="postgres")
        select_sql = statement.sql(dialect="postgres")
        placeholders = Counter(node.this.name for node in statement.find_all(exp.Placeholder))
        if placeholders:
            select_sql = self._escape_driver_percents(select_sql, placeholders)
        query = f'SELECT * FROM ({select_sql}) AS "baseball_query" LIMIT {max_rows + 1}'
        try:
            with transaction.atomic(using=self.connection_alias):
                with connections[self.connection_alias].cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL search_path = pg_catalog, public")
                    cursor.execute(
                        "SET LOCAL statement_timeout = %s",
                        [settings.BASEBALL_QUERY_TIMEOUT_MS],
                    )
                    cursor.execute(
                        "SET LOCAL lock_timeout = %s",
                        [settings.BASEBALL_QUERY_LOCK_TIMEOUT_MS],
                    )
                    if placeholders:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    columns = [column.name for column in cursor.description]
                    rows = cursor.fetchall()
        except OperationalError as exc:
            if getattr(exc.__cause__, "sqlstate", None) == "57014":
                raise BaseballQueryTimeoutError("야구 조회 시간이 제한을 초과했습니다.") from None
            if getattr(exc.__cause__, "sqlstate", None) == "55P03":
                raise BaseballQueryLockTimeoutError("야구 조회의 잠금 대기 시간이 제한을 초과했습니다.") from None
            if getattr(exc.__cause__, "sqlstate", None) == "42501":
                raise BaseballQueryAccessDeniedError("야구 조회 권한이 없습니다.") from None
            raise BaseballQueryExecutionError("야구 조회를 실행하지 못했습니다.") from None
        except DatabaseError as exc:
            if getattr(exc.__cause__, "sqlstate", None) == "55P03":
                raise BaseballQueryLockTimeoutError("야구 조회의 잠금 대기 시간이 제한을 초과했습니다.") from None
            if getattr(exc.__cause__, "sqlstate", None) == "42501":
                raise BaseballQueryAccessDeniedError("야구 조회 권한이 없습니다.") from None
            raise BaseballQueryExecutionError("야구 조회를 실행하지 못했습니다.") from None

        truncated = len(rows) > max_rows
        normalized_rows = []
        empty_result = {"columns": columns, "rows": [], "truncated": truncated}
        if len(json.dumps(empty_result, ensure_ascii=False).encode()) > settings.BASEBALL_QUERY_MAX_RESPONSE_BYTES:
            raise BaseballQueryResultTooLargeError("조회 결과 컬럼이 응답 크기 제한을 초과했습니다.")
        for row in rows[:max_rows]:
            normalized = json.loads(json.dumps(row, cls=DjangoJSONEncoder))
            candidate = {
                "columns": columns,
                "rows": [*normalized_rows, normalized],
                "truncated": truncated,
            }
            if len(json.dumps(candidate, ensure_ascii=False).encode()) > settings.BASEBALL_QUERY_MAX_RESPONSE_BYTES:
                if not normalized_rows:
                    raise BaseballQueryResultTooLargeError(
                        "조회 결과의 단일 행이 응답 크기 제한을 초과했습니다."
                    )
                truncated = True
                break
            normalized_rows.append(normalized)
        return {"columns": columns, "rows": normalized_rows, "truncated": truncated}

    @staticmethod
    def _escape_driver_percents(sql: str, placeholders: Counter) -> str:
        # AST placeholder 수와 SQL tokenizer 위치가 일치한 span만 보존한다.
        # params를 넘기는 psycopg 호출에서는 그 밖의 %를 %%로 보내야 한다.
        tokens = {token.start: token for token in Tokenizer(dialect="postgres").tokenize(sql)}
        spans = []
        names = []
        for match in re.finditer(r"%\(([A-Za-z_][A-Za-z0-9_]*)\)s", sql):
            token = tokens.get(match.start())
            if token and token.token_type is TokenType.MOD:
                spans.append(match.span())
                names.append(match.group(1))
        if Counter(names) != placeholders:
            raise BaseballQueryExecutionError("SQL 파라미터를 처리하지 못했습니다.")

        parts = []
        cursor = 0
        for start, end in spans:
            parts.append(sql[cursor:start].replace("%", "%%"))
            parts.append(sql[start:end])
            cursor = end
        parts.append(sql[cursor:].replace("%", "%%"))
        return "".join(parts)
