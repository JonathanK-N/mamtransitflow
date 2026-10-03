import base64
from unittest.mock import patch
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from django.test import override_settings
from rest_framework.exceptions import ValidationError
from pywebpush import WebPushException
from apps.erp import models as m
from apps.erp.notifications import notify
from apps.erp.push import validated_subscription,process_pending
from .test_messaging import pair,conversation,send
from .test_workflows import env,mission

pytestmark=pytest.mark.django_db(transaction=True)


def subscription(endpoint='https://fcm.googleapis.com/fcm/send/test'):
    public=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    encode=lambda data:base64.urlsafe_b64encode(data).decode().rstrip('=')
    return {'endpoint':endpoint,'keys':{'p256dh':encode(public),'auth':encode(b'1234567890abcdef')}}


@pytest.mark.parametrize('endpoint',['http://127.0.0.1/private','https://169.254.169.254/secret','https://fcm.googleapis.com.evil.test/','https://fcm.googleapis.com:9999/test','https://user:pass@fcm.googleapis.com/test','https://fcm.googleapis.com:bad/test'])
def test_push_endpoint_ssrf_rejected(endpoint):
    with pytest.raises(ValidationError):validated_subscription(subscription(endpoint))


@override_settings(TF_VAPID_PUBLIC_KEY='public',TF_VAPID_PRIVATE_KEY='private',TF_REDIS_URL='')
def test_subscription_ownership_private_payload_and_invalid_cleanup(pair):
    data=subscription()
    response=pair['bc'].post('/api/v2/notifications/subscriptions',data,format='json');assert response.status_code==201,response.data
    assert pair['fc'].post('/api/v2/notifications/subscriptions',data,format='json').status_code==400
    pair['bc'].patch('/api/v2/notifications/preferences',{'push':True},format='json')
    identity=conversation(pair);send(pair,identity,body='Contenu privé')
    with patch('pywebpush.webpush') as push:
        assert process_pending()==1
        payload=push.call_args.kwargs['data'];assert 'Contenu privé' not in payload and 'Vous avez une nouvelle notification' in payload
    send(pair,identity)
    class Expired:status_code=410
    with patch('pywebpush.webpush',side_effect=WebPushException('Expired',response=Expired())):process_pending()
    assert not m.PushSubscription.objects.exists()


@override_settings(TF_VAPID_PUBLIC_KEY='public',TF_VAPID_PRIVATE_KEY='private',TF_REDIS_URL='')
def test_push_revoked_membership_and_disabled_preferences(pair):
    pair['bc'].post('/api/v2/notifications/subscriptions',subscription(),format='json')
    pair['bc'].patch('/api/v2/notifications/preferences',{'push':True},format='json')
    identity=conversation(pair);send(pair,identity);pair['bm'].active=False;pair['bm'].save()
    with patch('pywebpush.webpush') as push:process_pending();push.assert_not_called()


def test_mission_events_are_persistent_and_minor_changes_do_not_spam(pair):
    trip=mission(pair);row=m.Mission.objects.get(pk=trip['id'])
    first=m.GlobalNotification.objects.filter(category='missions').count();assert first>0
    row.notes='Note administrative';row.save();assert m.GlobalNotification.objects.filter(category='missions').count()==first
    row.status='cancelled';row.save();assert m.GlobalNotification.objects.filter(category='missions',title='Mission annulée').exists()


def test_notification_history_paginates_beyond_one_hundred(pair):
    for n in range(110):notify(pair['org'],pair['user'].pk,'test:'+str(n),'operations','Alerte','Test',{})
    first=pair['client'].get('/api/v2/notifications').data;last=pair['client'].get('/api/v2/notifications?page=5').data
    assert first['count']==110 and len(first['results'])==25 and len(last['results'])==10
