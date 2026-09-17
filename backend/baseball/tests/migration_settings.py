from .unit_settings import *  # noqa: F403

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
    "other": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
}
