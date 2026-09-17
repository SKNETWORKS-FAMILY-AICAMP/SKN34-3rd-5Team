from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import EmailChangeChallenge
from accounts.serializers import _next_nickname_change


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}})
class MemberIntegrationTest(APITestCase):
    password = "MemberSafe936!"

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="member01", email="old@example.test", password=self.password
        )
        self.other = get_user_model().objects.create_user(
            username="member02", email="other@example.test", password=self.password
        )

    def authenticate(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_signup_stores_only_explicit_identity_fields(self):
        response = self.client.post(reverse("signup"), {
            "username": "signup01", "email": "signup@example.test",
            "password": self.password, "re_password": self.password,
            "first_name": "홍길동", "birth_date": "2000-02-29", "gender": "M",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="signup01")
        self.assertEqual((user.first_name, str(user.birth_date), user.gender), ("홍길동", "2000-02-29", "M"))
        self.assertFalse(any("resident" in field.name for field in user._meta.fields))
        duplicate = self.client.post(reverse("signup"), {
            "username": "signup01", "email": "another@example.test", "password": self.password,
            "re_password": self.password, "first_name": "중복", "birth_date": "2000-01-01", "gender": "F",
        }, format="json")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("username", duplicate.json())
        future = self.client.post(reverse("signup"), {
            "username": "future01", "email": "future@example.test", "password": self.password,
            "re_password": self.password, "first_name": "미래", "birth_date": "2999-01-01", "gender": "F",
        }, format="json")
        self.assertEqual(future.status_code, 400)
        self.assertIn("birth_date", future.json())

    def test_signup_integrity_race_is_a_field_error(self):
        with patch("accounts.views.SignupSerializer.save", side_effect=IntegrityError):
            response = self.client.post(reverse("signup"), {
                "username": "raceuser", "email": "race@example.test", "password": self.password,
                "re_password": self.password, "first_name": "경합", "birth_date": "2000-01-01", "gender": "M",
            }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_profile_patch_allowlist_validation_and_persistence(self):
        self.authenticate()
        payload = {
            "nickname": "야구팬", "team_code": "LG", "first_name": "이름",
            "notifications": {"comments": False, "courses": True, "announcements": True},
            "visibility": {"courses": True, "posts": False, "likes": False},
        }
        response = self.client.patch(reverse("auth_user"), payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual((self.user.nickname, self.user.team_code), ("야구팬", "LG"))
        self.assertIsNotNone(self.user.nickname_changed_at)
        for bad in ({"nickname": "숫자1"}, {"team_code": "XX"}, {"avatar": "data:image/svg+xml;base64,PHN2Zz4="}, {"email": "hijack@example.test"}):
            with self.subTest(bad=next(iter(bad))):
                result = self.client.patch(reverse("auth_user"), bad, format="json")
                self.assertEqual(result.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.test")

    def test_nickname_cooldown_uses_kst_calendar_month_end(self):
        changed = datetime(2025, 8, 31, 12, tzinfo=ZoneInfo("Asia/Seoul"))
        self.assertEqual(_next_nickname_change(changed), datetime(2026, 2, 28, 12, tzinfo=ZoneInfo("Asia/Seoul")))
        self.user.nickname = "처음"
        self.user.nickname_changed_at = timezone.now()
        self.user.save(update_fields=["nickname", "nickname_changed_at"])
        self.authenticate()
        response = self.client.patch(reverse("auth_user"), {"nickname": "다음"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user.nickname, "처음")

    def test_email_challenge_is_owned_expires_counts_attempts_and_is_one_time(self):
        self.authenticate()
        sent = self.client.post(reverse("email_request"), {"email": "new@example.test"}, format="json")
        self.assertEqual(sent.status_code, 200)
        challenge = EmailChangeChallenge.objects.get(pk=sent.json()["request_id"])
        self.assertNotIn("123456", challenge.code_hash)
        code = mail.outbox[-1].body.split("인증 코드는 ", 1)[1][:6]

        self.authenticate(self.other)
        self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(challenge.pk), "code": code}, format="json").status_code, 400)
        self.authenticate()
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(challenge.pk), "code": "000000"}, format="json").status_code, 400)
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 2)
        self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(challenge.pk), "code": code}, format="json").status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.test")
        self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(challenge.pk), "code": code}, format="json").status_code, 400)

        exhausted = EmailChangeChallenge.objects.create(user=self.user, email="attempts@example.test", code_hash=challenge.code_hash, expires_at=timezone.now() + timedelta(minutes=1))
        wrong = "999999" if code != "999999" else "000000"
        for _ in range(5):
            self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(exhausted.pk), "code": wrong}, format="json").status_code, 400)
        self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(exhausted.pk), "code": code}, format="json").status_code, 400)
        expired = EmailChangeChallenge.objects.create(user=self.user, email="later@example.test", code_hash=challenge.code_hash, expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(reverse("email_verify"), {"request_id": str(expired.pk), "code": code}, format="json").status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.test")

    def test_recovery_responses_do_not_disclose_accounts_and_duplicate_email_is_safe(self):
        self.other.email = self.user.email
        self.other.save(update_fields=["email"])
        for name in ("username_request", "password_request"):
            with self.subTest(name=name):
                cache.clear(); mail.outbox.clear()
                known = self.client.post(reverse(name), {"email": self.user.email}, format="json")
                cache.clear()
                unknown = self.client.post(reverse(name), {"email": "missing@example.test"}, format="json")
                self.assertEqual((known.status_code, unknown.status_code), (200, 200))
                self.assertEqual(known.content, unknown.content)
        cache.clear()
        self.assertEqual(self.client.post(reverse("username_request"), {"email": self.user.email}, format="json").status_code, 200)
        self.assertEqual(self.client.post(reverse("username_request"), {"email": self.user.email}, format="json").status_code, 429)
        cache.clear()
        self.assertEqual(self.client.post(reverse("password_request"), {"email": self.user.email}, format="json").status_code, 200)
        self.assertEqual(self.client.post(reverse("password_request"), {"email": self.user.email}, format="json").status_code, 429)
