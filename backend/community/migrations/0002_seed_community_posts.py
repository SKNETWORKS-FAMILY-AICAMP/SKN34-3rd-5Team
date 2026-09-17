import json
from pathlib import Path

from django.db import migrations, transaction


def seed_community_posts(apps, schema_editor):
    CommunityPost = apps.get_model("community", "CommunityPost")
    alias = schema_editor.connection.alias
    records = json.loads(Path(__file__).with_name("data").joinpath("community_posts_v1.json").read_text(encoding="utf-8"))
    with transaction.atomic(using=alias):
        for record in records:
            CommunityPost.objects.using(alias).get_or_create(
                source_id=record["sourceId"],
                defaults={
                    "post_number": record["postNumber"],
                    "board": record["board"],
                    "team_code": record["teamCode"],
                    "author": record["author"],
                    "title": record["title"],
                    "content": record["content"],
                    "category": record["category"],
                    "created_at": record["createdAt"],
                    "views": record["views"],
                    "recommendations": record["recommendations"],
                    "comment_count": record["commentCount"],
                    "is_sample": record["isSample"],
                },
            )


class Migration(migrations.Migration):
    dependencies = [("community", "0001_initial")]
    # Seed rows can become user-edited content, so rollback intentionally preserves them.
    operations = [migrations.RunPython(seed_community_posts, migrations.RunPython.noop)]
