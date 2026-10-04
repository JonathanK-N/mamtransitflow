from django.db import migrations


RELATIONS = [('erp_document','customer_id','erp_partner'),
             ('erp_invoice','mission_id','erp_mission'),
             ('erp_transportorder','source_quote_id','erp_invoice'),
             ('erp_partnercontact','customer_id','erp_partner')]


def install(apps, editor):
    if editor.connection.vendor != 'postgresql':return
    editor.execute('ALTER TABLE erp_partnercontact ADD CONSTRAINT erp_partnercontact_tenant_identity UNIQUE (organization_id,id)')
    for table, column, target in RELATIONS:
        editor.execute(f'ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_crm_tenant FOREIGN KEY (organization_id,{column}) REFERENCES {target} (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')


def uninstall(apps, editor):
    if editor.connection.vendor != 'postgresql':return
    for table, column, target in reversed(RELATIONS):
        editor.execute(f'ALTER TABLE {table} DROP CONSTRAINT {table}_{column}_crm_tenant')
    editor.execute('ALTER TABLE erp_partnercontact DROP CONSTRAINT erp_partnercontact_tenant_identity')


class Migration(migrations.Migration):
    dependencies=[('erp','0018_document_customer_invoice_activity_and_more')]
    operations=[migrations.RunPython(install,uninstall)]
