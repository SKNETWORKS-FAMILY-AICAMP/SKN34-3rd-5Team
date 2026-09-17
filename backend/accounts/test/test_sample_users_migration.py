from django.contrib.auth.hashers import is_password_usable
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


SAMPLE_USERNAMES = [f"sampleuser{index:02d}" for index in range(1, 11)]


class SampleUsersMigrationTest(TransactionTestCase):
    migrate_from = ("accounts", "0002_member_profile_email_challenge")
    migrate_to = ("accounts", "0003_add_sample_users")

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        old_apps.get_model("accounts", "CustomUser").objects.filter(
            username__in=SAMPLE_USERNAMES
        ).delete()

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )

    def migrate_forward(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        return self.executor.loader.project_state([self.migrate_to]).apps.get_model(
            "accounts", "CustomUser"
        )

    def test_creates_exactly_ten_normal_users_with_unusable_passwords(self):
        User = self.migrate_forward()
        users = list(User.objects.filter(username__in=SAMPLE_USERNAMES))

        self.assertEqual(len(users), 10)
        self.assertEqual({user.username for user in users}, set(SAMPLE_USERNAMES))
        self.assertTrue(all(not is_password_usable(user.password) for user in users))
        self.assertTrue(all(not user.is_staff and not user.is_superuser for user in users))

    def test_existing_user_is_unchanged_and_repeat_is_idempotent(self):
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model("accounts", "CustomUser")
        User.objects.create(
            username="sampleuser01",
            password="existing-password-hash",
            email="kept@example.com",
            first_name="기존사용자",
            nickname="기존닉네임",
            team_code="LG",
        )

        User = self.migrate_forward()
        existing = User.objects.get(username="sampleuser01")
        self.assertEqual(User.objects.filter(username__in=SAMPLE_USERNAMES).count(), 10)
        self.assertEqual(
            (existing.password, existing.email, existing.first_name, existing.nickname),
            ("existing-password-hash", "kept@example.com", "기존사용자", "기존닉네임"),
        )

        MigrationExecutor(connection).migrate([self.migrate_from])
        User = self.migrate_forward()
        self.assertEqual(User.objects.filter(username__in=SAMPLE_USERNAMES).count(), 10)
