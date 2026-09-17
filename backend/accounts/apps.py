from django.apps import AppConfig


def ensure_demo_users(sender, using, apps=None, **kwargs):
    from django.apps import apps as django_apps

    from .demo_users import seed_demo_users

    seed_demo_users(apps or django_apps, using=using)


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(ensure_demo_users, sender=self, dispatch_uid="accounts.demo_users")
