"""Intégrité inter-entreprises PostgreSQL. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib
from django.db import migrations


def install(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':return
    models=[m for m in apps.get_app_config('erp').get_models() if any(f.name=='organization' for f in m._meta.fields) and m._meta.pk.get_internal_type()=='UUIDField']
    tables={m._meta.db_table for m in models}
    quote=schema_editor.quote_name
    for model in models:
        table=model._meta.db_table
        schema_editor.execute(f'ALTER TABLE {quote(table)} ADD CONSTRAINT {quote(table+"_tenant_identity")} UNIQUE (organization_id,id)')
    for model in models:
        for field in model._meta.fields:
            related=getattr(field,'related_model',None)
            if related and related._meta.db_table in tables:
                table=model._meta.db_table
                name='erp_tenant_fk_'+hashlib.sha256((table+field.name).encode()).hexdigest()[:16]
                schema_editor.execute(f'ALTER TABLE {quote(table)} ADD CONSTRAINT {quote(name)} FOREIGN KEY (organization_id,{quote(field.column)}) REFERENCES {quote(related._meta.db_table)} (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')


def uninstall(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':return
    models=[m for m in apps.get_app_config('erp').get_models() if any(f.name=='organization' for f in m._meta.fields) and m._meta.pk.get_internal_type()=='UUIDField']
    tables={m._meta.db_table for m in models};quote=schema_editor.quote_name
    for model in models:
        for field in model._meta.fields:
            related=getattr(field,'related_model',None)
            if related and related._meta.db_table in tables:
                name='erp_tenant_fk_'+hashlib.sha256((model._meta.db_table+field.name).encode()).hexdigest()[:16]
                schema_editor.execute(f'ALTER TABLE {quote(model._meta.db_table)} DROP CONSTRAINT {quote(name)}')
    for model in models:
        table=model._meta.db_table
        schema_editor.execute(f'ALTER TABLE {quote(table)} DROP CONSTRAINT {quote(table+"_tenant_identity")}')


class Migration(migrations.Migration):
    dependencies=[('erp','0001_initial')]
    operations=[migrations.RunPython(install,uninstall)]
