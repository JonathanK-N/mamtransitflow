from django.db import transaction
from django.db.models.signals import post_save,post_delete
from django.dispatch import receiver
from . import models as m
from .realtime import publish

WATCHED={m.Mission,m.TransportOrder,m.Employee,m.Vehicle,m.Incident,m.Maintenance,m.LeaveRequest,m.DeliveryReceipt}
GPS_FIELDS={'tracking_status','tracking_lost_at','tracking_started_at','tracking_ended_at','updated_at'}


@receiver(post_save)
@receiver(post_delete)
def operations_changed(sender,instance,**kwargs):
    if sender not in WATCHED or kwargs.get('raw'):return
    fields=kwargs.get('update_fields')
    if sender is m.Mission and fields and set(fields)<=GPS_FIELDS:return
    organization=instance.organization_id
    def broadcast():
        users=list(m.Membership.objects.filter(organization_id=organization,active=True,user__is_active=True,role__in=['owner','admin','operations']).values_list('user_id',flat=True))
        publish(organization,users,'operations')
    transaction.on_commit(broadcast)
