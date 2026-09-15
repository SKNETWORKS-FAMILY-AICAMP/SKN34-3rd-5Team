import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("community", "0003_community_post_api"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunityDraft",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("board", models.CharField(choices=(("free", "free"), ("teams", "teams")), max_length=8)),
                ("team_code", models.CharField(blank=True, default="", max_length=2)),
                ("category", models.CharField(blank=True, default="", max_length=20)),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("content", models.TextField(blank=True, default="", max_length=20000)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="community_drafts", to=settings.AUTH_USER_MODEL)),
                ("published_post", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="source_drafts", to="community.communitypost")),
            ],
            options={
                "constraints": (
                    models.CheckConstraint(condition=Q(board="free", team_code="") | Q(board="teams", team_code__in=("LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO")), name="community_draft_board_team_valid"),
                    models.CheckConstraint(condition=Q(revision__gte=1), name="community_draft_revision_valid"),
                ),
            },
        ),
        migrations.CreateModel(
            name="CommunityImage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_key", models.CharField(max_length=255, unique=True)),
                ("content_type", models.CharField(max_length=20)),
                ("size", models.PositiveIntegerField()),
                ("width", models.PositiveIntegerField()),
                ("height", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("draft", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="images", to="community.communitydraft")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="community_images", to=settings.AUTH_USER_MODEL)),
                ("post", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="images", to="community.communitypost")),
            ],
            options={
                "ordering": ("created_at", "id"),
                "constraints": (
                    models.CheckConstraint(condition=Q(draft__isnull=True) | Q(post__isnull=True), name="community_image_single_target"),
                ),
            },
        ),
    ]
