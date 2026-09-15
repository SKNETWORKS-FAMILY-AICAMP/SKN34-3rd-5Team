import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=80)),
                ("stadium", models.CharField(max_length=120)),
                ("content", models.TextField(blank=True)),
                ("content_format", models.CharField(blank=True, max_length=16)),
                ("duration", models.CharField(max_length=80)),
                ("tags", models.JSONField(default=list)),
                ("start_lat", models.FloatField(blank=True, null=True)),
                ("start_lng", models.FloatField(blank=True, null=True)),
                ("author", models.CharField(default="익명", max_length=80)),
                ("edit_token_hash", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-created_at",),
                "constraints": [models.CheckConstraint(condition=models.Q(models.Q(("start_lat__isnull", True), ("start_lng__isnull", True)), models.Q(("start_lat__isnull", False), ("start_lng__isnull", False)), _connector="OR"), name="course_start_coordinates_paired")],
            },
        ),
        migrations.CreateModel(
            name="CourseStop",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveSmallIntegerField()),
                ("name", models.CharField(max_length=255)),
                ("lat", models.FloatField()),
                ("lng", models.FloatField()),
                ("category", models.CharField(max_length=120)),
                ("place_id", models.CharField(blank=True, max_length=255, null=True)),
                ("visit_id", models.CharField(blank=True, max_length=255, null=True)),
                ("address", models.CharField(blank=True, max_length=500, null=True)),
                ("tour_content_id", models.CharField(blank=True, max_length=255, null=True)),
                ("is_map_point", models.BooleanField(blank=True, null=True)),
                ("is_drawn_point", models.BooleanField(blank=True, null=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stops", to="travel.course")),
            ],
            options={
                "ordering": ("position",),
                "constraints": [models.UniqueConstraint(fields=("course", "position"), name="unique_course_stop_position")],
            },
        ),
    ]
