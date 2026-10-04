import asyncio
import logging
import time
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from . import models as m

logger=logging.getLogger(__name__)


def group(organization,user):return f'org.{organization}.user.{user}'


async def send_event(layer,target,payload):
    await asyncio.wait_for(layer.group_send(target,payload),timeout=2)


def publish(organization,users,event='changed',conversation=None,mission=None):
    try:layer=get_channel_layer()
    except Exception:
        logger.warning('Diffusion temps réel indisponible ; événement conservé en base.')
        return
    if not layer:return
    for user in users:
        try:
            async_to_sync(send_event)(layer,group(organization,user),{'type':'activity','event':event,'conversation':conversation,'mission':str(mission) if mission else None})
        except Exception:
            logger.warning('Diffusion temps réel indisponible ; événement conservé en base.')


class ActivityConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.member_id=None;self.organization=None;self.user_id=None;self.token=None;self.last_typing=0
        await self.accept()
        self.deadline=asyncio.create_task(self.authentication_deadline())

    async def authentication_deadline(self):
        await asyncio.sleep(10)
        if not self.member_id:await self.close(code=4401)

    @database_sync_to_async
    def authorize(self,token,organization,conversation=None):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from .messaging import accessible
        auth=JWTAuthentication();user=auth.get_user(auth.get_validated_token(token))
        member=m.Membership.objects.select_related('organization').get(user=user,organization_id=organization,active=True)
        if conversation and not accessible(member).filter(pk=conversation).exists():raise ValueError('Conversation inaccessible')
        return member.pk,user.pk

    async def receive(self,text_data=None,bytes_data=None,**kwargs):
        if bytes_data or text_data is None or len(text_data)>4096:
            await self.close(code=4400);return
        try:
            await super().receive(text_data=text_data,**kwargs)
        except (ValueError,TypeError,KeyError):await self.close(code=4400)

    async def receive_json(self,content,**kwargs):
        if not isinstance(content,dict):await self.close(code=4400);return
        if not self.member_id:
            if content.get('type')!='authenticate':await self.close(code=4401);return
            try:
                self.token=content['token'];self.organization=content['organization']
                self.member_id,self.user_id=await self.authorize(self.token,self.organization)
                await self.channel_layer.group_add(group(self.organization,self.user_id),self.channel_name)
            except Exception:await self.close(code=4403);return
            self.deadline.cancel();await self.send_json({'type':'ready'});return
        conversation=content.get('conversation')
        try:await self.authorize(self.token,self.organization,conversation)
        except Exception:await self.close(code=4403);return
        if content.get('type')=='ping':
            await self.channel_layer.group_add(group(self.organization,self.user_id),self.channel_name)
            if settings.TF_REDIS_URL and content.get('visible') is True:
                import redis.asyncio as redis
                client=redis.from_url(settings.TF_REDIS_URL,socket_connect_timeout=2,socket_timeout=2)
                try:await client.set('tf.active.'+group(self.organization,self.user_id),1,ex=45)
                except Exception:pass
                finally:await client.aclose()
            await self.send_json({'type':'pong'})
        elif content.get('type')=='typing' and conversation and time.monotonic()-self.last_typing>=3:
            self.last_typing=time.monotonic()
            users=await self.typing_users(conversation)
            for user in users:
                await self.channel_layer.group_send(group(self.organization,user),{'type':'activity','event':'typing','conversation':conversation,'member':self.member_id})

    @database_sync_to_async
    def typing_users(self,conversation):
        return list(m.ConversationParticipant.objects.filter(organization_id=self.organization,conversation_id=conversation,
            active=True,membership__active=True).exclude(membership_id=self.member_id).values_list('membership__user_id',flat=True))

    @database_sync_to_async
    def tracking_allowed(self,mission):
        member=m.Membership.objects.get(pk=self.member_id,active=True)
        from .applications import resource_enabled
        if not resource_enabled(member.organization,'missions'):return False
        if member.role in ('owner','admin','operations'):return m.Mission.objects.filter(pk=mission,organization_id=self.organization).exists()
        return member.role=='driver' and m.Mission.objects.filter(pk=mission,organization_id=self.organization,driver__user_id=self.user_id).exists()

    async def activity(self,event):
        if event.get('event')=='access_revoked':
            await self.send_json({'type':'access_revoked'});await self.close(code=4403);return
        try:await self.authorize(self.token,self.organization,event.get('conversation'))
        except Exception:
            if event.get('conversation'):return
            await self.close(code=4403);return
        if event.get('event') in ('tracking','tracking_lifecycle') and not await self.tracking_allowed(event.get('mission')):return
        await self.send_json({'mission':event.get('mission'),'type':event['event'],'conversation':event.get('conversation'),'member':event.get('member')})

    async def disconnect(self,code):
        if hasattr(self,'deadline'):self.deadline.cancel()
        if self.member_id:
            try:await self.channel_layer.group_discard(group(self.organization,self.user_id),self.channel_name)
            except Exception:pass
