from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.demo_users import DEMO_PASSWORD


class UserAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superuser = User.objects.create_superuser(username="admin", password="password")
        cls.member = User.objects.create_user(
            username="member", email="member@example.com", nickname="검색별명"
        )
        cls.other = User.objects.create_user(username="other", nickname="다른별명")
        cls.url = reverse("admin:accounts_customuser_changelist")

    def test_user_list_search_and_access(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 302)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.username)
        self.assertContains(response, self.member.email)
        self.assertContains(response, self.member.nickname)

        response = self.client.get(self.url, {"q": self.member.nickname})
        self.assertContains(response, self.member.username)
        self.assertNotContains(response, self.other.username)

    @override_settings(DEBUG=True, DEMO_USERS_ENABLED=True)
    def test_demo_password_column_only_shows_matching_fixture(self):
        User = get_user_model()
        sample, _ = User.objects.get_or_create(username="sampleuser01")
        sample.email = "sampleuser01@example.com"
        sample.first_name = "김민준"
        sample.birth_date = "1991-01-01"
        sample.gender = "M"
        sample.nickname = "야구팬민준"
        sample.team_code = "LG"
        sample.set_password(DEMO_PASSWORD)
        sample.save()
        changed, _ = User.objects.get_or_create(username="sampleuser02")
        changed.email = "sampleuser02@example.com"
        changed.set_password("Changed123!")
        changed.save()
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertContains(response, "더미 비밀번호")
        self.assertContains(response, DEMO_PASSWORD, count=1)
        self.assertContains(response, sample.username)
        self.assertContains(response, changed.username)

    @override_settings(DEBUG=False, DEMO_USERS_ENABLED=True)
    def test_demo_password_column_hidden_without_debug(self):
        self.client.force_login(self.superuser)
        self.assertNotContains(self.client.get(self.url), "더미 비밀번호")

    @override_settings(DEBUG=True, DEMO_USERS_ENABLED=False)
    def test_demo_password_column_hidden_without_opt_in(self):
        self.client.force_login(self.superuser)
        self.assertNotContains(self.client.get(self.url), "더미 비밀번호")
