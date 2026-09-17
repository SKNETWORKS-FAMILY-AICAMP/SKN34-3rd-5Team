import os

from django.core.exceptions import ImproperlyConfigured


def positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a positive integer") from None
    if value <= 0:
        raise ImproperlyConfigured(f"{name} must be a positive integer")
    return value
