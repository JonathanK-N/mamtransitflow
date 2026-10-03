"""
ASGI config for transitflow project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'transitflow.settings')

application = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from apps.erp.realtime import ActivityConsumer

protocol_application = ProtocolTypeRouter({'http': application,
    'websocket': AllowedHostsOriginValidator(URLRouter([path('ws/activity', ActivityConsumer.as_asgi())]))})

import asyncio
import logging
from channels.db import database_sync_to_async
from django.conf import settings

async def push_loop():
    from apps.erp.push import process_pending
    while True:
        try:await database_sync_to_async(process_pending,thread_sensitive=False)()
        except Exception:logging.getLogger(__name__).warning('Traitement push temporairement indisponible ; reprise prévue.')
        await asyncio.sleep(5)

async def application(scope,receive,send):
    if scope['type']!='lifespan':return await protocol_application(scope,receive,send)
    task=None
    while True:
        event=await receive()
        if event['type']=='lifespan.startup':
            if settings.TF_VAPID_PRIVATE_KEY:task=asyncio.create_task(push_loop())
            await send({'type':'lifespan.startup.complete'})
        elif event['type']=='lifespan.shutdown':
            if task:
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
            await send({'type':'lifespan.shutdown.complete'});return
