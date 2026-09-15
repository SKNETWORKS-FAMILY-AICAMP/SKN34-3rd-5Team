from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("travel", "0002_course_course_start_lat_bounds_and_more")]
    operations = [
        migrations.AddField(model_name="course", name="source_id", field=models.CharField(blank=True, max_length=80, null=True, unique=True)),
        migrations.AddField(model_name="course", name="description", field=models.TextField(blank=True)),
        migrations.AddField(model_name="course", name="cover", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="course", name="likes", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="course", name="views", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="course", name="is_sample", field=models.BooleanField(default=False)),
    ]
