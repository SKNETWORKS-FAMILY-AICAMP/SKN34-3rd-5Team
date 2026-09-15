import json
import uuid
from datetime import datetime
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.db import migrations


def seed_course_samples(apps, schema_editor):
    Course = apps.get_model("travel", "Course")
    CourseStop = apps.get_model("travel", "CourseStop")
    db_alias = schema_editor.connection.alias
    samples = json.loads((Path(__file__).parents[1] / "seed_data" / "course_samples_v1.json").read_text(encoding="utf-8"))

    for sample in samples:
        course, created = Course.objects.using(db_alias).get_or_create(
            source_id=sample["id"],
            defaults={
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"kbo-trip/course/{sample['id']}"),
                "title": sample["title"],
                "stadium": sample["stadium"],
                "description": sample["description"],
                "content": sample["content"],
                "content_format": sample.get("contentFormat", ""),
                "duration": sample["duration"],
                "cover": sample["cover"],
                "tags": sample["tags"],
                "author": sample["author"],
                "likes": sample["likes"],
                "views": sample.get("views", 0),
                "is_sample": True,
                "edit_token_hash": make_password(None),
            },
        )
        if not created:
            continue
        created_at = datetime.fromisoformat(sample["createdAt"])
        Course.objects.using(db_alias).filter(pk=course.pk).update(created_at=created_at, updated_at=created_at)
        CourseStop.objects.using(db_alias).bulk_create(
            CourseStop(
                course_id=course.pk,
                position=position,
                name=stop["name"],
                lat=stop["lat"],
                lng=stop["lng"],
                category=stop["category"],
                place_id=stop.get("placeId"),
                visit_id=stop.get("visitId"),
                address=stop.get("address"),
                tour_content_id=stop.get("tourContentId"),
                is_map_point=stop.get("isMapPoint"),
                is_drawn_point=stop.get("isDrawnPoint"),
            )
            for position, stop in enumerate(sample["stops"])
        )


class Migration(migrations.Migration):
    dependencies = [("travel", "0003_course_sample_fields")]
    operations = [migrations.RunPython(seed_course_samples, migrations.RunPython.noop)]
