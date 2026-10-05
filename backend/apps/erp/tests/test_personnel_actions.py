import hashlib
import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from apps.comptes.models import Utilisateur
from apps.erp import models as m
from .test_messaging import pair, conversation, send
from .test_workflows import env, mission
pytestmark=pytest.mark.django_db(transaction=True)

@pytest.fixture
def employee(pair):
    return m.Employee.objects.create(organization=pair['org'],user=pair['b'],name='Collaborateur test',job='driver')

def action(pair,employee,name='remove',client=None):
    return (client or pair['client']).post(f'/api/v2/employees/{employee.pk}/{name}',{},format='json')

def test_contact_reuses_messaging_pair(pair,employee):
    r=action(pair,employee,'contact');assert r.status_code==201,r.data
    second=action(pair,employee,'contact');assert second.status_code==200
    assert r.data['id']==second.data['id']==conversation(pair)
    assert m.Conversation.objects.count()==1

def test_contact_without_account(pair):
    row=m.Employee.objects.create(organization=pair['org'],name='Sans compte');count=Utilisateur.objects.count()
    r=action(pair,row,'contact');assert r.status_code==400 and 'compte TransitFlow actif' in str(r.data)
    assert Utilisateur.objects.count()==count and m.Conversation.objects.count()==0

@pytest.mark.parametrize('name',['contact','remove'])
def test_cross_tenant(pair,name):
    row=m.Employee.objects.create(organization=pair['other'],name='Autre entreprise')
    assert action(pair,row,name).status_code==404
    row.refresh_from_db();assert row.active

@pytest.mark.parametrize('name',['contact','remove'])
def test_normal_member_denied(pair,employee,name):
    pair['bm'].role='viewer';pair['bm'].save()
    assert action(pair,employee,name,client=pair['bc']).status_code==403

def test_preserve_user_other_tenant_history(pair,employee):
    other=m.Membership.objects.create(organization=pair['other'],user=pair['b'],role='driver')
    identity=conversation(pair);assert send(pair,identity,client=pair['bc']).status_code==201
    history=mission(pair|{'driver':employee});m.Mission.objects.filter(pk=history['id']).update(status='completed')
    assert action(pair,employee).status_code==200
    employee.refresh_from_db();pair['bm'].refresh_from_db();other.refresh_from_db();pair['b'].refresh_from_db()
    assert not employee.active and not pair['bm'].active and other.active and pair['b'].is_active
    assert m.Message.objects.count()==1 and m.Conversation.objects.count()==1
    assert m.Mission.objects.get(pk=history['id']).driver_id==employee.pk
    assert m.AuditEvent.objects.filter(action='employee-remove',organization=pair['org'],actor=pair['user']).exists()
    assert 'ancien collaborateur' in pair['client'].get('/api/v2/messaging/conversations/'+identity).data['title']
    pair['bc'].credentials(HTTP_X_ORGANIZATION=str(pair['other'].pk))
    assert pair['bc'].get('/api/v2/messaging/conversations').status_code==200

@pytest.mark.parametrize('path',['employees','missions','field/context','notifications','messaging/conversations','catalog','documents'])
def test_removed_apis_denied(pair,employee,path):
    assert action(pair,employee).status_code==200
    assert pair['bc'].get('/api/v2/'+path).status_code==403

def test_chat_attachment_history_preserved_access_denied(pair,employee,tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    identity=conversation(pair)
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        r=pair['client'].post('/api/v2/messaging/conversations/'+identity+'/messages',{'body':'Historique','client_id':'489f7d1b-3189-47cd-9b2a-39598b3a0c31','file':SimpleUploadedFile('proof.pdf',b'%PDF-1.4\nproof',content_type='application/pdf')},format='multipart');assert r.status_code==201,r.data
        attachment=r.data['attachments'][0]['id']
        assert action(pair,employee).status_code==200
        assert pair['bc'].get('/api/v2/messaging/attachments/'+attachment).status_code==403
        assert pair['bc'].get('/api/v2/messaging/conversations/'+identity+'/messages').status_code==403
        assert send(pair,identity,client=pair['bc']).status_code==403
        assert m.Message.objects.count()==1 and m.MessageAttachment.objects.count()==1

@pytest.mark.parametrize('status',['planned','active'])
def test_missions_block_removal_atomically(pair,employee,status):
    row=mission(pair|{'driver':employee});m.Mission.objects.filter(pk=row['id']).update(status=status)
    r=action(pair,employee);assert r.status_code==400 and 'Réaffectez' in str(r.data)
    employee.refresh_from_db();pair['bm'].refresh_from_db();assert employee.active and pair['bm'].active

@pytest.mark.parametrize('actor_role,target_role,status',[('admin','admin',403),('admin','owner',403),('owner','admin',200),('owner','owner',200)])
def test_roles_policy(pair,employee,actor_role,target_role,status):
    pair['member'].role=actor_role;pair['member'].save();pair['bm'].role=target_role;pair['bm'].save()
    if actor_role=='admin' and target_role=='owner':m.Membership.objects.create(organization=pair['org'],user=pair['foreign'].user,role='owner')
    assert action(pair,employee).status_code==status

def test_last_owner_and_self_protected(pair):
    row=m.Employee.objects.create(organization=pair['org'],user=pair['user'],name='Propriétaire')
    assert action(pair,row).status_code==400
    pair['bm'].role='owner';pair['bm'].save();assert action(pair,row).status_code==400
    assert pair['client'].patch('/api/v2/team',{'id':pair['member'].pk,'active':False},format='json').status_code==400

def test_generic_routes_cannot_bypass_removal(pair,employee):
    assert pair['client'].delete('/api/v2/employees/'+str(employee.pk)).status_code==403
    assert pair['client'].patch('/api/v2/employees/'+str(employee.pk),{'active':False},format='json').status_code==400
    assert pair['client'].patch('/api/v2/team',{'id':pair['bm'].pk,'active':False},format='json').status_code==200
    employee.refresh_from_db();assert not employee.active

def test_reinvitation_reuses_employee_and_membership(pair,employee):
    from apps.erp.security import grant_invitation
    assert action(pair,employee).status_code==200
    invite=m.TeamInvitation.objects.create(organization=pair['org'],email=pair['b'].courriel,role='driver',digest=hashlib.sha256(b'new invitation').hexdigest(),expires_at=timezone.now()+timezone.timedelta(days=1))
    grant_invitation(invite,pair['b']);employee.refresh_from_db();pair['bm'].refresh_from_db()
    assert employee.active and pair['bm'].active
    assert m.Employee.objects.filter(organization=pair['org'],user=pair['b']).count()==1
    assert m.Membership.objects.filter(organization=pair['org'],user=pair['b']).count()==1

def test_live_websocket_revoked_and_cannot_reauthenticate(pair,employee):
    from transitflow.asgi import application
    token=str(RefreshToken.for_user(pair['b']).access_token)
    with override_settings(ALLOWED_HOSTS=['testserver'],CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}}):
        async def scenario():
            socket=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')]);assert (await socket.connect())[0]
            await socket.send_json_to({'type':'authenticate','token':token,'organization':str(pair['org'].pk)})
            assert (await socket.receive_json_from())['type']=='ready'
            r=await database_sync_to_async(action)(pair,employee);assert r.status_code==200
            assert (await socket.receive_json_from())['type']=='access_revoked'
            assert (await socket.receive_output())['code']==4403
            await socket.disconnect()
            again=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')]);await again.connect()
            await again.send_json_to({'type':'authenticate','token':token,'organization':str(pair['org'].pk)})
            assert (await again.receive_output())['code']==4403
            await again.disconnect()
        async_to_sync(scenario)()


def test_remove_unlinked_employee_without_creating_user(pair):
    row=m.Employee.objects.create(organization=pair['org'],name='Personnel sans compte')
    before=Utilisateur.objects.count();assert action(pair,row).status_code==200
    row.refresh_from_db();assert not row.active and Utilisateur.objects.count()==before


def test_pending_push_and_unused_invitation_revoked_only_in_target_org(pair,employee):
    pending=m.GlobalNotification.objects.create(organization=pair['org'],user=pair['b'],key='pending',category='messages',title='Nouveau message',push_pending=True)
    other=m.GlobalNotification.objects.create(organization=pair['other'],user=pair['b'],key='pending',category='messages',title='Nouveau message',push_pending=True)
    invite=m.TeamInvitation.objects.create(organization=pair['org'],email=pair['b'].courriel,role='driver',digest='b'*64,expires_at=timezone.now()+timezone.timedelta(days=1))
    assert action(pair,employee).status_code==200
    pending.refresh_from_db();other.refresh_from_db();invite.refresh_from_db()
    assert not pending.push_pending and other.push_pending and invite.expires_at<=timezone.now()


def test_cannot_plan_a_new_mission_with_departed_driver(pair,employee):
    assert action(pair,employee).status_code==200
    with pytest.raises(AssertionError,match='quitté'):
        mission(pair|{'driver':employee})


def test_concurrent_contact_creates_one_pair(pair,employee):
    from django.db import connection, transaction
    from .test_concurrency import concurrent
    from apps.erp.messaging import direct_conversation
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    def create(index):
        with transaction.atomic():direct_conversation(pair['member'],pair['bm'],pair['user'])
    assert concurrent(create)==['accepted','accepted']
    assert m.Conversation.objects.count()==1 and m.ConversationParticipant.objects.count()==2


def test_reinvited_contact_reuses_pair_and_restores_only_direct_participation(pair,employee):
    from apps.erp.security import grant_invitation
    identity=conversation(pair);assert action(pair,employee).status_code==200
    invite=m.TeamInvitation.objects.create(organization=pair['org'],email=pair['b'].courriel,role='driver',digest='c'*64,expires_at=timezone.now()+timezone.timedelta(days=1))
    grant_invitation(invite,pair['b'])
    r=action(pair,employee,'contact');assert r.status_code==200 and r.data['id']==identity
    assert pair['bc'].get('/api/v2/messaging/conversations/'+identity).status_code==200
