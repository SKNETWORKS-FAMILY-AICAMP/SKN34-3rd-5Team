from django.db import migrations

from accounts.demo_users import seed_demo_users


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_add_sample_users")]
    operations = [migrations.RunPython(seed_demo_users, migrations.RunPython.noop)]
