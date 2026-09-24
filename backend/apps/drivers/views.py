"""
TransitFlow — Routes chauffeurs
Auteur : Jonathan K-N

  GET   /api/chauffeurs        -> liste (avec filtres recherche/statut)
  GET   /api/chauffeurs/<code> -> fiche d un chauffeur (code style 'c1')
  POST  /api/chauffeurs        -> creation (reserve a 'fleet.admin')
  PATCH /api/chauffeurs/<code> -> mise a jour partielle (admin, ou le chauffeur sur sa propre fiche)

Cloisonnement : un administrateur voit toutes les fiches ; un chauffeur
ne voit que la sienne (la liste ne contient que lui, et la fiche d un
autre chauffeur repond 404 comme si elle n existait pas).
"""

from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte, est_admin, voit_tout
from .models import Chauffeur
from .serializers import ChauffeurCreationSerializer, ChauffeurMajSerializer, ChauffeurSerializer

# Champs qu un chauffeur a le droit de modifier sur sa propre fiche. Le
# statut, le permis, le vehicule habituel... restent reserves a
# l administrateur (le statut 'en-trajet'/'disponible' est gere par le
# serveur au demarrage et a la fin d un trajet).
CHAMPS_MODIFIABLES_PAR_LE_CHAUFFEUR = {'telephone', 'adresse'}


def _introuvable():
    return Response({'ok': False, 'message': 'Chauffeur introuvable.'}, status=status.HTTP_404_NOT_FOUND)


class ChauffeursView(APIView):
    def get_permissions(self):
        # Lire la liste : n importe quel utilisateur connecte. Creer : reserve a l administrateur.
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.admin')
        return [classe()]

    def get(self, request):
        chauffeurs = Chauffeur.objects.select_related('compte')
        if not est_admin(request.user):
            chauffeurs = chauffeurs.filter(pk=request.user.chauffeur_id)
        statut = request.query_params.get('statut')
        if statut and statut != 'tous':
            chauffeurs = chauffeurs.filter(statut=statut)
        recherche = request.query_params.get('recherche')
        if recherche:
            chauffeurs = chauffeurs.filter(
                Q(prenom__icontains=recherche) | Q(nom__icontains=recherche) |
                Q(telephone__icontains=recherche) | Q(courriel__icontains=recherche)
            )
        return Response({'ok': True, 'chauffeurs': ChauffeurSerializer(chauffeurs, many=True).data})

    def post(self, request):
        serializer = ChauffeurCreationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chauffeur = serializer.save()
        reponse = {'ok': True, 'chauffeur': ChauffeurSerializer(chauffeur).data}
        # Mot de passe genere par le serveur : renvoye UNE seule fois, pour
        # que l administrateur le transmette au chauffeur.
        mot_de_passe_genere = getattr(chauffeur, 'mot_de_passe_genere', None)
        if mot_de_passe_genere:
            reponse['motDePasseInitial'] = mot_de_passe_genere
        return Response(reponse, status=status.HTTP_201_CREATED)


class ChauffeurDetailView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur or not voit_tout(request.user, chauffeur):
            return _introuvable()
        return Response({'ok': True, 'chauffeur': ChauffeurSerializer(chauffeur).data})

    def patch(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur or not voit_tout(request.user, chauffeur):
            return _introuvable()
        if not est_admin(request.user):
            interdits = set(request.data.keys()) - CHAMPS_MODIFIABLES_PAR_LE_CHAUFFEUR
            if interdits:
                raise PermissionDenied('Champs reserves a l administrateur : ' + ', '.join(sorted(interdits)) + '.')

        serializer = ChauffeurMajSerializer(chauffeur, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'ok': True, 'chauffeur': ChauffeurSerializer(chauffeur).data})
