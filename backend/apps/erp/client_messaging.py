import uuid
from collections.abc import Mapping
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from . import models as m, services
from .views import ScopedView, Page
from .portal import PortalView


def messages(request, org, conversation):
    page=Page()
    rows=page.paginate_queryset(conversation.messages.filter(organization=org).order_by('-created_at','-id'),request)
    return page.get_paginated_response([dict(id=str(x.pk),body=x.body,created_at=x.created_at,outgoing=x.sender_id==request.user.pk) for x in rows])


def send(request,org,conversation):
    if not isinstance(request.data,Mapping):raise ValidationError('Le message doit être un objet JSON.')
    from .auth import limit
    limit(request,'client-message:'+str(org.pk)+':'+str(request.user.pk),120)
    body=request.data.get('body','')
    if not isinstance(body,str) or not 1<=len(body.strip())<=5000:
        raise ValidationError('Le message doit contenir entre 1 et 5 000 caractères.')
    try:client_id=uuid.UUID(str(request.data.get('client_id')))
    except (ValueError,TypeError):raise ValidationError('Identifiant du message invalide.')
    row,created=m.ClientMessage.objects.get_or_create(organization=org,conversation=conversation,sender=request.user,client_id=client_id,defaults={'body':body.strip()})
    if not created and row.body!=body.strip():raise ValidationError('Cet identifiant est déjà utilisé par un autre message.')
    return Response(dict(id=str(row.pk),body=row.body,created_at=row.created_at,outgoing=True),status=201 if created else 200)


class ClientMessagesView(ScopedView):
    def conversation(self,pk):
        self.ensure('partners')
        if self.member.role not in ('owner','admin','operations','finance'):
            raise PermissionDenied('Discussion client inaccessible.')
        if 'customer-portal' not in self.active_applications:raise PermissionDenied('Le portail client est désactivé.')
        rows=m.ClientConversation.objects.select_related('access').filter(organization=self.org,access__partner_id=pk,access__active=True,active=True).order_by('-access__created_at','-access_id')
        access=self.request.query_params.get('access') or self.request.data.get('access')
        if access:
            try:rows=rows.filter(access_id=uuid.UUID(str(access)))
            except (ValueError,TypeError):raise ValidationError('Accès portail invalide.')
        row=rows.first()
        if row is None:
            from rest_framework.exceptions import NotFound
            raise NotFound('Discussion client inaccessible.')
        return row
    def get(self,request,pk):return messages(request,self.org,self.conversation(pk))
    def post(self,request,pk):
        return send(request,self.org,self.conversation(pk))


class StartClientConversationView(ScopedView):
    def post(self,request,pk):
        self.ensure('partners',True)
        if self.member.role not in ('owner','admin','operations','finance') or 'customer-portal' not in self.active_applications:
            raise PermissionDenied('Discussion client inaccessible.')
        from .auth import limit
        limit(request,'client-conversation:'+str(request.user.pk),60)
        rows=m.PortalAccess.objects.filter(organization=self.org,partner_id=pk,active=True).order_by('-created_at','-id')
        selected=request.data.get('access')
        if selected:
            try:rows=rows.filter(pk=uuid.UUID(str(selected)))
            except (ValueError,TypeError):raise ValidationError('Accès portail invalide.')
        access=rows.first()
        if access is None:
            from rest_framework.exceptions import NotFound
            raise NotFound('Accès portail inaccessible.')
        conversation,created=m.ClientConversation.objects.get_or_create(organization=self.org,access=access,defaults={'creator':request.user})
        if created:services.audit(self.org,request.user,'client-conversation-create',conversation,partner=str(pk))
        return Response({'id':str(conversation.pk),'access':str(access.pk)})


class PortalMessagesView(PortalView):
    def conversation(self):
        return get_object_or_404(m.ClientConversation,organization=self.org,access=self.access,active=True)
    def get(self,request):return messages(request,self.org,self.conversation())
    @transaction.atomic
    def post(self,request):
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        # Recheck suspension after acquiring the same lock used by administration.
        get_object_or_404(m.PortalAccess,pk=self.access.pk,organization=self.org,user=request.user,active=True)
        return send(request,self.org,self.conversation())
