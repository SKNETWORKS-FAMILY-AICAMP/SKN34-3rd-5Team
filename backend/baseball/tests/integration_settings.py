import os

from django.core.exceptions import ImproperlyConfigured

from baseball.limits import positive_int_env


def required(name):
    value = os.getenv(name, "")
    if not value:
        raise ImproperlyConfigured(f"{name} is required for disposable integration tests")
    return value


token = required("BASEBALL_INTEGRATION_TOKEN")
container = required("BASEBALL_INTEGRATION_CONTAINER")
db_host = required("DB_HOST")
db_port = required("DB_PORT")
db_name = required("DB_NAME")
db_user = required("DB_USER")
db_password = required("DB_PASSWORD")
reader_user = required("BASEBALL_DB_USER")
reader_password = required("BASEBALL_DB_PASSWORD")
if (
    required("BASEBALL_INTEGRATION_GUARD") != "baseball-query-disposable-v1"
    or container != f"skn34-baseball-query-{token}"
    or db_host != "127.0.0.1"
    or db_name != f"baseball_query_test_{token}"
    or db_user != f"baseball_owner_{token}"
    or reader_user != f"baseball_reader_{token}"
    or db_user == reader_user
    or db_password == reader_password
    or len(db_password) < 20
    or len(reader_password) < 20
    or not db_port.isdigit()
    or not 1024 < int(db_port) < 65536
    or int(db_port) == 5432
):
    raise ImproperlyConfigured("integration target is not an owned disposable PostgreSQL")

SECRET_KEY = "disposable-integration-only"
DEBUG = False
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.postgres",
    "rest_framework_simplejwt.token_blacklist",
    "baseball.apps.BaseballConfig",
    "llm",
    "accounts",
]
AUTH_USER_MODEL = "accounts.CustomUser"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_password,
        "HOST": db_host,
        "PORT": db_port,
    },
    "baseball_readonly": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": reader_user,
        "PASSWORD": reader_password,
        "HOST": db_host,
        "PORT": db_port,
    },
}
DATABASE_ROUTERS = ["baseball.db_router.BaseballDatabaseRouter"]
BASEBALL_QUERY_MAX_ROWS = positive_int_env("BASEBALL_QUERY_MAX_ROWS", 200)
BASEBALL_QUERY_TIMEOUT_MS = positive_int_env("BASEBALL_QUERY_TIMEOUT_MS", 50)
BASEBALL_QUERY_LOCK_TIMEOUT_MS = positive_int_env("BASEBALL_QUERY_LOCK_TIMEOUT_MS", 50)
BASEBALL_QUERY_MAX_SQL_BYTES = positive_int_env("BASEBALL_QUERY_MAX_SQL_BYTES", 32768)
BASEBALL_QUERY_MAX_RESPONSE_BYTES = positive_int_env(
    "BASEBALL_QUERY_MAX_RESPONSE_BYTES", 1024 * 1024
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
