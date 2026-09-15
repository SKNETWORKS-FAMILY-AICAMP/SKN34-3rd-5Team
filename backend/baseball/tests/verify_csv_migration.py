"""Independently verify the real PostgreSQL CSV migration result."""

import csv
import json
import os
import re
from pathlib import Path

import django

if os.environ.get("DJANGO_SETTINGS_MODULE") != "baseball.tests.integration_settings":
    raise RuntimeError("run through run_postgres_integration.py")
django.setup()

from django.db import connection  # noqa: E402

from baseball.serializers import RESOURCE_MODELS  # noqa: E402


DATA = Path(__file__).resolve().parents[3] / "data"
REPORT = Path("/tmp/baseball-csv-migration-verification.json")


def rows(relative):
    with (DATA / relative).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def unique(items):
    return len(set(items))


def normalized_group_size(value):
    value = value.strip()
    if not value or value == "무료 대상 증빙 필요" or re.fullmatch(r"\d+(?:·\d+)+인", value):
        return None
    return int(float(value))


mapping = rows("raw/team_stadium_code_map.csv")
stadium_rows = rows("preprocessed/stadium_coordinates.csv")
zone_rows = rows("preprocessed/구장좌석구역.csv")
price_rows = rows("preprocessed/구장티켓가격.csv")
map_rows = rows("preprocessed/구장좌석도.csv")
scope_rows = rows("preprocessed/구장좌석경험.csv")
food_rows = rows("preprocessed/구장먹거리_공식매점.csv")
stadium_codes = {row["stadium_code"] for row in stadium_rows}

expected = {
    "teams": unique(row["team_code"] for row in mapping),
    "stadiums": len(stadium_codes),
    "home-contexts": unique(("2026", row["team_code"], row["stadium_code"]) for row in mapping if row["stadium_code"] in stadium_codes),
    "postseason-stages": unique(row["id"] for row in rows("preprocessed/kbo_schedule_postseason_tbd.csv")),
    "games": unique(row["id"] for row in rows("preprocessed/kbo_schedule_full.csv")),
    "standing-histories": unique((row["team_code"], row["snapshot_date"]) for row in rows("preprocessed/kbo_standing_history.csv")),
    "seat-zones": unique((row["season"], row["team_code"], row["stadium_code"], row["zone_code"]) for row in zone_rows),
    "ticket-prices": unique((row["season"], row["team_code"], row["stadium_code"], row["zone_code"], row["price_tier"], row["day_type"], row["customer_type"], normalized_group_size(row["group_size"]), int(row["price_krw"]), row["valid_from"] or None, row["valid_to"] or None, row["discount_condition"]) for row in price_rows),
    "ticket-policies": unique((row["id"], 1) for row in rows("preprocessed/kbo_ticket_policy_structured.csv")),
    "seat-maps": unique((row["season"], row["team_code"], row["stadium_code"], row["map_title"]) for row in map_rows),
    "seat-map-assets": unique((row["season"], row["team_code"], row["stadium_code"], row["map_title"], asset_no) for row in map_rows for asset_no, column in enumerate(("asset_url", "secondary_asset_url"), 1) if row[column]),
    "seat-scopes": unique((row["season"], row["team_code"], row["stadium_code"], row["scope_code"]) for row in scope_rows),
    "seat-views": unique((row["season"], row["team_code"], row["stadium_code"], row["scope_code"]) for row in scope_rows),
    "food-stores": unique(row["record_id"] for row in food_rows),
    "food-store-locations": unique((row["record_id"], 1) for row in food_rows if row["floor"] or row["zone_location"]),
    "food-store-menus": unique((row["record_id"], row["menu_category_official"]) for row in food_rows if row["menu_category_official"]),
    "transports": unique((row["stadium_code"], row["access_code"]) for row in rows("preprocessed/구장교통정보.csv")),
    "stadium-contents": unique(row["record_id"] for row in rows("preprocessed/구장부가콘텐츠_공식.csv")),
    "facilities": unique(row["record_id"] for row in rows("preprocessed/구장편의시설.csv")),
}
actual = {name: model.objects.count() for name, model in RESOURCE_MODELS.items()}
orphans = {}
with connection.cursor() as cursor:
    for resource, model in RESOURCE_MODELS.items():
        for field in model._meta.fields:
            if not field.is_relation:
                continue
            parent = field.remote_field.model
            quote = connection.ops.quote_name
            cursor.execute(
                f"SELECT COUNT(*) FROM {quote(model._meta.db_table)} child "
                f"LEFT JOIN {quote(parent._meta.db_table)} parent "
                f"ON child.{quote(field.column)} = parent.{quote(parent._meta.pk.column)} "
                f"WHERE child.{quote(field.column)} IS NOT NULL "
                f"AND parent.{quote(parent._meta.pk.column)} IS NULL"
            )
            orphans[f"{resource}.{field.name}"] = cursor.fetchone()[0]

report = {"expected": expected, "actual": actual, "fk_orphans": orphans}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert len(expected) == len(actual) == 19, report
assert actual == expected, report
assert all(count == 0 for count in orphans.values()), report
print(f"PASS: exact CSV counts and FK integrity verified; report={REPORT}")
