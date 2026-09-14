"""
TransitFlow — Routes de connexion
Auteur : Jonathan K-N

  POST /api/auth/connexion -> verifie courriel/motDePasse/role, renvoie {ok, session, jeton, accueil}
  GET  /api/auth/session   -> renvoie la session du jeton envoye (verifie qu il est toujours valide)
  POST /api/auth/comptes   -> cree un compte de connexion (reserve a 'fleet.admin')

Le jeton est un JWT (djangorestframework-simplejwt) : il n y a pas de
table de sessions a gerer, il suffit qu il soit signe et non expire.
Comme dans la version precedente, il n y a pas de route /deconnexion :
le front-end oublie simplement le jeton localement (voir assets/js/auth.js).
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from .models import Utilisateur
from .permissions import DansGroupe, EstConnecte
from .serializers import CompteEntreeSerializer, ConnexionSerializer, SessionSerializer


class ConnexionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        entree = ConnexionSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = entree.validated_data

        utilisateur = authenticate(courriel=donnees['courriel'], password=donnees['motDePasse'])
        if not utilisateur:
            return Response({'ok': False, 'message': 'Courriel ou mot de passe incorrect.'},
                             status=status.HTTP_401_UNAUTHORIZED)

        role_demande = donnees.get('role')
        session = SessionSerializer(utilisateur).data
        if role_demande and session['role'] != role_demande:
            return Response({'ok': False, 'message': f'Ce compte n est pas un compte {role_demande}.'},
                             status=status.HTTP_401_UNAUTHORIZED)

        jeton = str(AccessToken.for_user(utilisateur))
        accueil = 'admin/tableau-de-bord.html' if session['role'] == 'admin' else 'chauffeur/mes-trajets.html'
        return Response({'ok': True, 'session': session, 'jeton': jeton, 'accueil': accueil})


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
