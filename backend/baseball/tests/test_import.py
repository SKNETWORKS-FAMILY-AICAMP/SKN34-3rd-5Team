import csv
import io
import json
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from baseball.serializers import RESOURCE_MODELS
from baseball.management.commands.import_baseball_data import stable_id
from baseball.models import Team


class BaseballImportTests(TestCase):
    data_dir = Path(__file__).resolve().parents[3] / "data"

    def test_import_is_idempotent_and_relations_are_valid(self):
        first = io.StringIO()
        call_command("import_baseball_data", stdout=first)
        counts = {name: model.objects.count() for name, model in RESOURCE_MODELS.items()}
        ids = {name: set(model.objects.values_list("pk", flat=True)) for name, model in RESOURCE_MODELS.items()}

        with tempfile.TemporaryDirectory() as temporary:
            reordered = Path(temporary) / "data"
            shutil.copytree(self.data_dir, reordered)
            prices = reordered / "preprocessed/구장티켓가격.csv"
            with prices.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            with prices.open("w", encoding="utf-8-sig", newline="") as stream:
                csv.writer(stream).writerows([rows[0], *reversed(rows[1:])])
            second = io.StringIO()
            call_command("import_baseball_data", data_dir=reordered, stdout=second)

        self.assertEqual(counts, {name: model.objects.count() for name, model in RESOURCE_MODELS.items()})
        self.assertEqual(ids, {name: set(model.objects.values_list("pk", flat=True)) for name, model in RESOURCE_MODELS.items()})
        self.assertFalse(json.loads(first.getvalue())["rejected"])
        self.assertEqual(19, len(counts))
        self.assertTrue(all(value > 0 for value in counts.values()))
        self.assertFalse(any(key.endswith(".imported") for key in json.loads(second.getvalue())["results"]))

    def test_existing_natural_key_is_preserved(self):
        Team.objects.create(id=7, team_code="LG", team_name_ko="관리자 수정값")
        Team.objects.create(id=8, team_code="USER", team_name_ko="사용자 데이터")
        call_command("import_baseball_data", stdout=io.StringIO())
        self.assertEqual("관리자 수정값", Team.objects.get(team_code="LG").team_name_ko)
        self.assertEqual(1, Team.objects.filter(team_code="LG").count())
        self.assertEqual("사용자 데이터", Team.objects.get(pk=8).team_name_ko)

    def test_hash_collision_fails_closed(self):
        Team.objects.create(id=stable_id(Team, "LG"), team_code="OTHER", team_name_ko="다른 데이터")
        with self.assertRaises(CommandError):
            call_command("import_baseball_data", stdout=io.StringIO())
        self.assertEqual(["OTHER"], list(Team.objects.values_list("team_code", flat=True)))

    def test_dry_run_reports_attempts_without_persisting(self):
        output = io.StringIO()
        call_command("import_baseball_data", dry_run=True, stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report["rolled_back"])
        self.assertGreater(report["totals"]["imported"], 0)
        self.assertEqual(0, report["totals"]["persisted"])
        self.assertTrue(all(not model.objects.exists() for model in RESOURCE_MODELS.values()))
        textual = next(
            item for item in report["provenance"]
            if item["source_file"] == "preprocessed/구장티켓가격.csv"
            and item["raw_values"].get("group_size") == "무료 대상 증빙 필요"
        )
        self.assertEqual("CONFIRMED", textual["status"])

    def test_unknown_boolean_rejects_and_rolls_back_every_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            shutil.copytree(self.data_dir, data_dir)
            zones = data_dir / "preprocessed/구장좌석구역.csv"
            with zones.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                fieldnames = reader.fieldnames
            rows[0]["accessible"] = "UNKNOWN"
            with zones.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            report_path = Path(temporary) / "report.json"
            with self.assertRaisesMessage(CommandError, "불리언이 아닌 값"):
                call_command("import_baseball_data", data_dir=data_dir, report=report_path, stdout=io.StringIO())

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, report["totals"]["rejected"])
            self.assertEqual(0, report["totals"]["persisted"])
            self.assertEqual("UNKNOWN", report["rejected"][0]["value"])
            self.assertTrue(all(not model.objects.exists() for model in RESOURCE_MODELS.values()))

    def test_unknown_group_size_rejects_and_rolls_back_every_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            shutil.copytree(self.data_dir, data_dir)
            prices = data_dir / "preprocessed/구장티켓가격.csv"
            with prices.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                fieldnames = reader.fieldnames
            rows[0]["group_size"] = "UNKNOWN"
            with prices.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            report_path = Path(temporary) / "report.json"
            with self.assertRaisesMessage(CommandError, "정수가 아닌 값"):
                call_command("import_baseball_data", data_dir=data_dir, report=report_path, stdout=io.StringIO())

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, report["totals"]["rejected"])
            self.assertEqual(0, report["totals"]["persisted"])
            self.assertEqual("UNKNOWN", report["rejected"][0]["value"])
            self.assertTrue(all(not model.objects.exists() for model in RESOURCE_MODELS.values()))
