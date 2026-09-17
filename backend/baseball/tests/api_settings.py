SECRET_KEY = "baseball-api-tests-only-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
ROOT_URLCONF = "baseball.tests.urls"
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "rest_framework", "drf_spectacular", "rest_framework_simplejwt", "rest_framework_simplejwt.token_blacklist",
    "baseball.apps.BaseballConfig", "accounts",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
AUTH_USER_MODEL = "accounts.CustomUser"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {"SCHEMA_PATH_PREFIX_INSERT": "/api"}
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True, "DIRS": [], "OPTIONS": {"context_processors": []}}]
