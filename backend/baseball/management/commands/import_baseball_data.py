import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, transaction

from baseball.data_loader import BaseballDataLoaderV1, stable_id


class Command(BaseCommand):
    help = "저장소의 검증된 CSV를 야구 테이블에 신규 행만 적재합니다."

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", type=Path)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--report", type=Path)

    def handle(self, *args, **options):
        root = options["data_dir"] or Path(__file__).resolve().parents[4] / "data"
        loader = BaseballDataLoaderV1(apps, root, DEFAULT_DB_ALIAS)
        failure = None
        with transaction.atomic(using=DEFAULT_DB_ALIAS):
            try:
                report = loader.load()
            except Exception as error:
                failure = error
                report = loader.report()
            rolled_back = options["dry_run"] or failure is not None or bool(loader.rejections)
            if rolled_back:
                transaction.set_rollback(True, using=DEFAULT_DB_ALIAS)

        report["dry_run"] = options["dry_run"]
        report["rolled_back"] = rolled_back
        report["totals"]["rejected"] = len(loader.rejections)
        report["totals"]["persisted"] = 0 if rolled_back else report["totals"]["imported"]
        body = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        if options["report"]:
            options["report"].parent.mkdir(parents=True, exist_ok=True)
            options["report"].write_text(body + "\n", encoding="utf-8")
        self.stdout.write(body)
        if failure:
            if isinstance(failure, CommandError):
                raise failure
            raise CommandError(str(failure)) from failure
        if loader.rejections:
            raise CommandError(f"{len(loader.rejections)}개 행이 거부되어 전체 적재를 롤백했습니다")
