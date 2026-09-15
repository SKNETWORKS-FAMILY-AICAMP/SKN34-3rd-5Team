import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("community", "0003_community_post_api"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="communitypost",
            name="content_doc",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="CommunityPostImage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file", models.ImageField(upload_to="community/images/%Y/%m/")),
                ("mime_type", models.CharField(max_length=16)),
                ("byte_size", models.PositiveIntegerField()),
                ("width", models.PositiveIntegerField()),
                ("height", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="community_images", to=settings.AUTH_USER_MODEL)),
                ("post", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="images", to="community.communitypost")),
            ],
        ),
    ]
