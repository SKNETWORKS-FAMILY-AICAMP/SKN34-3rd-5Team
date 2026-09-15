import importlib
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.core.management.base import CommandError
from django.core.validators import MaxLengthValidator
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from baseball.data_loader import BaseballDataLoaderV1, NATURAL_FIELDS, stable_id


class BaseballCsvMigrationTests(TransactionTestCase):
    databases = {"default", "other"}
    data_dir = Path(__file__).resolve().parents[3] / "data"
    migration = importlib.import_module("baseball.migrations.0002_load_baseball_csv_data")

    def reset_to_empty_0001(self, alias="default"):
        executor = MigrationExecutor(connections[alias])
        executor.migrate([("baseball", "0001_initial")])
        old_apps = executor.loader.project_state([("baseball", "0001_initial")]).apps
        for name in reversed(NATURAL_FIELDS):
            old_apps.get_model("baseball", name).objects.using(alias).all().delete()
        return old_apps

    def migrate_forward(self, alias="default"):
        executor = MigrationExecutor(connections[alias])
        executor.migrate([("baseball", "0002_load_baseball_csv_data")])
        return executor.loader.project_state([("baseball", "0002_load_baseball_csv_data")]).apps

    def test_empty_migration_populates_all_models_and_relations(self):
        self.reset_to_empty_0001()
        historical = self.migrate_forward()
        counts = {name: historical.get_model("baseball", name).objects.count() for name in NATURAL_FIELDS}
        self.assertEqual(19, len(counts))
        self.assertTrue(all(count > 0 for count in counts.values()))
        self.assertEqual(10, counts["Team"])
        self.assertEqual(9, counts["Stadium"])
        Game = historical.get_model("baseball", "Game")
        self.assertFalse(Game.objects.filter(home_team__isnull=False, home_team__team_code="").exists())

    def test_existing_natural_key_and_reverse_are_preserved(self):
        historical = self.reset_to_empty_0001()
        Team = historical.get_model("baseball", "Team")
        Team.objects.create(id=7, team_code="LG", team_name_ko="관리자 수정값")
        self.migrate_forward()
        self.assertEqual("관리자 수정값", Team.objects.get(team_code="LG").team_name_ko)
        MigrationExecutor(connections["default"]).migrate([("baseball", "0001_initial")])
        self.assertEqual("관리자 수정값", Team.objects.get(team_code="LG").team_name_ko)

    def test_loader_rerun_and_nondefault_alias_are_idempotent(self):
        self.reset_to_empty_0001("other")
        historical = self.migrate_forward("other")
        before = historical.get_model("baseball", "Game").objects.using("other").count()
        report = BaseballDataLoaderV1(historical, self.data_dir, "other").load()
        self.assertEqual(before, historical.get_model("baseball", "Game").objects.using("other").count())
        self.assertEqual(0, report["totals"]["imported"])

    def test_loader_rejects_invalid_choice_and_overlength_scalar_fields(self):
        historical = self.reset_to_empty_0001()
        Team = historical.get_model("baseball", "Team")
        field = Team._meta.get_field("team_code")
        cases = ({"_choices": (("LG", "LG"),)}, {"_validators": [MaxLengthValidator(2)]})
        for index, patched in enumerate(cases, 1):
            field.__dict__.pop("validators", None)
            with self.subTest(patched=patched), mock.patch.multiple(field, **patched):
                loader = BaseballDataLoaderV1(historical, self.data_dir)
                with self.assertRaises(CommandError):
                    loader.add(Team, f"invalid-{index}", team_code="INVALID", team_name_ko="테스트")
                self.assertEqual(1, len(loader.rejections))
        field.__dict__.pop("validators", None)
        self.assertFalse(Team.objects.exists())

    def test_invalid_csv_rolls_back_and_failed_migration_is_unrecorded(self):
        historical = self.reset_to_empty_0001()
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "data"
            shutil.copytree(self.data_dir, copied)
            path = copied / "preprocessed/구장좌석구역.csv"
            text = path.read_text(encoding="utf-8-sig").replace(",Y,", ",UNKNOWN,", 1)
            path.write_text(text, encoding="utf-8-sig")
            with self.assertRaisesMessage(Exception, "불리언이 아닌 값"):
                BaseballDataLoaderV1(historical, copied).load()
        self.assertFalse(historical.get_model("baseball", "Team").objects.exists())

        with mock.patch.object(self.migration.BaseballDataLoaderV1, "load", side_effect=ValueError("broken csv")):
            with self.assertRaisesMessage(ValueError, "broken csv"):
                self.migrate_forward()
        self.assertFalse(MigrationRecorder(connections["default"]).migration_qs.filter(app="baseball", name="0002_load_baseball_csv_data").exists())

    def test_stable_id_collision_rolls_back(self):
        historical = self.reset_to_empty_0001()
        Team = historical.get_model("baseball", "Team")
        Team.objects.create(id=stable_id(Team, "LG"), team_code="OTHER", team_name_ko="다른 값")
        with self.assertRaisesMessage(Exception, "stable ID collision"):
            self.migrate_forward()
        self.assertEqual(["OTHER"], list(Team.objects.values_list("team_code", flat=True)))

    def test_missing_data_directory_reports_the_path(self):
        missing = Path(tempfile.gettempdir()) / "missing-baseball-csv-data"
        with self.assertRaisesMessage(CommandError, str(missing)):
            BaseballDataLoaderV1(apps, missing)
