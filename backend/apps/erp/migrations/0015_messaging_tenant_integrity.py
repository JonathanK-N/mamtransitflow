import hashlib
from django.db import migrations

NAMES=['Conversation','ConversationParticipant','Message','MessageAttachment','GlobalNotification','NotificationPreference','PushSubscription']

def install(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':return
    quote=schema_editor.quote_name
    for name in ['Membership']+NAMES:
        table=apps.get_model('erp',name)._meta.db_table
        schema_editor.execute(f'ALTER TABLE {quote(table)} ADD CONSTRAINT {quote(table+"_tenant_identity")} UNIQUE (organization_id,id)')
    for name in NAMES:
        model=apps.get_model('erp',name)
        for field in model._meta.fields:
            related=getattr(field,'related_model',None)
            if related and any(f.name=='organization' for f in related._meta.fields):
                table=model._meta.db_table
                constraint='erp_tenant_fk_'+hashlib.sha256((table+field.name).encode()).hexdigest()[:16]
                schema_editor.execute(f'ALTER TABLE {quote(table)} ADD CONSTRAINT {quote(constraint)} FOREIGN KEY (organization_id,{quote(field.column)}) REFERENCES {quote(related._meta.db_table)} (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE')

def uninstall(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':return
    quote=schema_editor.quote_name
    for name in NAMES:
        model=apps.get_model('erp',name)
        for field in model._meta.fields:
            related=getattr(field,'related_model',None)
            if related and any(f.name=='organization' for f in related._meta.fields):
                constraint='erp_tenant_fk_'+hashlib.sha256((model._meta.db_table+field.name).encode()).hexdigest()[:16]
                schema_editor.execute(f'ALTER TABLE {quote(model._meta.db_table)} DROP CONSTRAINT {quote(constraint)}')
    for name in NAMES+['Membership']:
        table=apps.get_model('erp',name)._meta.db_table
        schema_editor.execute(f'ALTER TABLE {quote(table)} DROP CONSTRAINT {quote(table+"_tenant_identity")}')

class Migration(migrations.Migration):
    dependencies=[('erp','0014_conversation_conversationparticipant_and_more')]
    operations=[migrations.RunPython(install,uninstall)]
