from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("llm", "0002_chat_models")]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="role",
            field=models.CharField(
                choices=[("human", "사용자"), ("ai", "AI")],
                default="human",
                max_length=10,
            ),
        ),
    ]
