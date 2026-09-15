from pathlib import Path

from django.db import migrations

from baseball.data_loader import BaseballDataLoaderV1


def load_csv_data(apps, schema_editor):
    data_dir = Path(__file__).resolve().parents[3] / "data"
    BaseballDataLoaderV1(apps, data_dir, schema_editor.connection.alias).load()


class Migration(migrations.Migration):
    dependencies = [("baseball", "0001_initial")]
    operations = [migrations.RunPython(load_csv_data, migrations.RunPython.noop)]
