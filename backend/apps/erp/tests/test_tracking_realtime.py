import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.test import override_settings
from rest_framework_simplejwt.tokens import RefreshToken
from apps.erp.realtime import group
from .test_tracking import gps_env
from .test_workflows import env

pytestmark=pytest.mark.django_db(transaction=True)

@pytest.mark.parametrize('role,allowed',[('owner',True),('operations',True),('viewer',False),('finance',False)])
@override_settings(ALLOWED_HOSTS=['testserver'],CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}})
def test_tracking_events_recheck_role(gps_env,role,allowed):
    e=gps_env;e['member'].role=role;e['member'].save();token=str(RefreshToken.for_user(e['user']).access_token)
    from transitflow.asgi import application
    async def run():
        ws=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')])
        assert (await ws.connect())[0]
        await ws.send_json_to({'type':'authenticate','token':token,'organization':str(e['org'].pk)})
        assert (await ws.receive_json_from())['type']=='ready'
        await get_channel_layer().group_send(group(e['org'].pk,e['user'].pk),{'type':'activity','event':'tracking','mission':str(e['trip'].pk)})
        if allowed:
            message=await ws.receive_json_from();assert message['type']=='tracking' and message['mission']==str(e['trip'].pk)
            assert 'latitude' not in message and 'longitude' not in message
        else:assert await ws.receive_nothing(timeout=0.2)
        await ws.disconnect()
    async_to_sync(run)()

@override_settings(ALLOWED_HOSTS=['testserver'],CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}})
def test_tracking_socket_foreign_organization_refused(gps_env):
    e=gps_env;token=str(RefreshToken.for_user(e['user']).access_token)
    from transitflow.asgi import application
    async def run():
        ws=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')]);assert (await ws.connect())[0]
        await ws.send_json_to({'type':'authenticate','token':token,'organization':str(e['other'].pk)})
        message=await ws.receive_output();assert message['type']=='websocket.close' and message['code']==4403
        await ws.disconnect()
    async_to_sync(run)()
