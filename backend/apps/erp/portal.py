"""Portail privé des clients. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib
import secrets
from datetime import timedelta
from pathlib import Path
from django.http import FileResponse,HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from . import models as m,services,security
from .applications import active_keys
from .views import ScopedView,Page


def customer_data(partner):
    return dict(id=str(partner.pk),name=partner.name,email=partner.email,phone=partner.phone,contact_name=partner.contact_name)


def invitation_data(invite):
    state='accepted' if invite.used_at else 'canceled' if invite.canceled_at else 'expired' if invite.expires_at<=timezone.now() else 'pending'
    return dict(id=str(invite.pk),email=invite.email,customer=invite.partner.name,partner=str(invite.partner_id),status=state,expires_at=invite.expires_at)


class PortalInput(serializers.Serializer):
    email=serializers.EmailField(error_messages={'required':'Le courriel est requis.','null':'Le courriel est requis.','blank':'Le courriel est requis.','invalid':'Saisissez une adresse courriel valide.'})
    mode=serializers.ChoiceField(choices=['existing','new'],default='existing',error_messages={'invalid_choice':'Choisissez un client existant ou un nouveau client.'})
    partner=serializers.UUIDField(required=False,error_messages={'invalid':'Sélectionnez un client valide.'})
    name=serializers.CharField(required=False,max_length=150,error_messages={'blank':'Le nom du client est requis.','max_length':'150 caractères maximum.'})
    contact_name=serializers.CharField(required=False,allow_blank=True,max_length=150,error_messages={'max_length':'150 caractères maximum.'})
    phone=serializers.CharField(required=False,allow_blank=True,max_length=40,error_messages={'max_length':'40 caractères maximum.'})
    def validate(self,data):
        data['email']=data['email'].strip().lower()
        if data['mode']=='new' and not data.get('name'):raise ValidationError({'name':'Le nom du client est requis.'})
        if data['mode']=='existing' and not data.get('partner'):raise ValidationError({'partner':'Sélectionnez un client existant.'})
        return data


class PortalAdminView(ScopedView):
    def check(self):
        if self.member.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
        if 'customer-portal' not in self.active_applications:raise PermissionDenied('Le portail client est désactivé.')
    def customers(self):
        return m.Partner.objects.filter(organization=self.org,kind__in=['customer','both'],archived_at__isnull=True)
    def invitations(self):
        return m.TeamInvitation.objects.filter(organization=self.org,role='client',partner__organization=self.org).select_related('partner')
    def get(self,request,section=None):
        self.check()
        if section=='customers':
            from django.db.models import Q
            query=request.query_params.get('q','').strip()[:150]
            rows=self.customers().filter(Q(name__icontains=query)|Q(email__icontains=query)|Q(phone__icontains=query)|Q(contact_name__icontains=query)).order_by('name','id')
            output=customer_data
        elif section=='invitations':rows=self.invitations();output=invitation_data
        else:
            rows=m.PortalAccess.objects.filter(organization=self.org).select_related('user','partner')
            output=lambda x:dict(id=str(x.pk),name=x.user.nom,email=x.user.courriel,customer=x.partner.name,active=x.active)
        paginator=Page();page=paginator.paginate_queryset(rows,request)
        return paginator.get_paginated_response([output(x) for x in page])
    def issue(self,request,partner,email):
        token=secrets.token_urlsafe(32)
        invite=m.TeamInvitation.objects.create(organization=self.org,email=email,role='client',partner=partner,
            digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=7))
        services.audit(self.org,request.user,'portal-invite',invite,partner=str(partner.pk))
        link=request.build_absolute_uri('/app')+'?invitation='+token
        from .invitation_email import send_invitation
        sent=send_invitation(request,invite,link)
        return Response({'link':link,'sent':sent,'company':self.org.name,'customer':customer_data(partner),'invitation':invitation_data(invite)},status=201)
    def check_email(self,email):
        if m.Membership.objects.filter(organization=self.org,user__courriel__iexact=email).exists():
            raise ValidationError({'email':'Ce compte est déjà un collaborateur interne.'})
        if m.PortalAccess.objects.filter(organization=self.org,user__courriel__iexact=email,active=True).exists():
            raise ValidationError({'email':'Ce client dispose déjà d’un accès actif.'})
    def post(self,request,pk=None,action=None):
        self.check();m.Organization.objects.select_for_update().get(pk=self.org.pk)
        if pk:
            invite=get_object_or_404(self.invitations().select_for_update(),pk=pk)
            if invite.used_at:raise ValidationError('Cette invitation a déjà été acceptée.')
            if action=='cancel':
                invite.canceled_at=timezone.now();invite.expires_at=invite.canceled_at;invite.save(update_fields=['canceled_at','expires_at','updated_at'])
                services.audit(self.org,request.user,'portal-invite-cancel',invite)
                return Response({'ok':True})
            if invite.canceled_at:raise ValidationError('Cette invitation a été annulée. Créez une nouvelle invitation.')
            self.check_email(invite.email)
            invite.canceled_at=timezone.now();invite.expires_at=invite.canceled_at;invite.save(update_fields=['canceled_at','expires_at','updated_at'])
            services.audit(self.org,request.user,'portal-invite-resend',invite)
            self.invitations().filter(email__iexact=invite.email,used_at__isnull=True,canceled_at__isnull=True).update(expires_at=timezone.now(),canceled_at=timezone.now())
            return self.issue(request,invite.partner,invite.email)
        serializer=PortalInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data;email=data['email']
        partner=None
        if data['mode']=='existing':partner=get_object_or_404(self.customers(),pk=data['partner'])
        duplicate=self.customers().filter(email__iexact=email)
        if partner:duplicate=duplicate.exclude(pk=partner.pk)
        duplicate=duplicate.first()
        if duplicate:return Response({'detail':'Un client utilisant cette adresse existe déjà. Voulez-vous l’utiliser ?','code':'duplicate_customer','customer':customer_data(duplicate)},status=409)
        self.check_email(email)
        pending=self.invitations().filter(email__iexact=email,used_at__isnull=True,canceled_at__isnull=True,expires_at__gt=timezone.now()).first()
        if pending:return Response({'detail':'Une invitation est déjà en attente pour cette adresse. Utilisez Renvoyer l’invitation.','code':'pending_invitation','invitation':invitation_data(pending)},status=409)
        if partner:
            if partner.email!=email:
                partner.email=email;partner.save(update_fields=['email','updated_at'])
                services.audit(self.org,request.user,'portal-customer-email',partner)
        else:
            partner=m.Partner.objects.create(organization=self.org,kind='customer',name=data['name'],email=email,phone=data.get('phone',''),contact_name=data.get('contact_name',''))
            services.audit(self.org,request.user,'portal-customer-create',partner)
        return self.issue(request,partner,email)
    def patch(self,request):
        self.check();m.Organization.objects.select_for_update().get(pk=self.org.pk)
        access_id=serializers.UUIDField().run_validation(request.data.get('id'))
        access=get_object_or_404(m.PortalAccess,organization=self.org,pk=access_id)
        active=request.data.get('active')
        if type(active) is not bool:raise ValidationError('État invalide.')
        if active and m.Membership.objects.filter(organization=self.org,user=access.user,active=True).exists():
            raise ValidationError('Ce compte dispose désormais d’un accès interne.')
        access.active=active;access.save(update_fields=['active','updated_at'])
        if not active:
            m.TeamInvitation.objects.filter(organization=self.org,email__iexact=access.user.courriel,role='client',used_at__isnull=True,canceled_at__isnull=True).update(expires_at=timezone.now(),canceled_at=timezone.now())
        services.audit(self.org,request.user,'portal-access',access,active=active)
        return Response({'ok':True})


class PortalView(ScopedView):
    def initial(self,request,*args,**kwargs):
        APIView.initial(self,request,*args,**kwargs)
        org_id=request.headers.get('X-Organization')
        if not org_id:raise PermissionDenied('Sélectionnez votre prestataire.')
        self.access=get_object_or_404(m.PortalAccess.objects.select_related('organization','partner'),organization_id=org_id,user=request.user,active=True)
        self.org=self.access.organization
        security.set_scope(self.org.pk)
        self.active_applications=active_keys(self.org)
        if 'customer-portal' not in self.active_applications:raise PermissionDenied('Le portail client est actuellement désactivé.')

    def documents(self):
        from django.db.models import Q
        return m.Document.objects.filter(organization=self.org,shared_with_customer=True).filter(Q(customer=self.access.partner)|Q(customer__isnull=True,category='delivery',mission__order__customer=self.access.partner))

    def get(self,request,resource='orders',pk=None):
        partner=self.access.partner
        if resource=='receipt':
            receipt=get_object_or_404(m.DeliveryReceipt,organization=self.org,mission_id=pk,mission__order__customer=partner)
            from .delivery import render_pdf
            response=HttpResponse(render_pdf(receipt),content_type='application/pdf')
            response['Content-Disposition']=f'attachment; filename="livraison-{receipt.pk}.pdf"'
            response['X-Content-Type-Options']='nosniff'
            services.audit(self.org,request.user,'portal-receipt-download',receipt)
            return response
        if resource=='document':
            document=get_object_or_404(self.documents(),pk=pk)
            response=FileResponse(document.file.open('rb'),as_attachment=True,filename=document.title+Path(document.file.name).suffix)
            response['X-Content-Type-Options']='nosniff'
            services.audit(self.org,request.user,'portal-document-download',document)
            return response
        if pk is not None:raise NotFound('Section introuvable.')
        if resource=='orders':
            from django.db.models import Exists,OuterRef
            from .crm_services import invoice_balances
            missions=m.Mission.objects.filter(organization=self.org,order_id=OuterRef('pk'))
            invoices=m.Invoice.objects.filter(organization=self.org,order_id=OuterRef('pk'),kind='invoice',status__in=['issued','paid'])
            qs=m.TransportOrder.objects.filter(organization=self.org,customer=partner).exclude(status='draft').annotate(
                has_planned=Exists(missions.filter(status='planned')),has_active=Exists(missions.filter(status='active')),
                has_invoice=Exists(invoices),has_unpaid=Exists(invoice_balances(invoices).filter(remaining__gt=0)))
            def output(x):
                stage='paid' if x.has_invoice and not x.has_unpaid else 'invoiced' if x.has_invoice else 'delivered' if x.status=='completed' else 'in_progress' if x.has_active else 'planned' if x.has_planned else 'received'
                return dict(id=str(x.pk),reference=x.reference,origin=x.origin,destination=x.destination,planned_date=x.planned_date,quantity=x.quantity,unit=x.unit,amount=x.amount,status=x.status,stage=stage)
        elif resource=='deliveries':
            qs=m.Mission.objects.filter(organization=self.org,order__customer=partner).select_related('receipt')
            def output(x):return dict(id=str(x.pk),reference=x.reference,origin=x.origin,destination=x.destination,departure=x.departure,arrival=x.arrival,completed_at=x.completed_at,delivered_quantity=x.delivered_quantity,status=x.status,signed=hasattr(x,'receipt'))
        elif resource=='invoices':
            from .crm_services import invoice_balances,payment_state
            qs=invoice_balances(m.Invoice.objects.filter(organization=self.org,customer=partner,kind__in=['invoice','credit'],status__in=['issued','paid']))
            def output(x):return dict(id=str(x.pk),number=x.number,kind=x.kind,date=x.date,due_date=x.due_date,subtotal=x.subtotal,tax=x.tax,total=x.total,paid=x.paid,balance=str(max(0,x.remaining)),status=x.status,payment_state=payment_state(x),lines=x.lines,notes=x.notes)
        elif resource=='documents':
            qs=self.documents()
            def output(x):return dict(id=str(x.pk),title=x.title,created_at=x.created_at)
        else:raise NotFound('Section introuvable.')
        paginator=Page();page=paginator.paginate_queryset(qs,request)
        return paginator.get_paginated_response([output(x) for x in page])
