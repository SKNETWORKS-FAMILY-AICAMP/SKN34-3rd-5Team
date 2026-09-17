from datetime import date

from django.contrib.auth.hashers import make_password
from django.db import migrations


SAMPLE_USERS = (
    ("김민준", "야구팬민준", "LG", "M"),
    ("이서연", "야구팬서연", "HH", "F"),
    ("박지훈", "야구팬지훈", "SK", "M"),
    ("최하은", "야구팬하은", "SS", "F"),
    ("정도윤", "야구팬도윤", "NC", "M"),
    ("강지우", "야구팬지우", "KT", "F"),
    ("조현우", "야구팬현우", "LT", "M"),
    ("윤서아", "야구팬서아", "HT", "F"),
    ("장준서", "야구팬준서", "OB", "M"),
    ("임수빈", "야구팬수빈", "WO", "F"),
)


def add_sample_users(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    users = User.objects.using(schema_editor.connection.alias)

    for index, (name, nickname, team_code, gender) in enumerate(SAMPLE_USERS, 1):
        users.get_or_create(
            username=f"sampleuser{index:02d}",
            defaults={
                "password": make_password(None),
                "email": f"sampleuser{index:02d}@example.com",
                "first_name": name,
                "birth_date": date(1990 + index, index, index),
                "gender": gender,
                "nickname": nickname,
                "team_code": team_code,
                "is_staff": False,
                "is_superuser": False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_member_profile_email_challenge")]
    # Reverse is intentionally a no-op: sample usernames may preexist or be edited later.
    operations = [migrations.RunPython(add_sample_users, migrations.RunPython.noop)]
