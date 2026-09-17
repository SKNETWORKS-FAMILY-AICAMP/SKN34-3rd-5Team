class BaseballDatabaseRouter:
    def allow_migrate(self, db, app_label, **hints):
        if db == "baseball_readonly":
            return False
        return None
