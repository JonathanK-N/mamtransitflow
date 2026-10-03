import asyncio
import uuid
import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.comptes.models import Utilisateur
from apps.erp import models as m
from .test_workflows import env, mission

pytestmark=pytest.mark.django_db(transaction=True)
BASE='/api/v2/messaging/'


@pytest.fixture
def pair(env):
    user=Utilisateur.objects.create_user(courriel='dispatch@example.test',nom='Exploitation',mot_de_passe='Long-password-938!')
    member=m.Membership.objects.create(organization=env['org'],user=user,role='operations')
    client=APIClient();client.force_authenticate(user);client.credentials(HTTP_X_ORGANIZATION=str(env['org'].pk))
    outsider=Utilisateur.objects.create_user(courriel='foreign@example.test',nom='Autre société',mot_de_passe='Long-password-938!')
    foreign=m.Membership.objects.create(organization=env['other'],user=outsider,role='owner')
    third=APIClient();third.force_authenticate(outsider);third.credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    return env|dict(b=user,bm=member,bc=client,foreign=foreign,fc=third)


def conversation(pair,**extra):
    response=pair['client'].post(BASE+'conversations',{'kind':'direct','participants':[pair['bm'].pk],**extra},format='json')
    assert response.status_code in (200,201),response.data
    return response.data['id']


def send(pair,identity,client=None,**extra):
    return (client or pair['client']).post(BASE+f'conversations/{identity}/messages',{'body':'Bonjour équipe','client_id':str(uuid.uuid4()),**extra},format='json')


def test_persistent_direct_pair_reuse_and_unread(pair):
    identity=conversation(pair);assert conversation(pair)==identity
    response=send(pair,identity);assert response.status_code==201,response.data
    assert pair['bc'].get(BASE+'conversations').data['unread']==1
    history=pair['bc'].get(BASE+f'conversations/{identity}/messages').data['results']
    assert history[0]['body']=='Bonjour équipe' and history[0]['sequence']==1
    assert pair['bc'].post(BASE+f'conversations/{identity}/read',{'sequence':1},format='json').status_code==200
    assert pair['bc'].get(BASE+'conversations').data['unread']==0
    assert pair['client'].get(BASE+f'conversations/{identity}/messages').data['results'][0]['readers']==['Exploitation']


def test_retry_is_idempotent_and_conflicting_body_rejected(pair):
    identity=conversation(pair);key=str(uuid.uuid4())
    first=send(pair,identity,client_id=key);second=send(pair,identity,client_id=key)
    assert first.data['id']==second.data['id'] and m.Message.objects.count()==1
    assert send(pair,identity,client_id=key,body='Autre contenu').status_code==400


@pytest.mark.parametrize('action',['history','detail','send','read','add'])
def test_foreign_conversation_ids_are_not_disclosed(pair,action):
    identity=conversation(pair);client=pair['fc']
    if action=='history':r=client.get(BASE+f'conversations/{identity}/messages')
    elif action=='detail':r=client.get(BASE+f'conversations/{identity}')
    elif action=='send':r=send(pair,identity,client)
    elif action=='read':r=client.post(BASE+f'conversations/{identity}/read',{'sequence':0},format='json')
    else:r=client.patch(BASE+f'conversations/{identity}',{'add':pair['foreign'].pk},format='json')
    assert r.status_code==404,r.data
    assert pair['fc'].get(BASE+'collaborators').data['results']==[]


def test_organization_header_and_external_participant_rejected(pair):
    assert pair['client'].post(BASE+'conversations',{'kind':'direct','participants':[pair['foreign'].pk]},format='json').status_code==400
    identity=conversation(pair)
    pair['client'].credentials(HTTP_X_ORGANIZATION=str(pair['other'].pk))
    assert pair['client'].get(BASE+f'conversations/{identity}').status_code==403
    m.Membership.objects.create(organization=pair['other'],user=pair['user'],role='owner')
    assert pair['client'].get(BASE+f'conversations/{identity}').status_code==404


def test_disabled_member_loses_all_access(pair):
    identity=conversation(pair);pair['bm'].active=False;pair['bm'].save()
    assert send(pair,identity,pair['bc']).status_code==403
    assert pair['bc'].get(BASE+'collaborators').status_code==403


def test_group_management_and_removal(pair):
    identity=conversation(pair,kind='group',title='Exploitation')
    assert pair['bc'].patch(BASE+f'conversations/{identity}',{'title':'Interdit'},format='json').status_code==403
    assert pair['client'].patch(BASE+f'conversations/{identity}',{'add':pair['foreign'].pk},format='json').status_code==404
    assert pair['client'].patch(BASE+f'conversations/{identity}',{'remove':pair['bm'].pk},format='json').status_code==200
    assert pair['bc'].get(BASE+f'conversations/{identity}/messages').status_code==404
    assert pair['bc'].get('/api/v2/notifications').data['results']==[]


def test_mission_requires_business_permissions_even_as_participant(pair):
    trip=mission(pair);pair['driver'].user=pair['b'];pair['driver'].save();pair['bm'].role='driver';pair['bm'].save()
    identity=conversation(pair,kind='mission',mission=trip['id'])
    assert pair['bc'].get(BASE+f'conversations/{identity}').status_code==200
    pair['driver'].user=None;pair['driver'].save()
    assert pair['bc'].get(BASE+f'conversations/{identity}').status_code==404
    assert pair['bc'].post(BASE+'conversations',{'kind':'mission','mission':trip['id']},format='json').status_code==404


def test_attachment_validation_private_download_and_archive(pair,tmp_path):
    identity=conversation(pair)
    with override_settings(MEDIA_ROOT=tmp_path):
        pdf=SimpleUploadedFile('preuve.pdf',b'%PDF-1.4\npreuve',content_type='application/pdf')
        response=pair['client'].post(BASE+f'conversations/{identity}/messages',{'body':'Preuve','client_id':str(uuid.uuid4()),'file':pdf},format='multipart')
        assert response.status_code==201,response.data
        attachment=response.data['attachments'][0]['id']
        own=pair['bc'].get(BASE+f'attachments/{attachment}');assert own.status_code==200 and own['Cache-Control']=='no-store';own.close()
        assert pair['fc'].get(BASE+f'attachments/{attachment}').status_code==404
        for name,contents,mime in [('bad.pdf',b'javascript','application/pdf'),('bad.html',b'%PDF-','text/html'),('bad.png',b'\x89PNG\r\n\x1a\n','text/html')]:
            bad=SimpleUploadedFile(name,contents,content_type=mime)
            assert pair['client'].post(BASE+f'conversations/{identity}/messages',{'body':'','client_id':str(uuid.uuid4()),'file':bad},format='multipart').status_code==400


def test_cursor_pagination_and_read_is_monotonic(pair):
    identity=conversation(pair);row=m.Conversation.objects.get(pk=identity)
    m.Message.objects.bulk_create([m.Message(organization=pair['org'],conversation=row,sender=pair['member'],sequence=n,client_id=uuid.uuid4(),body=str(n)) for n in range(1,61)])
    row.last_sequence=60;row.save()
    recent=pair['bc'].get(BASE+f'conversations/{identity}/messages').data
    assert len(recent['results'])==50 and recent['before']==11
    previous=pair['bc'].get(BASE+f'conversations/{identity}/messages?before=11').data
    assert len(previous['results'])==10 and previous['results'][0]['sequence']==1
    for sequence in (50,10):assert pair['bc'].post(BASE+f'conversations/{identity}/read',{'sequence':sequence},format='json').status_code==200
    assert pair['bc'].get(BASE+'conversations').data['unread']==10


def test_notifications_and_preferences_remain_scoped(pair):
    identity=conversation(pair);send(pair,identity)
    notifications=pair['bc'].get('/api/v2/notifications').data
    assert notifications['unread']==1 and notifications['results'][0]['context']['conversation']==identity
    key=notifications['results'][0]['key']
    assert pair['fc'].post('/api/v2/notifications',{'key':key},format='json').status_code==400
    assert pair['bc'].post('/api/v2/notifications',{'key':key},format='json').status_code==200
    assert pair['bc'].patch('/api/v2/notifications/preferences',{'messages':False},format='json').status_code==200
    send(pair,identity)
    assert m.GlobalNotification.objects.filter(user=pair['b']).count()==1


@override_settings(ALLOWED_HOSTS=['testserver'],CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}})
def test_websocket_authenticated_delivery_typing_and_revocation(pair):
    from transitflow.asgi import application
    identity=conversation(pair);token=str(RefreshToken.for_user(pair['b']).access_token)
    async def run():
        ws=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')])
        assert (await ws.connect())[0]
        await ws.send_json_to({'type':'authenticate','token':token,'organization':str(pair['org'].pk)})
        assert await ws.receive_json_from()=={'type':'ready'}
        response=await database_sync_to_async(send)(pair,identity)
        assert response.status_code==201
        events=[await ws.receive_json_from(),await ws.receive_json_from()]
        assert any(event['type']=='changed' and event['conversation']==identity for event in events)
        await ws.send_json_to({'type':'typing','conversation':str(uuid.uuid4())})
        assert (await ws.receive_output())['code']==4403
        await ws.disconnect()
    async_to_sync(run)()


@pytest.mark.parametrize('attack',['bad-token','foreign-org','inactive','bad-origin'])
@override_settings(ALLOWED_HOSTS=['testserver'],CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}})
def test_websocket_security_rejections(pair,attack):
    from transitflow.asgi import application
    token=str(RefreshToken.for_user(pair['b']).access_token)
    if attack=='inactive':pair['bm'].active=False;pair['bm'].save()
    async def run():
        ws=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://evil.test' if attack=='bad-origin' else b'http://testserver')])
        connected,_=await ws.connect()
        if attack=='bad-origin':assert not connected;return
        await ws.send_json_to({'type':'authenticate','token':'bad' if attack=='bad-token' else token,
            'organization':str(pair['other'].pk if attack=='foreign-org' else pair['org'].pk)})
        assert (await ws.receive_output())['code']==4403
        await ws.disconnect()
    async_to_sync(run)()
