from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0015_messaging_tenant_integrity'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='contact_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='Nom du contact'),
        ),
        migrations.AddField(
            model_name='teaminvitation',
            name='canceled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]