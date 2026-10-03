from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from . import models as m, security
from .notifications import notify
from .messaging import mission_allowed

IMPORTANT={m.Mission:['driver_id','status','departure','origin','destination'],
    m.Incident:['severity','status'],m.Maintenance:['status','due_date','due_mileage'],m.Document:['expiry','title']}


@receiver(pre_save)
def previous_state(sender,instance,**kwargs):
    if sender not in IMPORTANT or kwargs.get('raw'):return
    instance._notification_previous=sender.objects.filter(pk=instance.pk).values(*IMPORTANT[sender]).first()


@receiver(post_save)
def business_notification(sender,instance,created,**kwargs):
    if sender not in IMPORTANT or kwargs.get('raw'):return
    previous=getattr(instance,'_notification_previous',None)
    fields=IMPORTANT[sender]
    if not created and previous and all(previous[name]==getattr(instance,name) for name in fields):return
    org=instance.organization
    members=m.Membership.objects.filter(organization=org,active=True,user__is_active=True).select_related('user','organization')
    if sender is m.Mission:
        category='missions';module='missions'
        title='Nouvelle mission assignée' if created or previous and previous['driver_id']!=instance.driver_id else 'Mission annulée' if instance.status=='cancelled' else 'Mission modifiée'
        body='Mission '+instance.reference
        members=[member for member in members if mission_allowed(member,instance)]
    else:
        category='operations';module={m.Incident:'incidents',m.Maintenance:'maintenance',m.Document:'documents'}[sender]
        title={m.Incident:'Nouvel incident' if created else 'Incident actualisé',m.Maintenance:'Intervention atelier',m.Document:'Document important'}[sender]
        body=instance.title
        members=[member for member in members if security.allowed(member.role,module)
            and (member.role!='driver' or sender is m.Document and instance.mission_id and instance.mission.driver.user_id==member.user_id and instance.category!='finance')]
    context={'module':module,'id':str(instance.pk),'legacy_identity':str(instance.pk),'legacy_version':str(instance.updated_at)}
    for member in members:
        notify(org,member.user_id,f'{module}:{instance.pk}:{instance.updated_at.isoformat()}',category,title,body,context)
