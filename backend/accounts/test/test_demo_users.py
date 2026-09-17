from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from accounts.demo_users import DEMO_PASSWORD, is_demo_identity, seed_demo_users


SAMPLE_USERNAMES = [f"sampleuser{index:02d}" for index in range(1, 11)]


class DemoUsersMigrationTests(TransactionTestCase):
    migrate_seed_from = ("accounts", "0002_member_profile_email_challenge")
    migrate_from = ("accounts", "0003_add_sample_users")
    migrate_to = ("accounts", "0004_enable_demo_users")

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_seed_from])
        old_apps = self.executor.loader.project_state([self.migrate_seed_from]).apps
        old_apps.get_model("accounts", "CustomUser").objects.filter(
            username__in=["sampleadmin", *SAMPLE_USERNAMES]
        ).delete()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def migrate_forward(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        return self.executor.loader.project_state([self.migrate_to]).apps.get_model(
            "accounts", "CustomUser"
        )

    @override_settings(DEBUG=True, DEMO_USERS_ENABLED=True)
    def test_creates_admin_and_upgrades_original_samples_idempotently(self):
        User = self.migrate_forward()
        admin = User.objects.get(username="sampleadmin")
        samples = list(User.objects.filter(username__in=SAMPLE_USERNAMES))

        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertTrue(check_password(DEMO_PASSWORD, admin.password))
        self.assertEqual(len(samples), 10)
        self.assertTrue(all(check_password(DEMO_PASSWORD, user.password) for user in samples))
        self.assertTrue(all(not user.is_staff and not user.is_superuser for user in samples))

        call_command("migrate", verbosity=0)
        self.assertEqual(User.objects.filter(username__in=["sampleadmin", *SAMPLE_USERNAMES]).count(), 11)

    @override_settings(DEBUG=True, DEMO_USERS_ENABLED=True)
    def test_preserves_collisions_existing_users_and_changed_passwords(self):
        User = self.apps.get_model("accounts", "CustomUser")
        changed = User.objects.get(username="sampleuser01")
        changed.password = "changed-password-hash"
        changed.save(update_fields=["password"])
        original = User.objects.get(username="sampleuser02")
        User.objects.create(username="existing", password="existing-password-hash")
        User.objects.create(
            username="sampleadmin",
            email="sampleadmin@example.com",
            first_name="더미관리자",
        )
        User.objects.filter(username="sampleadmin").update(password=make_password(DEMO_PASSWORD))

        User = self.migrate_forward()
        self.assertEqual(User.objects.get(username="sampleuser01").password, "changed-password-hash")
        self.assertTrue(check_password(DEMO_PASSWORD, User.objects.get(pk=original.pk).password))
        self.assertEqual(User.objects.get(username="existing").password, "existing-password-hash")
        collision = User.objects.get(username="sampleadmin")
        self.assertFalse(collision.is_staff)
        self.assertFalse(collision.is_superuser)
        self.assertEqual(collision.email, "sampleadmin@example.com")

    @override_settings(DEBUG=True, DEMO_USERS_ENABLED=True)
    def test_later_migrate_recreates_missing_sample(self):
        User = self.migrate_forward()
        User.objects.filter(username="sampleuser10").delete()

        call_command("migrate", verbosity=0)

        recreated = User.objects.get(username="sampleuser10")
        self.assertTrue(check_password(DEMO_PASSWORD, recreated.password))

    def test_disabled_setting_does_not_create_privileged_user(self):
        with override_settings(DEBUG=True, DEMO_USERS_ENABLED=False):
            User = self.migrate_forward()
        self.assertFalse(User.objects.filter(username="sampleadmin").exists())

        with override_settings(DEBUG=True, DEMO_USERS_ENABLED=True):
            call_command("migrate", verbosity=0)
            call_command("migrate", verbosity=0)
        self.assertEqual(User.objects.filter(username__in=["sampleadmin", *SAMPLE_USERNAMES]).count(), 11)

    @override_settings(DEBUG=False, DEMO_USERS_ENABLED=True)
    def test_debug_false_does_not_create_privileged_user(self):
        User = self.migrate_forward()
        self.assertFalse(User.objects.filter(username="sampleadmin").exists())


@override_settings(DEBUG=True, DEMO_USERS_ENABLED=True)
class DemoUsersGuardTests(SimpleTestCase):
    def test_seed_noops_without_model_or_profile_fields(self):
        missing_model_apps = Mock()
        missing_model_apps.get_model.side_effect = LookupError
        seed_demo_users(missing_model_apps, using="default")

        incomplete_user = Mock()
        incomplete_user._meta.fields = [SimpleNamespace(name="username")]
        incomplete_apps = Mock()
        incomplete_apps.get_model.return_value = incomplete_user
        seed_demo_users(incomplete_apps, using="default")

        incomplete_user.objects.using.assert_not_called()

    @patch("accounts.demo_users.check_password")
    def test_unrelated_username_skips_password_check(self, check_password):
        self.assertFalse(is_demo_identity(Mock(username="member")))
        check_password.assert_not_called()
