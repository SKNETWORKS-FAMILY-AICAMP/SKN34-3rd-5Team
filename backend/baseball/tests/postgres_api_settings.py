import os

from django.core.exceptions import ImproperlyConfigured

from .api_settings import *  # noqa: F403


if (
    os.getenv("BASEBALL_CRUD_TEST_GUARD") != "owned-disposable-baseball-crud-v1"
    or os.getenv("DB_HOST") != "127.0.0.1"
    or os.getenv("DB_PORT") in {None, "", "5432"}
    or not os.getenv("DB_NAME", "").startswith("baseball_crud_")
    or not os.getenv("BASEBALL_CRUD_TEST_CONTAINER", "").startswith("skn34-baseball-crud-")
    or not os.getenv("BASEBALL_CRUD_TEST_DB", "").startswith("baseball_crud_test_")
):
    raise ImproperlyConfigured("baseball CRUD tests require an owned disposable PostgreSQL")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"], "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"], "HOST": os.environ["DB_HOST"],
        "PORT": os.environ["DB_PORT"],
        "TEST": {"NAME": os.environ["BASEBALL_CRUD_TEST_DB"]},
    }
}
