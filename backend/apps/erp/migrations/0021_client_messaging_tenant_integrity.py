from django.db import migrations


def install(apps,editor):
    if editor.connection.vendor!='postgresql':return
    editor.execute('ALTER TABLE erp_clientconversation ADD CONSTRAINT erp_clientconversation_tenant_identity UNIQUE (organization_id,id)')
    editor.execute('ALTER TABLE erp_clientconversation ADD CONSTRAINT erp_clientconversation_access_tenant FOREIGN KEY (organization_id,access_id) REFERENCES erp_portalaccess (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')
    editor.execute('ALTER TABLE erp_clientmessage ADD CONSTRAINT erp_clientmessage_conversation_tenant FOREIGN KEY (organization_id,conversation_id) REFERENCES erp_clientconversation (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')


def uninstall(apps,editor):
    if editor.connection.vendor!='postgresql':return
    editor.execute('ALTER TABLE erp_clientmessage DROP CONSTRAINT erp_clientmessage_conversation_tenant')
    editor.execute('ALTER TABLE erp_clientconversation DROP CONSTRAINT erp_clientconversation_access_tenant')
    editor.execute('ALTER TABLE erp_clientconversation DROP CONSTRAINT erp_clientconversation_tenant_identity')


class Migration(migrations.Migration):
    dependencies=[('erp','0020_clientconversation_clientmessage')]
    operations=[migrations.RunPython(install,uninstall)]
