from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from . import models as m
from .messaging import accessible, mission_allowed
from .views import ScopedView, Page


def notify(organization,user,key,category,title,body,context):
    preference=m.NotificationPreference.objects.filter(organization=organization,user_id=user).first()
    if preference and not getattr(preference,category,True):return
    row,created=m.GlobalNotification.objects.get_or_create(organization=organization,user_id=user,key=key,
        defaults=dict(category=category,title=title[:180],body=body[:500],context=context,
            push_pending=bool(preference and preference.push),push_after=timezone.now()))
    if created:
        from .realtime import publish
        transaction.on_commit(lambda:publish(organization.pk,[user],'notification'))


def visible_notifications(member):
    qs=m.GlobalNotification.objects.filter(organization=member.organization,user=member.user)
    conversation_ids=[str(identity) for identity in accessible(member).values_list('pk',flat=True)]
    qs=qs.filter(~Q(category='messages')|Q(context__conversation__in=conversation_ids))
    if member.role=='driver':
        missions=[str(identity) for identity in m.Mission.objects.filter(organization=member.organization,driver__user=member.user).values_list('pk',flat=True)]
        qs=qs.filter(~Q(category='missions')|Q(context__id__in=missions))
    from . import security
    from .applications import resource_enabled
    for resource in ('invoices','orders','payments','partners'):
        if not security.allowed(member.role,resource) or not resource_enabled(member.organization,resource):
            qs=qs.filter(Q(context__module__isnull=True)|~Q(context__module=resource))
    if not security.allowed(member.role,'missions'):qs=qs.exclude(category='missions')
    for module in ('incidents','maintenance','documents'):
        if not security.allowed(member.role,module):qs=qs.filter(Q(context__module__isnull=True)|~Q(context__module=module))
    if member.role=='driver':
        documents=[str(identity) for identity in m.Document.objects.filter(organization=member.organization,
            mission__driver__user=member.user).exclude(category='finance').values_list('pk',flat=True)]
        qs=qs.filter(Q(context__module__isnull=True)|~Q(context__module='documents')|Q(context__id__in=documents))
    return qs


class GlobalNotificationsView(ScopedView):
    def legacy(self):
        if self.member.role not in ('owner','admin','operations','workshop','driver') or not self.enabled('missions'):return []
        from .field import NotificationsView
        view=NotificationsView();view.request=self.request;view.member=self.member;view.org=self.org;view.active_applications=self.active_applications
        return [dict(item,id=item['key'],category='operations',context={'module':'field'},source='field') for item in view.notifications()]

    def get(self,request):
        qs=visible_notifications(self.member)
        legacy=self.legacy()
        identities={(n.get('identity'),n.get('version')) for n in legacy}
        existing=set()
        mission_identities=set()
        if identities:
            for category,context in qs.exclude(category='messages').values_list('category','context'):
                pair=(context.get('legacy_identity'),context.get('legacy_version'))
                if pair in identities:existing.add(pair)
                if category=='missions':mission_identities.add(context.get('legacy_identity'))
        legacy=[n for n in legacy if (n.get('identity'),n.get('version')) not in existing and n.get('identity') not in mission_identities]
        class Feed:
            def __init__(self):self.size=qs.count()
            def count(self):return self.size+len(legacy)
            def __getitem__(self,section):
                start=section.start or 0;stop=section.stop
                records=qs.order_by(F('read_at').asc(nulls_first=True),'-created_at')[min(start,self.size):min(stop,self.size)]
                items=[dict(id=str(n.pk),key=n.key,title=n.title,body=n.body,read=bool(n.read_at),category=n.category,
                    context=n.context,created_at=n.created_at,severity='info',source='global') for n in records]
                return items+legacy[max(0,start-self.size):max(0,stop-self.size)]
        paginator=Page();rows=paginator.paginate_queryset(Feed(),request)
        response=paginator.get_paginated_response(rows);response.data['unread']=qs.filter(read_at__isnull=True).count()+sum(not n['read'] for n in legacy)
        return response

    def post(self,request):
        key=serializers.CharField(max_length=128).run_validation(request.data.get('key'))
        row=visible_notifications(self.member).filter(key=key).first()
        if row:
            row.read_at=timezone.now();row.push_pending=False;row.save(update_fields=['read_at','push_pending','updated_at'])
        else:
            from .field import NotificationsView
            if not any(n['key']==key for n in self.legacy()):raise serializers.ValidationError('Notification inaccessible.')
            m.NotificationRead.objects.get_or_create(organization=self.org,user=request.user,key=key)
        from .realtime import publish
        transaction.on_commit(lambda:publish(self.org.pk,[request.user.pk],'notification'))
        return Response({'ok':True})


class PreferencesView(ScopedView):
    def get(self,request):
        from django.conf import settings
        row,_=m.NotificationPreference.objects.get_or_create(organization=self.org,user=request.user)
        return Response(dict((name,getattr(row,name)) for name in ['messages','missions','operations','push','preview'])|
            {'vapid_public_key':settings.TF_VAPID_PUBLIC_KEY})
    def patch(self,request):
        row,_=m.NotificationPreference.objects.get_or_create(organization=self.org,user=request.user)
        for name in ['messages','missions','operations','push','preview']:
            if name in request.data:setattr(row,name,serializers.BooleanField().run_validation(request.data[name]))
        row.save()
        if not row.push:m.GlobalNotification.objects.filter(organization=self.org,user=request.user).update(push_pending=False)
        return self.get(request)
