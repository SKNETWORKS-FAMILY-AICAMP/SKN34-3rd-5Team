#!/usr/bin/env python3
"""Create, verify, and remove one owned disposable PostgreSQL test container."""

import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[2]
IMAGE = "pgvector/pgvector:pg18"
PYTHON_VERSION = "3.13.5"
LABEL = "dev.skn34.baseball-query-test"


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def container_identity(container):
    result = subprocess.run(
        ["docker", "inspect", "--format", f"{{{{.Id}}}} {{{{index .Config.Labels \"{LABEL}\"}}}}", container],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return result or None


def owned_container(container, container_id, token):
    return container_identity(container) == f"{container_id} {token}"


def main():
    for command in ("docker", "uv"):
        if not shutil.which(command):
            raise RuntimeError(f"required command is missing: {command}")

    token = uuid.uuid4().hex[:12]
    container = f"skn34-baseball-query-{token}"
    database = f"baseball_query_test_{token}"
    owner = f"baseball_owner_{token}"
    reader = f"baseball_reader_{token}"
    owner_password = secrets.token_urlsafe(24)
    reader_password = secrets.token_urlsafe(24)
    container_id = None
    try:
        container_id = run(
            [
                "docker", "run", "-d", "--rm", "--name", container,
                "--label", f"{LABEL}={token}",
                "-e", f"POSTGRES_DB={database}",
                "-e", f"POSTGRES_USER={owner}",
                "-e", f"POSTGRES_PASSWORD={owner_password}",
                "-p", "127.0.0.1::5432", IMAGE,
            ],
            capture_output=True,
        ).stdout.strip()
        if not owned_container(container, container_id, token):
            raise RuntimeError("created container ownership could not be verified")

        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", owner, "-d", database],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        port_output = run(
            ["docker", "port", container, "5432/tcp"], capture_output=True
        ).stdout.strip()
        port = port_output.rsplit(":", 1)[-1]
        if not owned_container(container, container_id, token):
            raise RuntimeError("container ownership changed before database setup")
        print(f"TARGET: owned disposable PostgreSQL at 127.0.0.1:{port} ({container})")

        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": "baseball.tests.integration_settings",
                "BASEBALL_INTEGRATION_GUARD": "baseball-query-disposable-v1",
                "BASEBALL_INTEGRATION_TOKEN": token,
                "BASEBALL_INTEGRATION_CONTAINER": container,
                "DB_HOST": "127.0.0.1",
                "DB_PORT": port,
                "DB_NAME": database,
                "DB_USER": owner,
                "DB_PASSWORD": owner_password,
                "BASEBALL_DB_USER": reader,
                "BASEBALL_DB_PASSWORD": reader_password,
                "BASEBALL_QUERY_MAX_ROWS": "200",
                "BASEBALL_QUERY_TIMEOUT_MS": "200",
                "BASEBALL_QUERY_LOCK_TIMEOUT_MS": "25",
                "BASEBALL_QUERY_MAX_SQL_BYTES": "32768",
                "BASEBALL_QUERY_MAX_RESPONSE_BYTES": "1048576",
            }
        )
        run(
            [
                "docker", "exec", container, "psql", "-U", owner, "-d", database,
                "-v", "ON_ERROR_STOP=1", "-c",
                f'REVOKE CREATE ON DATABASE "{database}" FROM PUBLIC;',
                "-c", "REVOKE CREATE ON SCHEMA public FROM PUBLIC;",
            ]
        )
        uv = [
            "uv", "run", "--python", PYTHON_VERSION, "--isolated",
            "--with-requirements", "requirements.txt", "python",
        ]
        run([*uv, "manage.py", "migrate", "--noinput"], cwd=BACKEND, env=env)
        run([*uv, "-m", "baseball.tests.verify_csv_migration"], cwd=BACKEND, env=env)
        if subprocess.run(
            [*uv, "manage.py", "provision_baseball_reader"], cwd=BACKEND, env=env
        ).returncode == 0:
            raise RuntimeError("provision unexpectedly accepted default PUBLIC TEMPORARY")
        run(
            [*uv, "manage.py", "provision_baseball_reader", "--prepare-db-permissions"],
            cwd=BACKEND,
            env=env,
        )
        run([*uv, "-m", "baseball.tests.postgres_integration"], cwd=BACKEND, env=env)
        run(
            [*uv, "-c", "import django, platform, psycopg, sqlglot; "
             "print(f'Python {platform.python_version()} | Django {django.get_version()} | '"
             "f'psycopg {psycopg.__version__} | sqlglot {sqlglot.__version__}')"],
            cwd=BACKEND,
            env=env,
        )
        run(["docker", "exec", container, "postgres", "--version"])
        print(f"PASS: disposable PostgreSQL integration completed ({container})")
    finally:
        if container_id:
            identity = container_identity(container)
            if identity:
                if identity != f"{container_id} {token}":
                    raise RuntimeError("refusing to remove a container without matching ownership")
                run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL)
            leftovers = run(
                ["docker", "ps", "-a", "--filter", f"name=^/{container}$", "--format", "{{.Names}}"],
                capture_output=True,
            ).stdout.strip()
            if leftovers:
                raise RuntimeError(f"owned disposable container was not removed: {leftovers}")
            print("CLEANUP: no owned disposable container remains")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
