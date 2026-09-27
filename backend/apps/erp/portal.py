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


class PortalAdminView(ScopedView):
    def check(self):
        if self.member.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
        if 'customer-portal' not in self.active_applications:raise PermissionDenied('Le portail client est désactivé.')
    def get(self,request):
        self.check()
        access=m.PortalAccess.objects.filter(organization=self.org).select_related('user','partner')
        paginator=Page();page=paginator.paginate_queryset(access,request)
        return paginator.get_paginated_response([dict(id=str(x.pk),name=x.user.nom,email=x.user.courriel,customer=x.partner.name,active=x.active) for x in page])
    def post(self,request):
        self.check();m.Organization.objects.select_for_update().get(pk=self.org.pk)
        email=serializers.EmailField().run_validation(request.data.get('email')).strip().lower()
        partner_id=serializers.UUIDField().run_validation(request.data.get('partner'))
        partner=get_object_or_404(m.Partner,organization=self.org,pk=partner_id,kind__in=['customer','both'])
        if m.Membership.objects.filter(organization=self.org,user__courriel=email).exists():
            raise ValidationError('Ce compte est déjà un collaborateur interne.')
        if m.PortalAccess.objects.filter(organization=self.org,user__courriel=email,active=True).exists():
            raise ValidationError('Ce client dispose déjà d’un accès actif.')
        m.TeamInvitation.objects.filter(organization=self.org,email=email,used_at__isnull=True).update(expires_at=timezone.now())
        token=secrets.token_urlsafe(32)
        invite=m.TeamInvitation.objects.create(organization=self.org,email=email,role='client',partner=partner,
            digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=7))
        services.audit(self.org,request.user,'portal-invite',invite,partner=str(partner.pk))
        link=request.build_absolute_uri('/app')+'?invitation='+token
        from apps.comptes.invitations import envoyer
        sent=envoyer(email,f'Votre portail client - {self.org.name}',f'Accédez à vos commandes, livraisons et factures : {link}','')
        return Response({'link':link,'sent':sent},status=201)
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
            m.TeamInvitation.objects.filter(organization=self.org,email=access.user.courriel,role='client',used_at__isnull=True).update(expires_at=timezone.now())
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
        return m.Document.objects.filter(organization=self.org,shared_with_customer=True,category='delivery',mission__order__customer=self.access.partner)

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
            qs=m.TransportOrder.objects.filter(organization=self.org,customer=partner).exclude(status='draft')
            def output(x):return dict(id=str(x.pk),reference=x.reference,origin=x.origin,destination=x.destination,planned_date=x.planned_date,quantity=x.quantity,unit=x.unit,amount=x.amount,status=x.status)
        elif resource=='deliveries':
            qs=m.Mission.objects.filter(organization=self.org,order__customer=partner).select_related('receipt')
            def output(x):return dict(id=str(x.pk),reference=x.reference,origin=x.origin,destination=x.destination,departure=x.departure,arrival=x.arrival,completed_at=x.completed_at,delivered_quantity=x.delivered_quantity,status=x.status,signed=hasattr(x,'receipt'))
        elif resource=='invoices':
            qs=m.Invoice.objects.filter(organization=self.org,customer=partner,status__in=['issued','paid'])
            def output(x):return dict(id=str(x.pk),number=x.number,kind=x.kind,date=x.date,due_date=x.due_date,subtotal=x.subtotal,tax=x.tax,total=x.total,paid=x.paid,status=x.status,lines=x.lines,notes=x.notes)
        elif resource=='documents':
            qs=self.documents()
            def output(x):return dict(id=str(x.pk),title=x.title,created_at=x.created_at)
        else:raise NotFound('Section introuvable.')
        paginator=Page();page=paginator.paginate_queryset(qs,request)
        return paginator.get_paginated_response([output(x) for x in page])
