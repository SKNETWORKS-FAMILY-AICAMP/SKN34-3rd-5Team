from config.settings import *  # noqa: F403


INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in {"llm", "django.contrib.postgres"}]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ROOT_URLCONF = "accounts.test.migration_test_settings"
urlpatterns = []
