"""API cloisonnée. Auteur : Jonathan Kakesa (JonathanK-N)."""
import csv
import hashlib
import secrets
from collections.abc import Mapping
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

LABELS={'leave':'Congés et absences','advances':'Avances du personnel','periods':'Périodes comptables','statements':'Rapprochement bancaire','contracts':'Contrats de transport','pricing':'Grilles tarifaires','subcontracts':'Sous-traitance','incidents':'Incidents et sinistres',
    'supplier-bills':'Factures fournisseurs','supplier-payments':'Règlements fournisseurs',
    'partners':'Clients et fournisseurs','employees':'Personnel','vehicles':'Flotte','orders':'Commandes',
    'routes':'Lignes et circuits','missions':'Missions','bookings':'Réservations','maintenance':'Entretien',
    'expenses':'Dépenses','invoices':'Facturation','payments':'Règlements','accounts':'Plan de comptes',
    'journal':'Comptabilité','stock':'Stocks et pièces','movements':'Mouvements de stock','purchases':'Achats',
    'documents':'Documents','audit':'Journal d’audit'}
ACTIONS={'leave':{'draft':['submit','cancel'],'submitted':['approve','reject','cancel'],'approved':['cancel']},
    'advances':{'draft':['approve','cancel'],'approved':['disburse','cancel'],'disbursed':['settle']},
    'periods':{'draft':['close']},'statements':{'draft':['match'],'matched':['unmatch']},'contracts':{'draft':['activate','close'],'active':['generate','pause','close'],'paused':['activate','close']},
    'subcontracts':{'draft':['approve','cancel'],'approved':['complete','cancel']},'incidents':{'draft':['report'],'reported':['resolve']},
    'supplier-bills':{'draft':['post','cancel']},'orders':{'draft':['price','confirm','cancel'],'confirmed':['cancel']},
    'missions':{'planned':['start','cancel'],'active':['complete']},
    'maintenance':{'planned':['start','cancel'],'active':['complete','cancel']},
    'invoices':{'draft':['issue','cancel']},'journal':{'draft':['post']},
    'expenses':{'draft':['approve']},'bookings':{'confirmed':['board','cancel']},
    'purchases':{'draft':['order','cancel'],'ordered':['receive','cancel']}}
ACTION_FIELDS={
    'leave':{'reject':[{'name':'decision_note','label':'Motif du refus','type':'textarea','required':True}]},
    'advances':{action:[{'name':'reference','label':'Référence du justificatif','type':'text','required':True},{'name':'date','label':'Date réelle du mouvement','type':'date','required':True}] for action in ('disburse','settle')},
    'periods':{'close':[{'name':'closing_note','label':'Note de clôture (verrouillage définitif)','type':'textarea','required':True}]},
    'statements':{'match':[{'name':'journal','label':'Écriture comptabilisée','type':'relation','resource':'journal','required':True},{'name':'note','label':'Note de rapprochement','type':'textarea','required':True}],
        'unmatch':[{'name':'note','label':'Motif de dérapprochement','type':'textarea','required':True}]},
    'orders':{'price':[{'name':'pricing_rule','label':'Grille tarifaire','type':'relation','resource':'pricing','required':True}]},
    'subcontracts':{'complete':[{'name':'completion_note','label':'Bilan de prestation','type':'textarea','required':True}]},
    'incidents':{'resolve':[{'name':'resolution','label':'Mesures prises et résolution','type':'textarea','required':True}]},
}


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
        if request.method in ('POST','PATCH','DELETE') and not isinstance(request.data,Mapping):
            raise ValidationError('Le corps de la requête doit être un objet contenant les champs attendus.')
        self.member=security.membership(request);self.org=self.member.organization
        if request.method in ('POST','PATCH','DELETE'):
            m.Organization.objects.select_for_update().get(pk=self.org.pk)
            self.member=security.membership(request)
        from .applications import active_keys
        self.active_applications=active_keys(self.org)
    def context(self):return {'organization':self.org,'request':self.request}
    def enabled(self,resource):
        from .applications import resource_enabled
        return resource_enabled(self.org,resource,self.active_applications)
    def ensure(self,resource,write=False):
        if not self.enabled(resource):raise PermissionDenied('Cette application est désactivée pour votre entreprise.')
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
            if not self.enabled(resource):continue
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
                'action_fields':ACTION_FIELDS.get(resource,{}),
                'actions':{state:[action for action in actions if (action!='price' or self.enabled('pricing')) and not (resource=='periods' and action=='close' and self.member.role not in ('owner','admin'))] for state,actions in ACTIONS.get(resource,{}).items()}})
        return Response({'customer_portal':'customer-portal' in self.active_applications,'resources':result,'countries':m.COUNTRIES,'activities':m.ACTIVITIES,'roles':m.ROLES})


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
        elif model is m.SupplierPayment:
            from .business import supplier_payment
            obj=supplier_payment(self.org,request.user,serializer.validated_data)
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
        if resource in ('employees','audit','payments','supplier-payments','movements','bookings','journal','accounts'):raise PermissionDenied('Historique conservé ; suppression interdite.')
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        obj=get_object_or_404(self.queryset(resource),pk=pk)
        if hasattr(obj,'status') and obj.status not in ('draft','planned','available','retired'):raise ValidationError('Cette fiche ne peut plus être supprimée.')
        services.audit(self.org,request.user,'delete',obj)
        obj.delete();return Response(status=204)


class ActionView(ScopedView):
    def post(self,request,resource,pk,action):
        if resource=='periods' and action=='close' and self.member.role not in ('owner','admin'):raise PermissionDenied('Clôture réservée à l’administration.')
        if resource=='orders' and action=='price':self.ensure('pricing')
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
        missions=self.queryset('missions') if self.enabled('missions') and security.allowed(self.member.role,'missions') else m.Mission.objects.none()
        vehicles=m.Vehicle.objects.filter(organization=org) if self.enabled('vehicles') else m.Vehicle.objects.none()
        if self.member.role=='driver':vehicles=vehicles.filter(mission__driver__user=request.user).distinct()
        financial=self.enabled('invoices') and security.allowed(self.member.role,'invoices')
        inv=m.Invoice.objects.filter(organization=org,kind='invoice').exclude(status__in=['draft','cancelled'])
        balance=sum((x.total-x.paid for x in inv),Decimal(0)) if financial else None
        credits=m.Invoice.objects.filter(organization=org,kind='credit',status='issued').aggregate(s=Sum('total'))['s'] or 0
        if balance is not None:balance-=credits
        alerts=[]
        for v in vehicles:
            for field,label in [('insurance_expiry','Assurance'),('inspection_expiry','Visite technique')]:
                expiry=getattr(v,field)
                if expiry and expiry<=today+timedelta(days=30):alerts.append({'label':f'{label} · {v.plate}','date':expiry,'resource':'vehicles','id':str(v.pk),'overdue':expiry<today})
        if self.enabled('stock') and security.allowed(self.member.role,'stock'):
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
        subcontract_costs=dict(m.Subcontract.objects.filter(organization=self.org,status='completed',mission__order__isnull=False)
            .values('mission__order').annotate(total=Sum('agreed_amount')).values_list('mission__order','total'))
        for order in orders.iterator():
            cost=costs.get(order.pk,0)+subcontract_costs.get(order.pk,0)
            missions.append({'reference':order.reference,'customer':order.customer.name,'revenue':order.amount,'cost':cost,'margin':order.amount-cost})
        return Response({'trial_balance':list(balances.values()),'profitability':missions,'currency':self.org.currency,
            'note':'Rentabilité commerciale : prix convenu moins dépenses de mission validées et sous-traitances réalisées, hors charges indirectes.'})


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
            'invitations':[{'id':x.pk,'email':x.email,'role':x.role,'expires_at':x.expires_at,'used':bool(x.used_at)} for x in m.TeamInvitation.objects.filter(organization=self.org).exclude(role='client')]})
    def post(self,request):
        self.check();from rest_framework import serializers
        email=serializers.EmailField().run_validation(request.data.get('email')).lower()
        role=request.data.get('role','viewer')
        if role not in dict(m.ROLES) or role=='owner':raise ValidationError('Rôle invalide.')
        if role=='admin' and self.member.role!='owner':raise PermissionDenied('Seul un propriétaire invite un administrateur.')
        token=secrets.token_urlsafe(32)
        m.TeamInvitation.objects.filter(organization=self.org,email=email,used_at__isnull=True).exclude(role='client').update(expires_at=timezone.now())
        invite=m.TeamInvitation.objects.create(organization=self.org,email=email,role=role,
            digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=7))
        services.audit(self.org,request.user,'invite',invite)
        from .invitation_email import send_invitation
        link=request.build_absolute_uri('/app')+'?invitation='+token
        sent=send_invitation(request,invite,link)
        return Response({'link':link,'sent':sent},status=201)
    def patch(self,request):
        self.check();m.Organization.objects.select_for_update().get(pk=self.org.pk)
        member=get_object_or_404(m.Membership,pk=request.data.get('id'),organization=self.org)
        role=request.data.get('role',member.role);active=request.data.get('active',member.active)
        if not isinstance(active,bool) or role not in dict(m.ROLES):raise ValidationError('Rôle ou état invalide.')
        if (member.role=='owner' or role=='owner') and self.member.role!='owner':raise PermissionDenied('Seul un propriétaire gère les propriétaires.')
        if member.role=='owner' and (role!='owner' or not active) and m.Membership.objects.filter(organization=self.org,role='owner',active=True).count()<=1:
            raise ValidationError('Conservez au moins un propriétaire actif.')
        if self.member.role!='owner' and (member.role=='admin' or role=='admin'):raise PermissionDenied('Seul un propriétaire gère les administrateurs.')
        if member.user_id==request.user.pk and not active:raise ValidationError('Vous ne pouvez pas retirer votre propre accès.')
        if member.active and not active:
            from .personnel import remove_employee
            employee=m.Employee.objects.filter(organization=self.org,user=member.user).first()
            if employee is None:raise ValidationError('Rattachez une fiche Personnel pour retirer cet accès.')
            remove_employee(self.org,self.member,employee)
        elif not member.active and active:raise ValidationError('Envoyez une nouvelle invitation pour rétablir cet accès.')
        member.role=role;member.active=active;member.save();services.audit(self.org,request.user,'membership',member,role=role,active=active)
        return Response({'ok':True})


class AcceptInvitationView(APIView):
    permission_classes=[IsAuthenticated]
    @transaction.atomic
    def post(self,request):
        digest=hashlib.sha256(str(request.data.get('token','')).encode()).hexdigest()
        candidate=get_object_or_404(m.TeamInvitation,digest=digest)
        security.set_scope(candidate.organization_id)
        m.Organization.objects.select_for_update().get(pk=candidate.organization_id)
        invite=get_object_or_404(m.TeamInvitation.objects.select_for_update(),pk=candidate.pk)
        if invite.email.lower()!=request.user.courriel.lower():raise PermissionDenied('Connectez-vous avec le courriel invité.')
        if invite.used_at or invite.canceled_at or invite.expires_at<=timezone.now():raise ValidationError('Invitation expirée ou déjà utilisée.')
        security.set_scope(invite.organization_id)
        security.grant_invitation(invite,request.user)
        invite.used_at=timezone.now();invite.save(update_fields=['used_at'])
        return Response({'organization':str(invite.organization_id)})
