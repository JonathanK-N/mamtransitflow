"""
TransitFlow — Routes de connexion
Auteur : Jonathan K-N

  POST /api/auth/connexion   -> verifie courriel/motDePasse/role, renvoie
                                {ok, session, jeton, rafraichissement, accueil}
  POST /api/auth/rafraichir  -> echange un jeton de rafraichissement contre un nouveau jeton d acces
  POST /api/auth/deconnexion -> met le jeton de rafraichissement sur liste noire
  GET  /api/auth/session     -> renvoie la session du jeton envoye (verifie qu il est toujours valide)
  POST /api/auth/comptes     -> cree un compte de connexion (reserve a 'fleet.admin')

Les jetons sont des JWT (djangorestframework-simplejwt) : un jeton d acces
court (envoye a chaque requete) et un jeton de rafraichissement de 7 jours,
que assets/js/store.js utilise pour renouveler le jeton d acces sans
redemander le mot de passe. A la deconnexion, le jeton de rafraichissement
est mis sur liste noire et ne peut plus servir.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Utilisateur
from .permissions import DansGroupe, EstConnecte
from .serializers import CompteEntreeSerializer, ConnexionSerializer, SessionSerializer


class ConnexionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        entree = ConnexionSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = entree.validated_data

        # Le courriel est stocke en minuscules : la casse saisie n a pas d importance.
        utilisateur = authenticate(request, courriel=donnees['courriel'].strip().lower(),
                                   password=donnees['motDePasse'])
        if not utilisateur:
            return Response({'ok': False, 'message': 'Courriel ou mot de passe incorrect.'},
                             status=status.HTTP_401_UNAUTHORIZED)

        role_demande = donnees.get('role')
        session = SessionSerializer(utilisateur).data
        if role_demande and session['role'] != role_demande:
            return Response({'ok': False, 'message': f'Ce compte n est pas un compte {role_demande}.'},
                             status=status.HTTP_401_UNAUTHORIZED)

        rafraichissement = RefreshToken.for_user(utilisateur)
        accueil = 'admin/tableau-de-bord.html' if session['role'] == 'admin' else 'chauffeur/mes-trajets.html'
        return Response({'ok': True, 'session': session, 'jeton': str(rafraichissement.access_token),
                         'rafraichissement': str(rafraichissement), 'accueil': accueil})


class RafraichirView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        entree = TokenRefreshSerializer(data={'refresh': request.data.get('rafraichissement', '')})
        try:
            entree.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, ValidationError):
            return Response({'ok': False, 'message': 'Session expiree, veuillez vous reconnecter.'},
                             status=status.HTTP_401_UNAUTHORIZED)
        donnees = entree.validated_data
        # Avec ROTATE_REFRESH_TOKENS, un nouveau jeton de rafraichissement est
        # emis a chaque fois et l ancien part sur liste noire.
        return Response({'ok': True, 'jeton': donnees['access'],
                         'rafraichissement': donnees.get('refresh', request.data.get('rafraichissement'))})


class DeconnexionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            RefreshToken(request.data.get('rafraichissement', '')).blacklist()
        except TokenError:
            pass  # jeton deja expire ou invalide : la session est terminee de toute facon
        return Response({'ok': True})


class SessionView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request):
        return Response({'ok': True, 'session': SessionSerializer(request.user).data})


class CreerCompteView(APIView):
    permission_classes = [DansGroupe('fleet.admin')]

    def post(self, request):
        entree = CompteEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = entree.validated_data

        if Utilisateur.objects.filter(courriel__iexact=donnees['courriel']).exists():
            return Response({'ok': False, 'message': 'Un compte existe deja avec ce courriel.'},
                             status=status.HTTP_400_BAD_REQUEST)

        groupes = Group.objects.filter(name__in=donnees['groupes'])
        if groupes.count() != len(set(donnees['groupes'])):
            return Response({'ok': False, 'message': 'Groupe de permission inconnu.'},
                             status=status.HTTP_400_BAD_REQUEST)

        chauffeur = None
        if donnees.get('chauffeurId'):
            from apps.drivers.models import Chauffeur
            chauffeur = Chauffeur.depuis_code(donnees['chauffeurId'])
            if not chauffeur:
                return Response({'ok': False, 'message': 'Chauffeur introuvable.'},
                                 status=status.HTTP_404_NOT_FOUND)

        utilisateur = Utilisateur.objects.create_user(
            courriel=donnees['courriel'], mot_de_passe=donnees['motDePasse'],
            nom=donnees.get('nom', ''), chauffeur=chauffeur
        )
        utilisateur.groups.set(groupes)
        return Response({'ok': True, 'compte': SessionSerializer(utilisateur).data},
                         status=status.HTTP_201_CREATED)
