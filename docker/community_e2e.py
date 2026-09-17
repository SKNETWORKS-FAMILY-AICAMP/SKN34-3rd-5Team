#!/usr/bin/env python3
"""Disposable HTTP E2E for the integrated community-w0 Compose stack."""

import argparse
import json
import os
import secrets
import sys
from datetime import timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import Resolver404, resolve
from django.utils import timezone


BASE_URL = "http://nginx/api"
OWNED_PREFIX = "w0e2e"


class E2EFailure(Exception):
    pass


def check(condition, message):
    if not condition:
        raise E2EFailure(message)


def request(method, path, body=None, token=None, expected=(200,), headers=None):
    data = None if body is None else json.dumps(body).encode()
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    try:
        response = urlopen(Request(f"{BASE_URL}{path}", data=data, headers=request_headers, method=method), timeout=20)
        status, raw = response.status, response.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    check(status in expected, f"{method} {path} returned HTTP {status}, expected {expected}")
    if status == 204 or not raw:
        return None
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise E2EFailure(f"{method} {path} did not return JSON") from error


def assert_w0():
    check(os.getenv("COMMUNITY_COMPOSE_PROJECT") == "community-w0", "write mode is restricted to community-w0")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database = cursor.fetchone()[0]
    check(database == os.getenv("DB_NAME"), "connected database does not match the isolated Compose environment")
    check(connection.settings_dict["HOST"] == "db", "database host is not the isolated Compose service")


def integrated_models():
    try:
        from community.models import CommunityPost, CommunityReport, GamePrediction, PredictionGame
    except ImportError:
        return None
    return CommunityPost, CommunityReport, GamePrediction, PredictionGame


def preflight():
    assert_w0()
    request("GET", "/community/posts/?board=free")
    paths = (
        "/community/posts/w0-e2e-preflight/",
        "/community/posts/w0-e2e-preflight/comments/",
        "/community/comments/1/",
        "/community/posts/w0-e2e-preflight/vote/",
        "/community/posts/w0-e2e-preflight/reports/",
        "/community/predictions/games/",
        "/community/predictions/games/w0-e2e-preflight/vote/",
    )
    missing = []
    for path in paths:
        try:
            resolve(path)
        except Resolver404:
            missing.append(path)
    if integrated_models() is None or missing:
        print(f"PREFLIGHT DEFERRED: integrated community models/routes missing ({len(missing)} routes)")
        return
    print("PREFLIGHT PASS: integrated community models/routes and public read are available")


def run():
    assert_w0()
    models = integrated_models()
    check(models is not None, "integrated community models are not available")
    CommunityPost, CommunityReport, GamePrediction, PredictionGame = models
    suffix = secrets.token_hex(5)
    usernames = [f"{OWNED_PREFIX}{suffix}a", f"{OWNED_PREFIX}{suffix}b"]
    password = f"W0!a{secrets.token_hex(12)}"
    keys = [f"{OWNED_PREFIX}-{secrets.token_hex(12)}" for _ in range(2)]
    fixture_id = f"{OWNED_PREFIX}-fixture-{suffix}"
    created_ids = []
    User = get_user_model()

    def auth(token):
        return {"token": token}

    try:
        public_posts = request("GET", "/community/posts/?board=free")
        check(isinstance(public_posts, list), "public post list is not an array")
        print("PASS public post read")

        for index, username in enumerate(usernames):
            request("POST", "/auth/signup/", {
                "username": username,
                "email": f"{username}@example.test",
                "password": password,
                "re_password": password,
                "first_name": f"W0 E2E {index + 1}",
                "birth_date": "2000-01-01",
                "gender": "M" if index == 0 else "F",
            }, expected=(201,))
        users = list(User.objects.filter(username__in=usernames).order_by("username"))
        check(len(users) == 2 and all(not user.is_staff and not user.is_superuser for user in users), "ordinary members were not created")
        pairs = []
        for username in usernames:
            pair = request("POST", "/auth/signin", {"username": username, "password": password})
            check(isinstance(pair.get("access"), str) and isinstance(pair.get("refresh"), str), "JWT login did not return a token pair")
            pairs.append(pair)
        token_a, token_b = pairs[0]["access"], pairs[1]["access"]
        print("PASS two ordinary members and actual JWT login")

        request("POST", "/community/posts/", {
            "board": "free", "teamCode": "", "category": "잡담", "title": "unauthorized", "content": "blocked"
        }, expected=(401,))
        for token, key, payload in (
            (token_a, keys[0], {"board": "free", "teamCode": "", "category": "잡담", "title": "W0 free", "content": "free body"}),
            (token_b, keys[1], {"board": "teams", "teamCode": "LG", "category": "잡담", "title": "W0 team", "content": "team body"}),
        ):
            post = request("POST", "/community/posts/", payload, token=token, expected=(201,), headers={"Idempotency-Key": key})
            check(isinstance(post.get("id"), str), "post creation did not return an id")
            created_ids.append(post["id"])
        free_id, team_id = created_ids
        for post_id in created_ids:
            request("GET", f"/community/posts/{post_id}/")
        request("PATCH", f"/community/posts/{free_id}/", {"title": "other user"}, **auth(token_b), expected=(403,))
        request("DELETE", f"/community/posts/{free_id}/", **auth(token_b), expected=(403,))
        updated_free = request("PATCH", f"/community/posts/{free_id}/", {"title": "W0 free updated"}, **auth(token_a))
        updated_team = request("PATCH", f"/community/posts/{team_id}/", {"title": "W0 team updated"}, **auth(token_b))
        check(updated_free["title"] == "W0 free updated" and updated_team["title"] == "W0 team updated", "post updates did not persist")
        print("PASS free/team post create-read-update and denial")

        comment = request("POST", f"/community/posts/{free_id}/comments/", {"content": "W0 comment"}, **auth(token_a), expected=(201,))
        comment_id = comment["id"]
        request("PATCH", f"/community/comments/{comment_id}/", {"content": "other"}, **auth(token_b), expected=(403,))
        request("DELETE", f"/community/comments/{comment_id}/", **auth(token_b), expected=(403,))
        changed = request("PATCH", f"/community/comments/{comment_id}/", {"content": "W0 comment updated"}, **auth(token_a))
        check(changed["content"] == "W0 comment updated", "comment update did not persist")
        comments = request("GET", f"/community/posts/{free_id}/comments/")
        check(any(value["id"] == comment_id for value in comments), "comment list omitted the created comment")
        request("DELETE", f"/community/comments/{comment_id}/", **auth(token_a), expected=(204,))
        print("PASS comment CRUD and other-user denial")

        for desired in ("up", "down", None):
            vote = request("POST", f"/community/posts/{free_id}/vote/", {"vote": desired}, **auth(token_a))
            check(vote["vote"] == desired, "post vote transition did not persist")
        first_report = request("POST", f"/community/posts/{free_id}/reports/", {"reason": "spam", "detail": "W0 disposable report"}, **auth(token_b), expected=(201,))
        second_report = request("POST", f"/community/posts/{free_id}/reports/", {"reason": "spam", "detail": "W0 disposable report"}, **auth(token_b), expected=(200,))
        check(first_report["created"] is True and second_report == {"id": first_report["id"], "created": False}, "report idempotency failed")
        check(CommunityReport.objects.filter(post_id=free_id, reporter__username=usernames[1]).count() == 1, "report was not persisted exactly once")
        print("PASS post vote transition/cancel and report persistence")

        live_games = request("GET", "/community/predictions/games/")
        check(isinstance(live_games, list), "prediction live list is not an array")
        now = timezone.now()
        game_date = now.astimezone(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)
        PredictionGame.objects.create(
            source_id=fixture_id, game_date=game_date, starts_at=now + timedelta(days=1), stadium="W0 E2E FIXTURE",
            away_team_code="LG", away_team_name="W0 Away", home_team_code="OB", home_team_name="W0 Home",
            status="scheduled", result="", source_fetched_at=now,
        )
        for desired in ("home", "away", None):
            game = request("POST", f"/community/predictions/games/{fixture_id}/vote/", {"choice": desired}, **auth(token_a))
            check(game["myChoice"] == desired, "game vote transition did not persist")
        check(GamePrediction.objects.filter(game_id=fixture_id).count() == 0, "cancelled game vote remained in the database")
        PredictionGame.objects.filter(pk=fixture_id).update(locked_at=timezone.now())
        request("POST", f"/community/predictions/games/{fixture_id}/vote/", {"choice": "home"}, **auth(token_a), expected=(409,))
        print("PASS prediction live list and isolated fixture vote/change/cancel/lock")

        request("DELETE", f"/community/posts/{free_id}/", **auth(token_a), expected=(204,))
        request("DELETE", f"/community/posts/{team_id}/", **auth(token_b), expected=(204,))
        for post_id in created_ids:
            request("GET", f"/community/posts/{post_id}/", expected=(404,))
        print("PASS free/team post delete")
    finally:
        CommunityPost.objects.filter(idempotency_key__in=keys).delete()
        PredictionGame.objects.filter(pk=fixture_id).delete()
        User.objects.filter(username__in=usernames).delete()
        check(not CommunityPost.objects.filter(idempotency_key__in=keys).exists(), "owned post cleanup failed")
        check(not PredictionGame.objects.filter(pk=fixture_id).exists(), "owned prediction fixture cleanup failed")
        check(not User.objects.filter(username__in=usernames).exists(), "owned member cleanup failed")
    print("PASS owned-only cleanup; no credentials or tokens emitted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="run disposable writes; community-w0 only")
    args = parser.parse_args()
    try:
        run() if args.run else preflight()
    except E2EFailure as error:
        print(f"FAIL {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
