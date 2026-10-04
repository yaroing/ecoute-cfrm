class SensitiveRouter:
    def db_for_read(self, model, **hints):
        return "sensible" if model._meta.app_label == "sensible" else "default"

    db_for_write = db_for_read

    def allow_migrate(self, db, app_label, **hints):
        return (app_label == "sensible") == (db == "sensible")
