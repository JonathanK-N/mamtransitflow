import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import override_settings
from rest_framework_simplejwt.tokens import RefreshToken
from apps.erp.realtime import group
from .test_workflows import env

pytestmark=pytest.mark.django_db(transaction=True)


@override_settings(ALLOWED_HOSTS=['testserver'],CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}})
def test_operations_socket_rechecks_role_and_tenant(env):
    from transitflow.asgi import application
    token=str(RefreshToken.for_user(env['user']).access_token)
    async def run():
        ws=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')])
        assert (await ws.connect())[0]
        await ws.send_json_to({'type':'authenticate','token':token,'organization':str(env['org'].pk)})
        assert (await ws.receive_json_from())['type']=='ready'
        layer=get_channel_layer()
        await layer.group_send(group(env['other'].pk,env['user'].pk),{'type':'activity','event':'operations'})
        assert await ws.receive_nothing(timeout=.2)
        await layer.group_send(group(env['org'].pk,env['user'].pk),{'type':'activity','event':'operations'})
        message=await ws.receive_json_from();assert message['type']=='operations'
        assert set(message)=={'type','mission','conversation','member'}
        @database_sync_to_async
        def change_role():
            env['member'].role='viewer';env['member'].save()
        await change_role()
        await layer.group_send(group(env['org'].pk,env['user'].pk),{'type':'activity','event':'operations'})
        assert await ws.receive_nothing(timeout=.2)
        await ws.disconnect()
    async_to_sync(run)()
