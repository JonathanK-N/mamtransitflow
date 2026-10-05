from decimal import Decimal
from django.db.models import Q, Sum, Max, F
from django.db.models import CharField, Value
from django.db.models.functions import Cast, Replace
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import models as m, services, security
from .serializers import serializer_for
from .views import ScopedView, Page
from .crm_services import quote_action, invoice_from_mission, invoice_balances


def event_data(event):
    actions={'create':'Création','update':'Modification','issue':'Document émis','confirm':'Commande confirmée','start':'Mission démarrée',
        'complete':'Mission terminée','payment':'Paiement enregistré','quote-accept':'Devis accepté','quote-refuse':'Devis refusé','quote-expire':'Devis expiré',
        'quote-convert':'Commande créée depuis le devis','invoice-draft-delivery':'Brouillon de facture créé depuis la livraison',
        'client-archive':'Client archivé','client-restore':'Client restauré','portal-invite':'Invitation au portail',
        'portal-invite-cancel':'Invitation annulée','portal-invite-resend':'Invitation renvoyée','portal-access':'Accès portail modifié'}
    label=actions.get(event.action,event.action)
    if event.resource=='document' and 'shared_with_customer' in event.detail.get('fields',[]):label='Partage du document modifié'
    if event.resource=='invoice' and event.action=='issue' and event.detail.get('kind')=='quote':label='Devis marqué envoyé'
    return dict(id=str(event.pk),action=event.action,label=label,reference=event.detail.get('reference',''),resource=event.resource,object_id=event.object_id,created_at=event.created_at)

def client_activity(org,customer,role,active):
    from django.db import connection
    from .applications import resource_enabled
    key='object_id' if connection.vendor=='postgresql' else 'object_key'
    def related(model,filters):
        ids=model.objects.filter(organization=org,**filters)
        text=Cast('id',CharField())
        if connection.vendor!='postgresql':text=Replace(text,Value('-'),Value(''))
        ids=ids.annotate(text_id=text).values('text_id')
        return Q(resource=model._meta.model_name,**{key+'__in':ids})
    conditions=Q(resource='partner',object_id=str(customer.pk))
    for resource,model,filters in [
        ('orders',m.TransportOrder,{'customer':customer}),
        ('missions',m.Mission,{'order__customer':customer}),
        ('missions',m.DeliveryReceipt,{'mission__order__customer':customer}),
        ('invoices',m.Invoice,{'customer':customer}),
        ('payments',m.Payment,{'invoice__customer':customer}),
        ('contacts',m.PartnerContact,{'customer':customer})]:
        if security.allowed(role,resource) and resource_enabled(org,resource,active):conditions|=related(model,filters)
    if security.allowed(role,'documents') and resource_enabled(org,'documents',active):
        docs=m.Document.objects.filter(organization=org).filter(Q(customer=customer)|Q(customer__isnull=True,mission__order__customer=customer))
        if not security.allowed(role,'invoices'):docs=docs.exclude(category='finance')
        text=Cast('id',CharField())
        if connection.vendor!='postgresql':text=Replace(text,Value('-'),Value(''))
        conditions|=Q(resource='document',**{key+'__in':docs.annotate(text_id=text).values('text_id')})
    if role in ('owner','admin') and 'customer-portal' in active:
        conditions|=related(m.TeamInvitation,{'partner':customer})|related(m.PortalAccess,{'partner':customer})
    return m.AuditEvent.objects.filter(organization=org).annotate(object_key=Replace('object_id',Value('-'),Value(''))).filter(conditions).order_by('-created_at','-id')


class ClientView(ScopedView):
    def client(self, pk, write=False):
        self.ensure('partners',write)
        return get_object_or_404(m.Partner, organization=self.org, pk=pk, kind__in=['customer','both'])

    def get(self, request, pk=None, section=None):
        self.ensure('partners')
        if not pk:
            q=request.query_params.get('q','').strip()[:150]
            rows=m.Partner.objects.filter(organization=self.org,kind__in=['customer','both'])
            if q:rows=rows.filter(Q(name__icontains=q)|Q(contact_name__icontains=q)|Q(email__icontains=q)|Q(phone__icontains=q)|Q(contacts__organization=self.org,contacts__name__icontains=q)|Q(contacts__organization=self.org,contacts__email__icontains=q)).distinct()
            archived=request.query_params.get('archived','false')
            if archived!='all':rows=rows.filter(archived_at__isnull=archived!='true')
            sort=request.query_params.get('sort','name')
            rows=rows.order_by(sort if sort in ('name','-name','created_at','-created_at') else 'name','id')
            page=Page();items=page.paginate_queryset(rows,request)
            return page.get_paginated_response(serializer_for(m.Partner)(items,many=True,context=self.context()).data)
        customer=self.client(pk)
        if section=='duplicates':raise ValidationError('Section invalide.')
        if section=='activity':
            rows=client_activity(self.org,customer,self.member.role,self.active_applications)
            page=Page();items=page.paginate_queryset(rows,request)
            return page.get_paginated_response([event_data(x) for x in items])
        tabs=['overview','activity']
        if security.allowed(self.member.role,'contacts'):tabs.insert(1,'contacts')
        for tab,resource in [('quotes','invoices'),('orders','orders'),('missions','missions'),('invoices','invoices'),('payments','payments'),('documents','documents')]:
            if tab=='quotes' and 'commercial' not in self.active_applications:continue
            if self.enabled(resource) and security.allowed(self.member.role,resource):tabs.append(tab)
        stats={}
        if 'orders' in tabs:stats['orders']=m.TransportOrder.objects.filter(organization=self.org,customer=customer).count()
        if 'missions' in tabs:stats['completed_missions']=m.Mission.objects.filter(organization=self.org,order__customer=customer,status='completed').count()
        if 'invoices' in tabs:
            invoices=invoice_balances(m.Invoice.objects.filter(organization=self.org,customer=customer,kind='invoice',status__in=['issued','paid']))
            sums=invoices.aggregate(billed=Sum('total'),paid=Sum('paid'),credited=Sum('credited_amount'))
            billed,paid=sums['billed'] or Decimal(0),sums['paid'] or Decimal(0)
            stats.update(invoices=invoices.count(),billed=str(billed),paid=str(paid),credited=str(sums['credited'] or Decimal(0)),balance=str(billed-paid-(sums['credited'] or Decimal(0))),
                unpaid=invoices.filter(remaining__gt=0).count(),late=invoices.filter(due_date__lt=timezone.localdate(),remaining__gt=0).count())
        portal=None
        if self.member.role in ('owner','admin') and 'customer-portal' in self.active_applications:
            from .portal import invitation_data
            access=m.PortalAccess.objects.filter(organization=self.org,partner=customer).select_related('user').first()
            pending=m.TeamInvitation.objects.filter(organization=self.org,partner=customer,role='client',used_at__isnull=True,canceled_at__isnull=True,expires_at__gt=timezone.now()).first()
            portal=dict(access=dict(id=str(access.pk),active=access.active,email=access.user.courriel) if access else None,invitation=invitation_data(pending) if pending else None)
        return Response(dict(customer=serializer_for(m.Partner)(customer,context=self.context()).data,stats=stats,tabs=tabs,portal=portal,
            can_contact=self.member.role in ('owner','admin','operations','finance') and 'customer-portal' in self.active_applications and m.PortalAccess.objects.filter(organization=self.org,partner=customer,active=True).exists(),
            last_activity=max(customer.updated_at,client_activity(self.org,customer,self.member.role,self.active_applications).aggregate(last=Max('created_at'))['last'] or customer.updated_at),writable=security.allowed(self.member.role,'partners',True)))

    def post(self,request,pk=None,section=None):
        if section=='duplicates':
            self.ensure('partners',True)
            rows=m.Partner.objects.filter(organization=self.org)
            email=str(request.data.get('email','')).strip()
            name=str(request.data.get('name','')).strip()
            phone=str(request.data.get('phone','')).strip()
            query=Q(pk__isnull=True)
            if email:query|=Q(email__iexact=email)
            if name:query|=Q(name__iexact=name)
            if len(name)>=4:query|=Q(name__icontains=name[:150])
            if phone:
                import re
                normalized=re.sub(r'\D','',phone)
                expression=F('phone')
                for separator in (' ','-','(',')','+','.'):
                    expression=Replace(expression,Value(separator),Value(''))
                rows=rows.annotate(normalized_phone=expression)
                if normalized:query|=Q(normalized_phone=normalized)
            return Response(serializer_for(m.Partner)(rows.filter(query)[:10],many=True,context=self.context()).data)
        customer=self.client(pk,True)
        if section not in ('archive','restore'):raise ValidationError('Action invalide.')
        customer.archived_at=timezone.now() if section=='archive' else None
        customer.save(update_fields=['archived_at','updated_at'])
        services.audit(self.org,request.user,'client-'+section,customer)
        return Response({'ok':True})


class CommercialActionView(ScopedView):
    def post(self,request,pk,section):
        if section=='invoice':
            self.ensure('invoices',True);self.ensure('missions')
            mission=get_object_or_404(self.queryset('missions'),pk=pk)
            obj=invoice_from_mission(self.org,request.user,mission)
        else:
            self.ensure('invoices',True)
            if 'commercial' not in self.active_applications:raise PermissionDenied('L’application commerciale est désactivée.')
            if section=='convert':self.ensure('orders',True)
            quote=get_object_or_404(self.queryset('invoices'),pk=pk,kind='quote')
            obj=quote_action(self.org,request.user,quote,section,request.data,request=request)
        return Response(serializer_for(type(obj))(obj,context=self.context()).data)
