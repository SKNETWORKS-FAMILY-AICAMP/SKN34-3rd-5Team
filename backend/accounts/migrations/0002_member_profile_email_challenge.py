import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.AddField(model_name="customuser", name="avatar", field=models.TextField(blank=True)),
        migrations.AddField(model_name="customuser", name="nickname", field=models.CharField(blank=True, max_length=12)),
        migrations.AddField(model_name="customuser", name="nickname_changed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="customuser", name="notifications", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="customuser", name="team_code", field=models.CharField(blank=True, max_length=2)),
        migrations.AddField(model_name="customuser", name="visibility", field=models.JSONField(blank=True, default=dict)),
        migrations.CreateModel(
            name="EmailChangeChallenge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                ("code_hash", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.customuser")),
            ],
        ),
    ]
