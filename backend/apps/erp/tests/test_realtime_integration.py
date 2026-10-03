import json
import subprocess
import sys
import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import override_settings,AsyncClient
from rest_framework_simplejwt.tokens import RefreshToken
from .test_messaging import pair,conversation
from .test_workflows import env

pytestmark=pytest.mark.django_db(transaction=True)


@pytest.mark.skipif(not settings.TF_REDIS_URL,reason='Redis requis pour vérifier deux processus distincts')
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_redis_delivers_from_another_process(pair):
    from transitflow.asgi import application
    identity=conversation(pair);token=str(RefreshToken.for_user(pair['b']).access_token)
    from apps.erp.realtime import group
    target=group(pair['org'].pk,pair['b'].pk)
    async def run():
        ws=WebsocketCommunicator(application,'/ws/activity',headers=[(b'origin',b'http://testserver')])
        assert (await ws.connect())[0]
        await ws.send_json_to({'type':'authenticate','token':token,'organization':str(pair['org'].pk)})
        assert (await ws.receive_json_from())['type']=='ready'
        script="import os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','transitflow.settings');import django;django.setup();from channels.layers import get_channel_layer;from asgiref.sync import async_to_sync;async_to_sync(get_channel_layer().group_send)("+repr(target)+",{'type':'activity','event':'changed','conversation':"+repr(identity)+"})"
        import asyncio
        result=await asyncio.to_thread(subprocess.run,[sys.executable,'-c',script],cwd=str(settings.BASE_DIR),capture_output=True,timeout=20)
        assert result.returncode==0
        assert (await ws.receive_json_from(timeout=5))['conversation']==identity
        await ws.disconnect()
    async_to_sync(run)()


def test_asgi_private_attachment_stream_is_async_and_authorized(pair,tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.erp import models as m
    import uuid
    from django.test import override_settings
    identity=conversation(pair)
    with override_settings(MEDIA_ROOT=tmp_path):
        response=pair['client'].post('/api/v2/messaging/conversations/'+identity+'/messages',
            {'body':'','client_id':str(uuid.uuid4()),'file':SimpleUploadedFile('proof.pdf',b'%PDF-1.4\nproof',content_type='application/pdf')},format='multipart')
        assert response.status_code==201
        token=str(RefreshToken.for_user(pair['b']).access_token)
        async def run():
            client=AsyncClient()
            download=await client.get('/api/v2/messaging/attachments/'+response.data['attachments'][0]['id'],headers={'Authorization':'Bearer '+token,'X-Organization':str(pair['org'].pk)})
            assert download.status_code==200 and download.is_async and download['Cache-Control']=='no-store'
            assert b''.join([chunk async for chunk in download.streaming_content])==b'%PDF-1.4\nproof'
        async_to_sync(run)()
