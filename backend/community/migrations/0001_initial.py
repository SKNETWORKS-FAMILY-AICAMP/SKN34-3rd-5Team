from django.db import migrations, models
from django.db.models import Q


TEAM_CODES = ("LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO")


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="CommunityPost",
            fields=[
                ("source_id", models.CharField(max_length=40, primary_key=True, serialize=False)),
                ("post_number", models.CharField(max_length=6, unique=True)),
                ("board", models.CharField(choices=(("free", "free"), ("teams", "teams")), max_length=8)),
                ("team_code", models.CharField(blank=True, max_length=2)),
                ("author", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=200)),
                ("content", models.TextField()),
                ("category", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("views", models.PositiveIntegerField(default=0)),
                ("recommendations", models.PositiveIntegerField(default=0)),
                ("comment_count", models.PositiveIntegerField(default=0)),
                ("is_sample", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ("post_number",),
                "constraints": [models.CheckConstraint(condition=Q(board="free", team_code="") | Q(board="teams", team_code__in=TEAM_CODES), name="community_post_board_team_valid")],
            },
        ),
    ]
