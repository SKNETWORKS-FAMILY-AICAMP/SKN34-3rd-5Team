from datetime import date

from django.conf import settings
from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.db import connections


DEMO_PASSWORD = "DemoOnly123!"
DEMO_ADMIN_USERNAME = "sampleadmin"
DEMO_ADMIN_EMAIL = "sampleadmin@example.com"
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


def demo_users_enabled():
    return settings.DEBUG and settings.DEMO_USERS_ENABLED


def seed_demo_users(apps, schema_editor=None, using=None, **kwargs):
    if not demo_users_enabled():
        return

    alias = using or schema_editor.connection.alias
    try:
        User = apps.get_model("accounts", "CustomUser")
    except LookupError:
        return
    required_fields = {
        "username", "password", "email", "first_name", "birth_date", "gender",
        "nickname", "team_code", "is_staff", "is_superuser",
    }
    if not required_fields.issubset(field.name for field in User._meta.fields):
        return
    if schema_editor is None and User._meta.db_table not in connections[alias].introspection.table_names():
        return
    users = User.objects.using(alias)
    password = make_password(DEMO_PASSWORD)

    users.get_or_create(
        username=DEMO_ADMIN_USERNAME,
        defaults={
            "password": password,
            "email": DEMO_ADMIN_EMAIL,
            "first_name": "더미관리자",
            "is_staff": True,
            "is_superuser": True,
        },
    )
    for index, (name, nickname, team_code, gender) in enumerate(SAMPLE_USERS, 1):
        username = f"sampleuser{index:02d}"
        defaults = {
            "password": password,
            "email": f"{username}@example.com",
            "first_name": name,
            "birth_date": date(1990 + index, index, index),
            "gender": gender,
            "nickname": nickname,
            "team_code": team_code,
            "is_staff": False,
            "is_superuser": False,
        }
        user, created = users.get_or_create(username=username, defaults=defaults)
        if not created and not is_password_usable(user.password) and all(
            getattr(user, field) == value
            for field, value in defaults.items()
            if field not in {"password", "is_staff", "is_superuser"}
        ):
            users.filter(pk=user.pk).update(password=password)


def is_demo_identity(user):
    if not demo_users_enabled():
        return False
    if user.username == DEMO_ADMIN_USERNAME:
        matches_profile = user.email == DEMO_ADMIN_EMAIL and user.first_name == "더미관리자"
        return matches_profile and check_password(DEMO_PASSWORD, user.password)
    for index, (name, nickname, team_code, gender) in enumerate(SAMPLE_USERS, 1):
        if user.username == f"sampleuser{index:02d}":
            matches_profile = (
                user.email == f"sampleuser{index:02d}@example.com"
                and user.first_name == name
                and user.nickname == nickname
                and user.team_code == team_code
                and user.gender == gender
                and user.birth_date == date(1990 + index, index, index)
            )
            return matches_profile and check_password(DEMO_PASSWORD, user.password)
    return False
