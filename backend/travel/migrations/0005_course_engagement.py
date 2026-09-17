import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import travel.models


CREATE_ROUTE_NUMBER_SEQUENCE = """
CREATE SEQUENCE travel_route_number_seq MINVALUE 1 MAXVALUE 999999 NO CYCLE;
"""


def assign_route_numbers(apps, schema_editor):
    Course = apps.get_model("travel", "Course")
    db_alias = schema_editor.connection.alias
    for course in Course.objects.using(db_alias).order_by("created_at", "source_id", "id"):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("SELECT nextval('travel_route_number_seq')")
            number = cursor.fetchone()[0]
        Course.objects.using(db_alias).filter(pk=course.pk).update(route_number=f"{number:06d}")


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("travel", "0004_seed_course_samples")]

    operations = [
        migrations.RunSQL(CREATE_ROUTE_NUMBER_SEQUENCE, "DROP SEQUENCE IF EXISTS travel_route_number_seq"),
        migrations.AddField(
            model_name="course",
            name="route_number",
            field=models.CharField(blank=True, max_length=6, null=True, unique=True),
        ),
        migrations.RunPython(assign_route_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="course",
            name="route_number",
            field=models.CharField(default=travel.models.next_route_number, editable=False, max_length=6, unique=True),
        ),
        migrations.CreateModel(
            name="CourseReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="travel.course")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="course_reactions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="coursereaction",
            constraint=models.UniqueConstraint(fields=("course", "user"), name="course_reaction_user_unique"),
        ),
        migrations.CreateModel(
            name="CourseView",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_digest", models.CharField(max_length=64)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="viewer_records", to="travel.course")),
            ],
        ),
        migrations.AddConstraint(
            model_name="courseview",
            constraint=models.UniqueConstraint(fields=("course", "actor_digest"), name="course_view_actor_unique"),
        ),
    ]
