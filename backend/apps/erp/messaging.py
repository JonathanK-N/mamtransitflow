import hashlib
import uuid
from pathlib import Path
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery, Sum, F
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from . import models as m, services, security
from .views import ScopedView, Page
from .serializers import serializer_for


def mission_allowed(member, mission):
    from .applications import resource_enabled
    return (mission.organization_id == member.organization_id and resource_enabled(member.organization, 'missions')
            and security.allowed(member.role, 'missions')
            and (member.role != 'driver' or mission.driver.user_id == member.user_id))


def accessible(member):
    qs = m.Conversation.objects.filter(organization=member.organization,
        participants__membership=member, participants__active=True).select_related('mission__driver')
    if not security.allowed(member.role, 'missions'):
        return qs.filter(mission__isnull=True)
    if member.role == 'driver':
        qs = qs.filter(Q(mission__isnull=True) | Q(mission__driver__user=member.user))
    from .applications import resource_enabled
    if not resource_enabled(member.organization, 'missions'):
        qs = qs.filter(mission__isnull=True)
    return qs


def changed(conversation, event='changed'):
    from .realtime import publish
    members = list(conversation.participants.filter(active=True, membership__active=True).values_list('membership__user_id', flat=True))
    transaction.on_commit(lambda: publish(conversation.organization_id, members, event, str(conversation.pk)))


def direct_conversation(member, colleague, actor):
    m.Organization.objects.select_for_update().get(pk=member.organization_id)
    ids={member.pk,colleague.pk}
    if len(ids)!=2 or colleague.organization_id!=member.organization_id:
        raise ValidationError('Sélectionnez un autre collaborateur de cette entreprise.')
    members=list(m.Membership.objects.filter(organization_id=member.organization_id,pk__in=ids,active=True,user__is_active=True))
    if len(members)!=2:raise ValidationError('Collaborateur inaccessible.')
    key=':'.join(map(str,sorted(ids)))
    row=m.Conversation.objects.filter(organization_id=member.organization_id,kind='direct',direct_key=key).first()
    if row:
        row.participants.filter(membership__in=members,active=False).update(active=True,last_read_sequence=row.last_sequence)
        return row,False
    row=m.Conversation.objects.create(organization_id=member.organization_id,kind='direct',direct_key=key,creator=actor)
    for person in members:m.ConversationParticipant.objects.create(organization_id=member.organization_id,conversation=row,membership=person)
    services.audit(member.organization,actor,'conversation-create',row,kind='direct')
    changed(row)
    return row,True


class ConversationInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['direct', 'group', 'mission'])
    title = serializers.CharField(max_length=150, required=False, default='', allow_blank=True)
    participants = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=50, required=False, default=list)
    mission = serializers.UUIDField(required=False)


class MessagingView(ScopedView):
    def conversation(self, pk, lock=False):
        qs = accessible(self.member)
        if lock:
            qs = qs.select_for_update(of=('self',))
        return get_object_or_404(qs, pk=pk)

    def summary(self, row):
        participants = list(row.participants.all() if 'participants' in getattr(row,'_prefetched_objects_cache',{}) else row.participants.select_related('membership__user'))
        own = next(p for p in participants if p.membership_id == self.member.pk)
        others = [p.membership.user.nom+(' — ancien collaborateur' if not p.membership.active else '') for p in participants if p.membership_id != self.member.pk]
        return dict(id=str(row.pk), kind=row.kind, title=row.title or ', '.join(others) or 'Conversation',
            active=row.active, unread=max(0, row.last_sequence-own.last_read_sequence),
            last_message=getattr(row, 'preview', '') or '', last_message_at=row.last_message_at,
            sequence=row.last_sequence, mission=str(row.mission_id) if row.mission_id else None,
            mission_reference=row.mission.reference if row.mission_id else '',
            can_manage=row.creator_id == self.request.user.pk or self.member.role in ('owner', 'admin'),
            participants=[dict(id=p.membership_id, name=p.membership.user.nom+(' — ancien collaborateur' if not p.membership.active else ''), role=p.membership.role,
                active=p.active and p.membership.active, read_sequence=p.last_read_sequence) for p in participants])

    def get(self, request, pk=None):
        if pk:
            row=self.conversation(pk)
            row.preview=row.messages.order_by('-sequence').values_list('body', flat=True).first()
            return Response(self.summary(row))
        qs=accessible(self.member).prefetch_related('participants__membership__user')
        latest=m.Message.objects.filter(conversation=OuterRef('pk')).order_by('-sequence')
        qs=qs.annotate(preview=Subquery(latest.values('body')[:1]))
        q=request.query_params.get('q', '').strip()[:100]
        if q:
            qs=qs.filter(Q(title__icontains=q)|Q(participants__membership__user__nom__icontains=q)).distinct()
        paginator=Page(); rows=paginator.paginate_queryset(qs,request)
        response=paginator.get_paginated_response([self.summary(row) for row in rows])
        own=m.ConversationParticipant.objects.filter(organization=self.org,membership=self.member,active=True,conversation__in=accessible(self.member))
        response.data['unread']=own.aggregate(total=Sum(F('conversation__last_sequence')-F('last_read_sequence')))['total'] or 0
        return response

    def post(self,request):
        from .auth import limit
        limit(request,'conversation:'+str(request.user.pk),60)
        data=ConversationInput(data=request.data);data.is_valid(raise_exception=True);data=data.validated_data
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        ids=set(data['participants'])|{self.member.pk}
        mission=None
        if data['kind']=='mission':
            if 'mission' not in data:raise ValidationError('Mission requise.')
            mission=get_object_or_404(self.queryset('missions'),pk=data['mission'])
            ids=set(m.Membership.objects.filter(organization=self.org,active=True,role__in=['owner','admin','operations']).values_list('pk',flat=True))|{self.member.pk}
            if mission.driver.user_id:
                ids.update(m.Membership.objects.filter(organization=self.org,active=True,user_id=mission.driver.user_id).values_list('pk',flat=True))
        members=list(m.Membership.objects.filter(organization=self.org,active=True,pk__in=ids,user__is_active=True))
        if len(members)!=len(ids):raise ValidationError('Collaborateur inaccessible.')
        if mission and any(not mission_allowed(member,mission) for member in members):raise ValidationError('Accès à la mission requis pour chaque participant.')
        if data['kind']=='direct' and len(ids)!=2:raise ValidationError('Sélectionnez exactement un autre collaborateur.')
        if data['kind']=='group' and (len(ids)<2 or not data['title'].strip()):raise ValidationError('Titre et au moins deux participants requis.')
        if data['kind']=='direct':
            row,created=direct_conversation(self.member,next(x for x in members if x.pk!=self.member.pk),request.user)
            return Response(self.summary(row),status=201 if created else 200)
        key=':'.join(map(str,sorted(ids))) if data['kind']=='direct' else ''
        existing=m.Conversation.objects.filter(organization=self.org,kind=data['kind'])
        if data['kind']=='direct':existing=existing.filter(direct_key=key)
        elif mission:existing=existing.filter(mission=mission)
        else:existing=existing.none()
        row=existing.first()
        if row:
            if not row.participants.filter(membership=self.member,active=True).exists():raise PermissionDenied('Conversation inaccessible.')
            return Response(self.summary(row))
        row=m.Conversation.objects.create(organization=self.org,kind=data['kind'],creator=request.user,
            title=('Mission '+mission.reference) if mission else data['title'].strip(),mission=mission,direct_key=key)
        for member in members:m.ConversationParticipant.objects.create(organization=self.org,conversation=row,membership=member)
        services.audit(self.org,request.user,'conversation-create',row,kind=row.kind)
        changed(row)
        return Response(self.summary(row),status=201)

    def patch(self,request,pk):
        row=self.conversation(pk,True)
        if row.kind=='direct' or not (row.creator_id==request.user.pk or self.member.role in ('owner','admin')):raise PermissionDenied()
        if 'title' in request.data:
            row.title=serializers.CharField(max_length=150).run_validation(request.data['title']).strip()
        if 'active' in request.data:row.active=serializers.BooleanField().run_validation(request.data['active'])
        for action in ('add','remove'):
            if action not in request.data:continue
            identity=serializers.IntegerField(min_value=1).run_validation(request.data[action])
            member=get_object_or_404(m.Membership,organization=self.org,pk=identity,active=True,user__is_active=True)
            if action=='add':
                if row.participants.filter(active=True).count()>=50 and not row.participants.filter(membership=member,active=True).exists():raise ValidationError('Groupe limité à 50 participants.')
                if row.mission_id and not mission_allowed(member,row.mission):raise ValidationError('Ce collaborateur ne peut pas accéder à la mission.')
                p,created=m.ConversationParticipant.objects.get_or_create(organization=self.org,conversation=row,membership=member,
                    defaults={'last_read_sequence':row.last_sequence})
                if not created:p.active=True;p.save(update_fields=['active','updated_at'])
            else:
                if member.user_id==row.creator_id:raise ValidationError('Le créateur doit rester participant.')
                m.ConversationParticipant.objects.filter(organization=self.org,conversation=row,membership=member).update(active=False)
            services.audit(self.org,request.user,'conversation-'+action,row,membership=member.pk)
        row.save();changed(row)
        return Response(self.summary(row))


class CollaboratorsView(ScopedView):
    def get(self,request):
        qs=m.Membership.objects.filter(organization=self.org,active=True,user__is_active=True).exclude(pk=self.member.pk).select_related('user')
        q=request.query_params.get('q','').strip()[:100]
        if q:qs=qs.filter(Q(user__nom__icontains=q)|Q(user__courriel__icontains=q))
        paginator=Page();rows=paginator.paginate_queryset(qs.order_by('user__nom'),request)
        return paginator.get_paginated_response([dict(id=p.pk,name=p.user.nom,role=p.role) for p in rows])


class MessagesView(MessagingView):
    def payload(self,row,participants):
        return dict(id=str(row.pk),sequence=row.sequence,body=row.body,created_at=row.created_at,
            sender=row.sender.user.nom+(' — ancien collaborateur' if not row.sender.active else ''),sender_id=row.sender_id,own=row.sender_id==self.member.pk,
            readers=[p.membership.user.nom for p in participants if p.active and p.membership.active and p.membership_id!=row.sender_id and p.last_read_sequence>=row.sequence],
            attachments=[dict(id=str(a.pk),name=a.name,mime=a.mime,size=a.size) for a in row.attachments.all()])

    def get(self,request,pk):
        conversation=self.conversation(pk)
        before=serializers.IntegerField(min_value=1).run_validation(request.query_params['before']) if 'before' in request.query_params else None
        qs=conversation.messages.select_related('sender__user').prefetch_related('attachments')
        if before:qs=qs.filter(sequence__lt=before)
        rows=list(qs.order_by('-sequence')[:51]);more=len(rows)>50;rows=rows[:50]
        participants=list(conversation.participants.select_related('membership__user'))
        return Response({'results':[self.payload(row,participants) for row in reversed(rows)],'before':rows[-1].sequence if more else None})

    def post(self,request,pk):
        conversation=self.conversation(pk,True)
        if not conversation.active:raise ValidationError('Cette conversation est archivée.')
        from .auth import limit
        limit(request,'message:'+str(request.user.pk),120)
        body=serializers.CharField(max_length=10000,allow_blank=True,required=False).run_validation(request.data.get('body','')).strip()
        client_id=serializers.UUIDField().run_validation(request.data.get('client_id'))
        previous=conversation.messages.filter(sender=self.member,client_id=client_id).first()
        if previous:
            if previous.body!=body:raise ValidationError('Identifiant de message déjà utilisé.')
            return Response(self.payload(previous,list(conversation.participants.select_related('membership__user'))))
        upload=request.data.get('file');mime=''
        if upload:
            upload=serializers.FileField().run_validation(upload)
            serializer_for(m.Document)(context=self.context()).validate_file(upload)
            mime={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}[Path(upload.name).suffix.lower()]
            if upload.content_type!=mime:raise ValidationError('Le type MIME ne correspond pas au fichier.')
        if not body and not upload:raise ValidationError('Saisissez un message ou choisissez un fichier.')
        conversation.last_sequence+=1;conversation.last_message_at=timezone.now();conversation.save()
        row=m.Message.objects.create(organization=self.org,conversation=conversation,sender=self.member,
            sequence=conversation.last_sequence,body=body,client_id=client_id)
        if upload:
            attachment=m.MessageAttachment.objects.create(organization=self.org,message=row,file=upload,
                name=Path(upload.name).name[:180],mime=mime,size=upload.size)
            services.audit(self.org,request.user,'message-attachment',attachment)
        conversation.participants.filter(membership=self.member).update(last_read_sequence=row.sequence)
        from .notifications import notify
        for p in conversation.participants.filter(active=True,membership__active=True).exclude(membership=self.member).select_related('membership'):
            notify(self.org,p.membership.user_id,'message:'+str(row.pk),'messages','Nouveau message',
                'Vous avez reçu un nouveau message.',{'conversation':str(conversation.pk),'message':str(row.pk),'sequence':row.sequence})
        changed(conversation)
        return Response(self.payload(row,list(conversation.participants.select_related('membership__user'))),status=201)


class MessageReadView(MessagingView):
    def post(self,request,pk):
        row=self.conversation(pk,True)
        sequence=serializers.IntegerField(min_value=0,max_value=row.last_sequence).run_validation(request.data.get('sequence'))
        p=row.participants.get(membership=self.member)
        advanced=sequence>p.last_read_sequence
        if advanced:p.last_read_sequence=sequence;p.save(update_fields=['last_read_sequence','updated_at'])
        m.GlobalNotification.objects.filter(organization=self.org,user=request.user,category='messages',
            context__conversation=str(row.pk),context__sequence__lte=sequence,read_at__isnull=True).update(read_at=timezone.now(),push_pending=False)
        if advanced:changed(row,'read')
        return Response({'ok':True,'sequence':p.last_read_sequence})


class MessageAttachmentView(MessagingView):
    def get(self,request,pk):
        attachment=get_object_or_404(m.MessageAttachment.objects.select_related('message'),organization=self.org,pk=pk,
            message__conversation__in=accessible(self.member))
        services.audit(self.org,request.user,'message-download',attachment)
        response=FileResponse(attachment.file.open('rb'),as_attachment=True,filename=attachment.name,content_type=attachment.mime)
        response['X-Content-Type-Options']='nosniff'
        return response
