from django.db import migrations


def forward(apps,editor):
    invoice=apps.get_model('erp','Invoice')
    invoice.objects.filter(kind='quote',status='issued',quote_status='draft').update(quote_status='sent')
    invoice.objects.filter(kind='quote',status='cancelled',quote_status='draft').update(quote_status='refused')


class Migration(migrations.Migration):
    dependencies=[('erp','0022_auditevent_erp_client_audit_lookup_and_more')]
    operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
