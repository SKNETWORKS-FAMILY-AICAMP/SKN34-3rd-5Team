import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("community", "0004_community_rich_posts"), ("travel", "0005_course_content_doc")]

    operations = [migrations.AddField(
        model_name="communitypostimage", name="course",
        field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                related_name="images", to="travel.course"),
    )]
