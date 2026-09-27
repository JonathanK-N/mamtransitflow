"""Intégrité des rattachements clients. Auteur : Jonathan Kakesa (JonathanK-N)."""
from django.db import migrations

def install(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':return
    schema_editor.execute('ALTER TABLE erp_portalaccess ADD CONSTRAINT erp_portalaccess_tenant_identity UNIQUE (organization_id,id)')
    schema_editor.execute('ALTER TABLE erp_portalaccess ADD CONSTRAINT erp_portal_partner_tenant FOREIGN KEY (organization_id,partner_id) REFERENCES erp_partner (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')
    schema_editor.execute('ALTER TABLE erp_teaminvitation ADD CONSTRAINT erp_invite_partner_tenant FOREIGN KEY (organization_id,partner_id) REFERENCES erp_partner (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')

def uninstall(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':return
    schema_editor.execute('ALTER TABLE erp_teaminvitation DROP CONSTRAINT erp_invite_partner_tenant')
    schema_editor.execute('ALTER TABLE erp_portalaccess DROP CONSTRAINT erp_portal_partner_tenant')
    schema_editor.execute('ALTER TABLE erp_portalaccess DROP CONSTRAINT erp_portalaccess_tenant_identity')

class Migration(migrations.Migration):
    dependencies=[('erp','0010_document_shared_with_customer_teaminvitation_partner_and_more')]
    operations=[migrations.RunPython(install,uninstall)]
