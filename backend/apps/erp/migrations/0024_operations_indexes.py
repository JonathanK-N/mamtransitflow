from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('erp','0023_existing_quote_states')]
    operations=[
        migrations.AddIndex(model_name='mission',index=models.Index(fields=['organization','status','departure'],name='erp_ops_mission_departure')),
        migrations.AddIndex(model_name='mission',index=models.Index(fields=['organization','driver','departure','arrival'],name='erp_ops_driver_schedule')),
        migrations.AddIndex(model_name='mission',index=models.Index(fields=['organization','vehicle','departure','arrival'],name='erp_ops_vehicle_schedule')),
    ]
