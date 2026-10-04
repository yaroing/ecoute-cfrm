from django.db import migrations


def protect(apps, schema_editor):
    if schema_editor.connection.alias != "default":
        return
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(
            "CREATE TRIGGER audit_no_update BEFORE UPDATE ON core_audit BEGIN SELECT RAISE(ABORT, 'Audit immutable'); END"
        )
        schema_editor.execute(
            "CREATE TRIGGER audit_no_delete BEFORE DELETE ON core_audit BEGIN SELECT RAISE(ABORT, 'Audit immutable'); END"
        )
    else:
        schema_editor.execute(
            "CREATE FUNCTION audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit immutable'; END; $$"
        )
        schema_editor.execute(
            "CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON core_audit FOR EACH ROW EXECUTE FUNCTION audit_immutable()"
        )


def unprotect(apps, schema_editor):
    if schema_editor.connection.alias != "default":
        return
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS audit_no_update")
        schema_editor.execute("DROP TRIGGER IF EXISTS audit_no_delete")
    else:
        schema_editor.execute("DROP TRIGGER IF EXISTS audit_immutable ON core_audit")
        schema_editor.execute("DROP FUNCTION IF EXISTS audit_immutable()")


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(protect, unprotect)]
