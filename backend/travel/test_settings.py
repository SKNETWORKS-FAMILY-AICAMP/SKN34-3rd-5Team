import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase


BACKEND = Path(__file__).resolve().parent.parent


class CourseSettingsTests(TestCase):
    def load_hosts(self, value=None):
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(BACKEND)}
        if value is not None:
            environment["DJANGO_ALLOWED_HOSTS"] = value
        return subprocess.run(
            [sys.executable, "-B", "-c", "from unittest.mock import patch; from django.conf import Settings; import json; patcher = patch('dotenv.load_dotenv'); patcher.start(); print(json.dumps(Settings('config.settings').ALLOWED_HOSTS))"],
            cwd=BACKEND,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_allowed_hosts_are_explicit_and_environment_derived(self):
        self.assertEqual(json.loads(self.load_hosts().stdout), ["localhost", "127.0.0.1", "[::1]"])
        result = self.load_hosts("backend, localhost,127.0.0.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["backend", "localhost", "127.0.0.1"])
        self.assertNotEqual(self.load_hosts("*").returncode, 0)
