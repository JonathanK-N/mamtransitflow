"""API cloisonnée. Auteur : Jonathan Kakesa (JonathanK-N)."""
import csv
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from django.core.exceptions import ValidationError as DjangoValidation
from django.db import transaction, IntegrityError, models
from django.db.models import Sum, Q, Count
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError,NotFound
from rest_framework.pagination import PageNumberPagination
from apps.comptes.models import Utilisateur
from . import models as m, services, security
from .serializers import RESOURCES, serializer_for, OrganizationSerializer

LABELS={'partners':'Clients et fournisseurs','employees':'Personnel','vehicles':'Flotte','orders':'Commandes',
    'routes':'Lignes et circuits','missions':'Missions','bookings':'Réservations','maintenance':'Entretien',
    'expenses':'Dépenses','invoices':'Facturation','payments':'Règlements','accounts':'Plan de comptes',
    'journal':'Comptabilité','stock':'Stocks et pièces','movements':'Mouvements de stock','purchases':'Achats',
    'documents':'Documents','audit':'Journal d’audit'}
ACTIONS={'orders':{'draft':['confirm','cancel'],'confirmed':['cancel']},
    'missions':{'planned':['start','cancel'],'active':['complete']},
    'maintenance':{'planned':['start','cancel'],'active':['complete','cancel']},
    'invoices':{'draft':['issue','cancel']},'journal':{'draft':['post']},
    'expenses':{'draft':['approve']},'bookings':{'confirmed':['board','cancel']},
    'purchases':{'draft':['order','cancel'],'ordered':['receive','cancel']}}


class Page(PageNumberPagination):
    page_size=25
    page_size_query_param='page_size'
    max_page_size=100


class ScopedView(APIView):
    permission_classes=[IsAuthenticated]
    @transaction.atomic
    def dispatch(self,*args,**kwargs):
        response=super().dispatch(*args,**kwargs)
        if response.status_code>=400:transaction.set_rollback(True)
        response['Cache-Control']='no-store'
        return response
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        self.member=security.membership(request);self.org=self.member.organization
    def context(self):return {'organization':self.org,'request':self.request}
    def ensure(self,resource,write=False):
        if resource=='audit' and self.member.role not in ('owner','admin'):raise PermissionDenied('Journal réservé à l’administration.')
        if not security.allowed(self.member.role,resource,write):raise PermissionDenied('Votre rôle ne permet pas cette opération.')
    def queryset(self,resource):
        self.ensure(resource)
        model=RESOURCES.get(resource)
        if not model:raise NotFound('Module introuvable.')
        qs=model.objects.filter(organization=self.org)
        if self.member.role=='driver':
            if model is m.Mission:qs=qs.filter(driver__user=self.request.user)
            elif model is m.Document:qs=qs.filter(mission__driver__user=self.request.user).exclude(category='finance')
        return qs.select_related(*[f.name for f in model._meta.fields if isinstance(f,models.ForeignKey)])
    def handle_exception(self,exc):
        if isinstance(exc,(IntegrityError,ProtectedError)):exc=ValidationError('Opération en conflit avec une référence existante ou une autre opération. Actualisez puis réessayez.')
        if isinstance(exc,DjangoValidation):exc=ValidationError(getattr(exc,'message_dict',exc.messages))
        return super().handle_exception(exc)


class CatalogView(ScopedView):
    def get(self,request):
        result=[]
        for resource,model in RESOURCES.items():
            if not security.allowed(self.member.role,resource) or resource=='audit' and self.member.role not in ('owner','admin'):continue
            serializer=serializer_for(model)(context=self.context())
            fields=[]
            for name,field in serializer.fields.items():
                if name in ('id','label','relations','created_at','updated_at','actor'):continue
                dbfield=model._meta.get_field(name)
                kind='text'
                if isinstance(dbfield,models.DateTimeField):kind='datetime-local'
                elif isinstance(dbfield,models.DateField):kind='date'
                elif isinstance(dbfield,models.BooleanField):kind='checkbox'
                elif isinstance(dbfield,(models.DecimalField,models.IntegerField)):kind='number'
                elif isinstance(dbfield,models.TextField):kind='textarea'
                elif isinstance(dbfield,models.JSONField):kind='json'
                elif isinstance(dbfield,models.FileField):kind='file'
                elif isinstance(dbfield,models.EmailField):kind='email'
                relation=next((k for k,v in RESOURCES.items() if v is getattr(dbfield,'related_model',None)),None)
                options=[{'value':x,'label':y} for x,y in (dbfield.choices or [])]
                if relation:kind='relation'
                elif options:kind='select'
                if name=='user':
                    kind='select'
                    options=[{'value':'','label':'Aucun compte associé'}]+[{'value':x.user_id,'label':x.user.nom+' · '+x.user.courriel}
                        for x in m.Membership.objects.filter(organization=self.org,active=True).select_related('user')]
                default=dbfield.get_default() if dbfield.has_default() else None
                if default is models.NOT_PROVIDED:default=None
                fields.append({'name':name,'label':str(dbfield.verbose_name),'type':kind,'required':field.required,
                    'readonly':field.read_only,'relation':relation,'options':options,'default':default})
            result.append({'key':resource,'label':LABELS[resource],'fields':fields,
                'writable':security.allowed(self.member.role,resource,True) and resource!='audit',
                'canAct':resource=='missions' and self.member.role=='driver',
                'canTrack':resource=='missions' and self.member.role in ('owner','admin','operations','driver'),
                'userId':request.user.pk,
                'actions':ACTIONS.get(resource,{})})
        return Response({'resources':result,'countries':m.COUNTRIES,'activities':m.ACTIVITIES,'roles':m.ROLES})


class ResourceView(ScopedView):
    def get(self,request,resource,pk=None):
        qs=self.queryset(resource);serializer=serializer_for(RESOURCES[resource])
        if pk:return Response(serializer(get_object_or_404(qs,pk=pk),context=self.context()).data)
        search=request.query_params.get('q','').strip()[:150]
        if search:
            query=Q()
            for f in RESOURCES[resource]._meta.fields:
                if isinstance(f,models.CharField):query|=Q(**{f'{f.name}__icontains':search})
            qs=qs.filter(query)
        if request.query_params.get('status') and hasattr(RESOURCES[resource],'status'):
            qs=qs.filter(status=request.query_params['status'])
        for key in ('vehicle','mission','customer','driver','item','order'):
            value=request.query_params.get(key)
            if value and any(f.name==key for f in RESOURCES[resource]._meta.fields):
                try:qs=qs.filter(**{key:value})
                except (ValueError,DjangoValidation):raise ValidationError('Filtre invalide.')
        paginator=Page();page=paginator.paginate_queryset(qs,request)
        return paginator.get_paginated_response(serializer(page,many=True,context=self.context()).data)
    def post(self,request,resource,pk=None):
        if pk:raise ValidationError('Utilisez PATCH pour modifier une fiche.')
        self.ensure(resource,True)
        if resource=='audit':raise PermissionDenied('Le journal est immuable.')
        model=RESOURCES.get(resource)
        if not model:raise NotFound()
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        serializer=serializer_for(model)(data=request.data,context=self.context());serializer.is_valid(raise_exception=True)
        if model is m.Payment:obj=services.payment(self.org,request.user,serializer.validated_data)
        elif model is m.StockMovement:obj=services.stock_move(self.org,request.user,serializer.validated_data)
        elif model is m.Booking:obj=services.booking(self.org,request.user,serializer.validated_data)
        else:
            obj=serializer.save(organization=self.org);services.audit(self.org,request.user,'create',obj)
        return Response(serializer_for(model)(obj,context=self.context()).data,status=201)
    def patch(self,request,resource,pk):
        self.ensure(resource,True)
        if resource=='audit':raise PermissionDenied('Le journal est immuable.')
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        obj=get_object_or_404(self.queryset(resource).select_for_update(of=('self',)),pk=pk)
        serializer=serializer_for(RESOURCES[resource])(obj,data=request.data,partial=True,context=self.context())
        serializer.is_valid(raise_exception=True);serializer.save();services.audit(self.org,request.user,'update',obj,fields=list(serializer.validated_data))
        return Response(serializer.data)
    def delete(self,request,resource,pk):
        self.ensure(resource,True)
        if resource in ('audit','payments','movements','bookings','journal','accounts'):raise PermissionDenied('Historique conservé ; suppression interdite.')
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        obj=get_object_or_404(self.queryset(resource),pk=pk)
        if hasattr(obj,'status') and obj.status not in ('draft','planned','available','retired'):raise ValidationError('Cette fiche ne peut plus être supprimée.')
        services.audit(self.org,request.user,'delete',obj)
        obj.delete();return Response(status=204)


class ActionView(ScopedView):
    def post(self,request,resource,pk,action):
        if not (resource=='missions' and self.member.role=='driver' and action in ('start','complete')):
            self.ensure(resource,True)
        obj=get_object_or_404(self.queryset(resource),pk=pk)
        obj=services.transition(self.org,request.user,type(obj),obj.pk,action,request.data)
        return Response(serializer_for(type(obj))(obj,context=self.context()).data)


class OrganizationView(ScopedView):
    def get(self,request):return Response(OrganizationSerializer(self.org).data)
    def patch(self,request):
        if self.member.role not in ('owner','admin'):raise PermissionDenied()
        if 'currency' in request.data and request.data['currency']!=self.org.currency and (m.Invoice.objects.filter(organization=self.org).exists() or m.JournalEntry.objects.filter(organization=self.org).exists()):
            raise ValidationError('La devise ne peut pas changer après le début des écritures financières.')
        serializer=OrganizationSerializer(self.org,data=request.data,partial=True);serializer.is_valid(raise_exception=True);serializer.save()
        services.audit(self.org,request.user,'settings',self.org,fields=list(serializer.validated_data))
        return Response(serializer.data)


class DashboardView(ScopedView):
    def get(self,request):
        today=timezone.localdate();org=self.org
        missions=self.queryset('missions') if security.allowed(self.member.role,'missions') else m.Mission.objects.none()
        vehicles=m.Vehicle.objects.filter(organization=org)
        if self.member.role=='driver':vehicles=vehicles.filter(mission__driver__user=request.user).distinct()
        financial=security.allowed(self.member.role,'invoices')
        inv=m.Invoice.objects.filter(organization=org,kind='invoice').exclude(status__in=['draft','cancelled'])
        balance=sum((x.total-x.paid for x in inv),Decimal(0)) if financial else None
        credits=m.Invoice.objects.filter(organization=org,kind='credit',status='issued').aggregate(s=Sum('total'))['s'] or 0
        if balance is not None:balance-=credits
        alerts=[]
        for v in vehicles:
            for field,label in [('insurance_expiry','Assurance'),('inspection_expiry','Visite technique')]:
                expiry=getattr(v,field)
                if expiry and expiry<=today+timedelta(days=30):alerts.append({'label':f'{label} · {v.plate}','date':expiry,'resource':'vehicles','id':str(v.pk),'overdue':expiry<today})
        if security.allowed(self.member.role,'stock'):
            for item in m.StockItem.objects.filter(organization=org,quantity__lte=models.F('minimum'))[:10]:
                alerts.append({'label':f'Stock bas · {item.name}','resource':'stock','id':str(item.pk)})
        return Response({'fleet':vehicles.count(),'active':missions.filter(status='active').count(),
            'planned':missions.filter(status='planned').count(),'receivable':balance,'currency':org.currency,
            'missions':serializer_for(m.Mission)(missions.order_by('departure')[:8],many=True,context=self.context()).data,
            'alerts':alerts[:20],'activity':list(missions.values('status').annotate(count=Count('id'))),
            'organization':OrganizationSerializer(org).data})


class ReportsView(ScopedView):
    def get(self,request):
        self.ensure('journal')
        start=request.query_params.get('start');end=request.query_params.get('end')
        entries=m.JournalEntry.objects.filter(organization=self.org,status='posted')
        if start:entries=entries.filter(date__gte=start)
        if end:entries=entries.filter(date__lte=end)
        balances={a.code:{'code':a.code,'name':a.name,'debit':Decimal(0),'credit':Decimal(0)} for a in m.Account.objects.filter(organization=self.org)}
        for entry in entries:
            for line in entry.lines:
                row=balances[line['account']];row['debit']+=Decimal(line['debit']);row['credit']+=Decimal(line['credit'])
        for row in balances.values():row['balance']=row['debit']-row['credit']
        missions=[]
        orders=m.TransportOrder.objects.filter(organization=self.org).select_related('customer')
        if start:orders=orders.filter(planned_date__gte=start)
        if end:orders=orders.filter(planned_date__lte=end)
        costs=dict(m.Expense.objects.filter(organization=self.org,status='approved',mission__order__isnull=False)
            .values('mission__order').annotate(total=Sum('amount')).values_list('mission__order','total'))
        for order in orders.iterator():
            cost=costs.get(order.pk,0)
            missions.append({'reference':order.reference,'customer':order.customer.name,'revenue':order.amount,'cost':cost,'margin':order.amount-cost})
        return Response({'trial_balance':list(balances.values()),'profitability':missions,'currency':self.org.currency,
            'note':'Rentabilité commerciale : prix convenu moins dépenses de mission validées, hors charges indirectes.'})


class ExportView(ScopedView):
    def get(self,request,resource):
        if resource=='documents':raise ValidationError('Téléchargez les documents individuellement.')
        qs=self.queryset(resource);model=RESOURCES[resource]
        fields=[f.name for f in model._meta.fields if f.name not in ('organization','file')]
        response=HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="transitflow-{resource}.csv"';response.write('\ufeff')
        writer=csv.writer(response,delimiter=';');writer.writerow(fields)
        for obj in qs.iterator(chunk_size=500):
            values=[]
            for field in fields:
                val=str(getattr(obj,field) or '')
                if val.lstrip()[:1] in ('=','+','-','@'):val="'"+val
                values.append(val)
            writer.writerow(values)
        services.audit(self.org,request.user,'export',self.org,module=resource)
        return response


class DownloadView(ScopedView):
    def get(self,request,pk):
        obj=get_object_or_404(self.queryset('documents'),pk=pk)
        response=FileResponse(obj.file.open('rb'),as_attachment=True,filename=obj.title+Path(obj.file.name).suffix)
        response['X-Content-Type-Options']='nosniff';return response


class TeamView(ScopedView):
    def check(self):
        if self.member.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
    def get(self,request):
        self.check()
        return Response({'members':[{'id':x.pk,'name':x.user.nom,'email':x.user.courriel,'role':x.role,'active':x.active}
            for x in m.Membership.objects.filter(organization=self.org).select_related('user')],
            'invitations':[{'id':x.pk,'email':x.email,'role':x.role,'expires_at':x.expires_at,'used':bool(x.used_at)} for x in m.TeamInvitation.objects.filter(organization=self.org)]})
    def post(self,request):
        self.check();from rest_framework import serializers
        email=serializers.EmailField().run_validation(request.data.get('email')).lower()
        role=request.data.get('role','viewer')
        if role not in dict(m.ROLES) or role=='owner':raise ValidationError('Rôle invalide.')
        token=secrets.token_urlsafe(32)
        m.TeamInvitation.objects.filter(organization=self.org,email=email,used_at__isnull=True).update(expires_at=timezone.now())
        invite=m.TeamInvitation.objects.create(organization=self.org,email=email,role=role,
            digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=7))
        services.audit(self.org,request.user,'invite',invite)
        from apps.comptes.invitations import envoyer
        link=request.build_absolute_uri('/app')+'?invitation='+token
        sent=envoyer(email,f'Invitation à {self.org.name}',f'Rejoignez votre entreprise sur TransitFlow : {link}', '')
        return Response({'link':link,'sent':sent},status=201)
    def patch(self,request):
        self.check();m.Organization.objects.select_for_update().get(pk=self.org.pk)
        member=get_object_or_404(m.Membership,pk=request.data.get('id'),organization=self.org)
        role=request.data.get('role',member.role);active=request.data.get('active',member.active)
        if not isinstance(active,bool) or role not in dict(m.ROLES):raise ValidationError('Rôle ou état invalide.')
        if (member.role=='owner' or role=='owner') and self.member.role!='owner':raise PermissionDenied('Seul un propriétaire gère les propriétaires.')
        if member.role=='owner' and (role!='owner' or not active) and m.Membership.objects.filter(organization=self.org,role='owner',active=True).count()<=1:
            raise ValidationError('Conservez au moins un propriétaire actif.')
        member.role=role;member.active=active;member.save();services.audit(self.org,request.user,'membership',member,role=role,active=active)
        return Response({'ok':True})


class AcceptInvitationView(APIView):
    permission_classes=[IsAuthenticated]
    @transaction.atomic
    def post(self,request):
        digest=hashlib.sha256(str(request.data.get('token','')).encode()).hexdigest()
        invite=get_object_or_404(m.TeamInvitation.objects.select_for_update(),digest=digest)
        if invite.email.lower()!=request.user.courriel.lower():raise PermissionDenied('Connectez-vous avec le courriel invité.')
        if invite.used_at or invite.expires_at<timezone.now():raise ValidationError('Invitation expirée ou déjà utilisée.')
        security.set_scope(invite.organization_id)
        existing=m.Membership.objects.filter(organization=invite.organization,user=request.user).first()
        if existing:raise ValidationError('Vous êtes déjà membre de cette entreprise. Contactez son administrateur.')
        m.Membership.objects.create(organization=invite.organization,user=request.user,role=invite.role)
        invite.used_at=timezone.now();invite.save(update_fields=['used_at'])
        return Response({'organization':str(invite.organization_id)})


class PositionsView(ScopedView):
    def get(self,request,pk):
        mission=get_object_or_404(self.queryset('missions'),pk=pk)
        qs=m.Position.objects.filter(organization=self.org,mission=mission).order_by('-timestamp')[:2000]
        return Response({'positions':list(qs.values('timestamp','latitude','longitude'))})
    def post(self,request,pk):
        mission=get_object_or_404(self.queryset('missions'),pk=pk)
        if self.member.role=='viewer' or self.member.role=='driver' and mission.driver.user_id!=request.user.pk:raise PermissionDenied()
        if self.member.role not in ('owner','admin','operations','driver'):raise PermissionDenied()
        points=request.data.get('positions')
        if not isinstance(points,list) or not 1<=len(points)<=200:raise ValidationError('Entre 1 et 200 positions requises.')
        from rest_framework import serializers
        now=timezone.now()
        if mission.status not in ('active','completed') or mission.completed_at and now>mission.completed_at+timedelta(hours=24):
            raise ValidationError('Fenêtre de synchronisation fermée.')
        new=[]
        for point in points:
            if not isinstance(point,dict):raise ValidationError('Position invalide.')
            timestamp=serializers.DateTimeField().run_validation(point.get('timestamp'))
            lat=services.decimal(point.get('latitude'));lng=services.decimal(point.get('longitude'))
            end=mission.completed_at or now+timedelta(minutes=2)
            if not -90<=lat<=90 or not -180<=lng<=180 or not mission.started_at-timedelta(minutes=10)<=timestamp<=end:
                raise ValidationError('Position hors limites du trajet.')
            new.append(m.Position(organization=self.org,mission=mission,timestamp=timestamp,latitude=lat,longitude=lng))
        m.Position.objects.bulk_create(new,ignore_conflicts=True)
        return Response({'accepted':len(new)})
