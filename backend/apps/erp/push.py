import base64
import hashlib
import json
from datetime import timedelta
from urllib.parse import urlparse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from . import models as m
from .views import ScopedView
from .notifications import visible_notifications

PUSH_HOSTS=('fcm.googleapis.com','updates.push.services.mozilla.com','push.services.mozilla.com','web.push.apple.com')


def validated_subscription(value):
    if not isinstance(value,dict):raise serializers.ValidationError('Abonnement invalide.')
    endpoint=value.get('endpoint','')
    if not isinstance(endpoint,str) or len(endpoint)>2048:raise serializers.ValidationError('Destination push invalide.')
    try:
        url=urlparse(endpoint);port=url.port
    except ValueError:raise serializers.ValidationError('Destination push invalide.')
    if url.scheme!='https' or url.username or url.password or port not in (None,443) or url.fragment or url.hostname not in PUSH_HOSTS:
        raise serializers.ValidationError('Service push non autorisé.')
    keys=value.get('keys',{})
    if not isinstance(keys,dict) or any(not isinstance(keys.get(name),str) or len(keys[name])>128 for name in ('p256dh','auth')):
        raise serializers.ValidationError('Clés push invalides.')
    try:
        p256dh=base64.urlsafe_b64decode(keys['p256dh']+'='*(-len(keys['p256dh'])%4))
        auth=base64.urlsafe_b64decode(keys['auth']+'='*(-len(keys['auth'])%4))
        from cryptography.hazmat.primitives.asymmetric import ec
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),p256dh)
        if len(auth)!=16:raise ValueError()
    except Exception:raise serializers.ValidationError('Clés push invalides.')
    return {'endpoint':endpoint,'keys':{'p256dh':keys['p256dh'],'auth':keys['auth']}}


class PushSubscriptionsView(ScopedView):
    def post(self,request):
        if not settings.TF_VAPID_PUBLIC_KEY or not settings.TF_VAPID_PRIVATE_KEY:raise serializers.ValidationError('Push non configuré sur le serveur.')
        data=validated_subscription(request.data)
        identity=hashlib.sha256(data['endpoint'].encode()).hexdigest()
        existing=m.PushSubscription.objects.filter(endpoint_hash=identity).first()
        if not existing and m.PushSubscription.objects.filter(organization=self.org,user=request.user).count()>=10:
            raise serializers.ValidationError('Dix appareils maximum. Supprimez un ancien abonnement.')
        if existing and (existing.user_id!=request.user.pk or existing.organization_id!=self.org.pk):
            raise serializers.ValidationError('Désactivez les notifications du compte précédent sur cet appareil avant de les activer ici.')
        row,_=m.PushSubscription.objects.update_or_create(endpoint_hash=identity,
            defaults={'user':request.user,'organization':self.org,'subscription':data})
        return Response({'id':str(row.pk)},status=201)
    def delete(self,request):
        endpoint=serializers.CharField(max_length=2048).run_validation(request.data.get('endpoint'))
        m.PushSubscription.objects.filter(organization=self.org,user=request.user,
            endpoint_hash=hashlib.sha256(endpoint.encode()).hexdigest()).delete()
        return Response(status=204)


def process_pending(limit=20):
    if not settings.TF_VAPID_PRIVATE_KEY:return 0
    from pywebpush import webpush, WebPushException
    count=0
    candidates=list(m.GlobalNotification.objects.filter(push_pending=True,push_after__lte=timezone.now()).order_by('push_after').values_list('pk',flat=True)[:limit])
    for identity in candidates:
        with transaction.atomic():
            row=m.GlobalNotification.objects.select_for_update(skip_locked=True).filter(pk=identity,push_pending=True).first()
            if not row:continue
            member=m.Membership.objects.select_related('organization','user').filter(organization=row.organization,user=row.user,active=True,user__is_active=True).first()
            preference=m.NotificationPreference.objects.filter(organization=row.organization,user=row.user,push=True).first()
            if not member or not preference or not getattr(preference,row.category,True) or row.read_at or not visible_notifications(member).filter(pk=row.pk).exists():
                row.push_pending=False;row.save(update_fields=['push_pending']);continue
            visible=False
            if settings.TF_REDIS_URL:
                import redis
                client=redis.from_url(settings.TF_REDIS_URL,socket_connect_timeout=2,socket_timeout=2)
                from .realtime import group
                try:visible=bool(client.exists('tf.active.'+group(row.organization_id,row.user_id)))
                except Exception:pass
                finally:client.close()
            if visible:
                row.push_pending=False;row.save(update_fields=['push_pending']);continue
            payload={'id':str(row.pk),'title':'TransitFlow','body':'Vous avez une nouvelle notification.',
                'url':'/app#notifications','organization':str(row.organization_id),'user':row.user_id,'context':row.context}
            if preference.preview:
                payload.update(title='TransitFlow — '+row.title,body=row.body)
                if row.category=='messages':
                    message=m.Message.objects.filter(organization=row.organization,pk=row.context.get('message')).select_related('sender__user').first()
                    if message:payload.update(title='TransitFlow — '+message.sender.user.nom,body=message.body[:160] or 'Pièce jointe')
            retry=False
            for sub in m.PushSubscription.objects.filter(organization=row.organization,user=row.user):
                try:
                    webpush(subscription_info=sub.subscription,data=json.dumps(payload),vapid_private_key=settings.TF_VAPID_PRIVATE_KEY,
                        vapid_claims={'sub':settings.TF_VAPID_SUBJECT},ttl=300,timeout=5)
                except WebPushException as exc:
                    if exc.response is not None and exc.response.status_code in (404,410):sub.delete()
                    else:retry=True
                except Exception:retry=True
            row.push_attempts+=1;row.push_pending=retry and row.push_attempts<5
            row.push_after=timezone.now()+timedelta(seconds=min(3600,30*2**row.push_attempts))
            row.save(update_fields=['push_pending','push_attempts','push_after']);count+=1
    return count
