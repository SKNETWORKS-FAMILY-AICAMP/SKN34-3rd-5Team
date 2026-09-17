SECRET_KEY = "unit-tests-only"
INSTALLED_APPS = ["django.contrib.contenttypes", "baseball.apps.BaseballConfig"]
DATABASES = {
    "default": {"ENGINE": "django.db.backends.postgresql"},
    "baseball_readonly": {"ENGINE": "django.db.backends.postgresql"},
}
BASEBALL_QUERY_MAX_ROWS = 200
BASEBALL_QUERY_TIMEOUT_MS = 3000
BASEBALL_QUERY_LOCK_TIMEOUT_MS = 1000
BASEBALL_QUERY_MAX_SQL_BYTES = 32768
BASEBALL_QUERY_MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
