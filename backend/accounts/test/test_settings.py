import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import django


SETTINGS_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.py"


class SettingsRegressionTest(unittest.TestCase):
    def run_settings(self, environment=None):
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(SETTINGS_PATH.parent.parent)}
        env.update(environment or {})
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                """
import json
from unittest.mock import patch
from django.conf import Settings

with patch("dotenv.load_dotenv") as load_dotenv:
    settings = Settings("config.settings")
    from unittest.mock import call
    assert load_dotenv.call_args_list == [
        call(settings.BASE_DIR / ".env", override=False),
        call(settings.BASE_DIR.parent / ".env", override=False),
    ]
print(json.dumps({
    "mailers": settings.MAILERS,
    "default_from_email": settings.DEFAULT_FROM_EMAIL,
    "db_host": settings.DATABASES["default"]["HOST"],
    "explicit_settings": sorted(settings._explicit_settings),
    "jwt_uses_secret_key": settings.SIMPLE_JWT["SIGNING_KEY"] == settings.SECRET_KEY,
}))
""",
            ],
            cwd=SETTINGS_PATH.parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def load_settings(self, environment=None):
        result = self.run_settings(environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def run_mailer(self, backend):
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(SETTINGS_PATH.parent.parent),
            "EMAIL_BACKEND": backend,
        }
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                """
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from django.conf import Settings, settings
from django.core import mail

with patch("dotenv.load_dotenv"):
    config = Settings("config.settings")
settings.configure(MAILERS=config.MAILERS, DEFAULT_FROM_EMAIL=config.DEFAULT_FROM_EMAIL)
output = io.StringIO()
with redirect_stdout(output):
    sent = mail.send_mail("subject", "body", None, ["recipient@example.test"])
assert sent == 1
if config.MAILERS["default"]["BACKEND"].endswith("locmem.EmailBackend"):
    assert len(mail.outbox) == 1
else:
    assert "subject" in output.getvalue()
""",
            ],
            cwd=SETTINGS_PATH.parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_smtp_settings_map_environment_variables(self):
        settings = self.load_settings(
            {
                "EMAIL_HOST": "smtp.example.test",
                "EMAIL_PORT": "2525",
                "EMAIL_HOST_USER": "mailer@example.test",
                "EMAIL_HOST_PASSWORD": "app-password",
                "EMAIL_USE_TLS": " TrUe ",
                "DEFAULT_FROM_EMAIL": "noreply@example.test",
            }
        )

        options = settings["mailers"]["default"]["OPTIONS"]
        self.assertEqual(options["host"], "smtp.example.test")
        self.assertEqual(options["port"], 2525)
        self.assertEqual(options["username"], "mailer@example.test")
        self.assertEqual(options["password"], "app-password")
        self.assertTrue(options["use_tls"])
        self.assertEqual(settings["default_from_email"], "noreply@example.test")

    def test_mailer_backend_defaults_to_smtp_and_accepts_overrides(self):
        self.assertEqual(
            self.load_settings()["mailers"]["default"]["BACKEND"],
            "django.core.mail.backends.smtp.EmailBackend",
        )
        for backend in (
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
        ):
            with self.subTest(backend=backend):
                settings = self.load_settings({"EMAIL_BACKEND": backend})
                self.assertEqual(settings["mailers"]["default"]["BACKEND"], backend)
                self.assertNotIn("OPTIONS", settings["mailers"]["default"])

        settings = self.load_settings({"EMAIL_BACKEND": ""})
        self.assertEqual(
            settings["mailers"]["default"]["BACKEND"],
            "django.core.mail.backends.smtp.EmailBackend",
        )

    @unittest.skipUnless(django.VERSION >= (6, 1), "MAILERS requires Django 6.1+")
    def test_console_and_locmem_backends_send_without_smtp_options(self):
        for backend in (
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
        ):
            with self.subTest(backend=backend):
                result = self.run_mailer(backend)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_gmail_smtp_options_map_environment_variables(self):
        settings = self.load_settings(
            {
                "EMAIL_HOST": "smtp.gmail.com",
                "EMAIL_PORT": "587",
                "EMAIL_HOST_USER": "account@gmail.com",
                "EMAIL_HOST_PASSWORD": "google-app-password",
                "EMAIL_USE_TLS": "true",
                "DEFAULT_FROM_EMAIL": "account@gmail.com",
            }
        )

        options = settings["mailers"]["default"]["OPTIONS"]
        self.assertEqual(options["host"], "smtp.gmail.com")
        self.assertEqual(options["port"], 587)
        self.assertEqual(options["username"], "account@gmail.com")
        self.assertEqual(options["password"], "google-app-password")
        self.assertTrue(options["use_tls"])
        self.assertEqual(settings["default_from_email"], "account@gmail.com")

    def test_mailers_do_not_define_deprecated_email_settings(self):
        settings = self.load_settings()

        deprecated = {
            "EMAIL_BACKEND",
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "EMAIL_USE_TLS",
        }
        self.assertTrue(deprecated.isdisjoint(settings["explicit_settings"]))

    def test_tls_accepts_true_and_false_values(self):
        for value, expected in (("true", True), (" false ", False), ("TRUE", True)):
            with self.subTest(value=value):
                settings = self.load_settings({"EMAIL_USE_TLS": value})
                self.assertEqual(
                    settings["mailers"]["default"]["OPTIONS"]["use_tls"], expected
                )

    def test_tls_rejects_unknown_values(self):
        result = self.run_settings({"EMAIL_USE_TLS": "yes"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EMAIL_USE_TLS", result.stderr)

    def test_mailpit_is_the_local_default(self):
        settings = self.load_settings()

        options = settings["mailers"]["default"]["OPTIONS"]
        self.assertEqual(options["host"], "mailpit")
        self.assertEqual(options["port"], 1025)
        self.assertFalse(options["use_tls"])

    def test_default_from_email_fallbacks(self):
        cases = (
            ({"EMAIL_HOST_USER": "mailer@example.test"}, "mailer@example.test"),
            ({}, "webmaster@localhost"),
        )
        for environment, expected in cases:
            with self.subTest(environment=environment):
                settings = self.load_settings(environment)
                self.assertEqual(settings["default_from_email"], expected)

    def test_database_host_uses_environment_or_local_default(self):
        self.assertEqual(self.load_settings()["db_host"], "db")
        self.assertEqual(
            self.load_settings({"DB_HOST": "db.example.test"})["db_host"],
            "db.example.test",
        )

    def test_jwt_signing_key_uses_module_secret_key(self):
        self.assertTrue(self.load_settings()["jwt_uses_secret_key"])


if __name__ == "__main__":
    unittest.main()
