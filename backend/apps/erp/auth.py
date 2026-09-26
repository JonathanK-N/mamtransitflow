"""Authentification SaaS. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidation
from django.db import transaction, IntegrityError
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError,InvalidToken
from apps.comptes.models import Utilisateur
from .models import Organization,Membership,AuthLimit,TeamInvitation
from .serializers import OrganizationSerializer
from .security import set_scope
from .services import setup_accounts


def limit(request,scope,maximum=10):
    raw=f'{scope}:{request.META.get("REMOTE_ADDR","")}'
    key=hashlib.sha256(raw.encode()).hexdigest()
    now=timezone.now()
    with transaction.atomic():
        counter,_=AuthLimit.objects.get_or_create(key=key,defaults={'expires_at':now+timedelta(minutes=15)})
        counter=AuthLimit.objects.select_for_update().get(pk=counter.pk)
        if counter.expires_at<=now:counter.count=0;counter.expires_at=now+timedelta(minutes=15)
        counter.count+=1;counter.save()
        blocked=counter.count>maximum
    if blocked:raise Throttled(wait=900,detail='Trop de tentatives. Réessayez plus tard.')


def session_data(user):
    memberships=Membership.objects.filter(user=user,active=True).select_related('organization')
    return {'user':{'id':user.pk,'name':user.nom,'email':user.courriel},
        'organizations':[dict(OrganizationSerializer(x.organization).data,role=x.role) for x in memberships]}


def token_response(request,user,status=200):
    refresh=RefreshToken.for_user(user)
    response=Response(dict(session_data(user),access=str(refresh.access_token),csrf=get_token(request)),status=status)
    response.set_cookie('tf_refresh',str(refresh),httponly=True,secure=not settings.DEBUG,
        samesite='Strict',path='/api/v2/auth/',max_age=7*86400)
    response['Cache-Control']='no-store'
    return response


class CsrfView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def get(self,request):return Response({'csrf':get_token(request)})


class RegisterView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        limit(request,'register',10)
        from rest_framework import serializers
        email=serializers.EmailField().run_validation(request.data.get('email'))
        email=email.strip().lower();password=str(request.data.get('password',''))
        name=str(request.data.get('name','')).strip()
        if not name or len(name)>150:raise ValidationError('Nom requis (150 caractères maximum).')
        try:validate_password(password,Utilisateur(courriel=email,nom=name))
        except DjangoValidation as exc:raise ValidationError({'password':exc.messages})
        invitation=str(request.data.get('invitation',''))
        data=request.data.get('organization',{})
        if not isinstance(data,dict):raise ValidationError('Entreprise invalide.')
        org_serializer=OrganizationSerializer(data=data)
        if not invitation:org_serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                invite=None
                if invitation:
                    invite=TeamInvitation.objects.select_for_update().filter(digest=hashlib.sha256(invitation.encode()).hexdigest()).first()
                    if not invite or invite.used_at or invite.expires_at<=timezone.now() or invite.email.lower()!=email:
                        raise ValidationError('Invitation invalide, expirée ou destinée à un autre courriel.')
                user=Utilisateur.objects.create_user(courriel=email,mot_de_passe=password,nom=name)
                if invite:
                    org=invite.organization
                    Membership.objects.create(organization=org,user=user,role=invite.role)
                    invite.used_at=timezone.now();invite.save(update_fields=['used_at'])
                else:
                    org=org_serializer.save(slug=(slugify(data.get('name',''))[:60] or 'entreprise')+'-'+secrets.token_hex(4))
                    Membership.objects.create(organization=org,user=user,role='owner')
                    set_scope(org.pk);setup_accounts(org)
        except IntegrityError:raise ValidationError('Ce courriel est déjà utilisé. Connectez-vous à votre compte.')
        return token_response(request,user,201)


class LoginView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        limit(request,'login',15)
        user=authenticate(request,courriel=str(request.data.get('email','')).strip().lower(),password=request.data.get('password',''))
        if not user:return Response({'detail':'Courriel ou mot de passe incorrect.'},status=401)
        return token_response(request,user)


@method_decorator(csrf_protect,name='dispatch')
class RefreshView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        serializer=TokenRefreshSerializer(data={'refresh':request.COOKIES.get('tf_refresh','')})
        try:serializer.is_valid(raise_exception=True)
        except (TokenError,InvalidToken,ValidationError):return Response({'detail':'Session expirée.'},status=401)
        result=serializer.validated_data
        response=Response({'access':result['access']})
        response.set_cookie('tf_refresh',result.get('refresh',''),httponly=True,secure=not settings.DEBUG,
            samesite='Strict',path='/api/v2/auth/',max_age=7*86400)
        response['Cache-Control']='no-store';return response


@method_decorator(csrf_protect,name='dispatch')
class LogoutView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        try:RefreshToken(request.COOKIES.get('tf_refresh','')).blacklist()
        except TokenError:pass
        response=Response({'ok':True});response.delete_cookie('tf_refresh',path='/api/v2/auth/',samesite='Strict');return response


class MeView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):return Response(session_data(request.user))


class PasswordRequestView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        limit(request,'password-request',5)
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from apps.comptes.invitations import envoyer
        user=Utilisateur.objects.filter(courriel__iexact=str(request.data.get('email','')).strip(),is_active=True).first()
        if user:
            token=default_token_generator.make_token(user)
            uid=urlsafe_base64_encode(force_bytes(user.pk))
            url=request.build_absolute_uri('/connexion')+f'?reset={uid}:{token}'
            envoyer(user.courriel,'TransitFlow — nouveau mot de passe',
                f'Pour choisir un nouveau mot de passe : {url}\nCe lien est personnel. Ignorez ce message si vous n’avez pas fait cette demande.','')
        return Response({'detail':'Si un compte correspond à ce courriel, un lien de réinitialisation lui sera envoyé.'})


class PasswordResetView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        limit(request,'password-reset',10)
        return self.reset(request)
    @transaction.atomic
    def reset(self,request):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_decode
        try:
            uid,token=str(request.data.get('token','')).split(':',1)
            pk=urlsafe_base64_decode(uid).decode()
            user=Utilisateur.objects.select_for_update().get(pk=pk,is_active=True)
        except (ValueError,TypeError,UnicodeError,Utilisateur.DoesNotExist):
            raise ValidationError('Lien invalide ou expiré.')
        if not default_token_generator.check_token(user,token):raise ValidationError('Lien invalide ou expiré.')
        password=str(request.data.get('password',''))
        try:validate_password(password,user)
        except DjangoValidation as exc:raise ValidationError({'password':exc.messages})
        user.set_password(password);user.save(update_fields=['password'])
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken,BlacklistedToken
        for outstanding in OutstandingToken.objects.filter(user=user):BlacklistedToken.objects.get_or_create(token=outstanding)
        return Response({'detail':'Mot de passe modifié. Connectez-vous avec votre nouveau mot de passe.'})
