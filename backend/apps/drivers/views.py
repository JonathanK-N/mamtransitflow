"""
TransitFlow — Routes chauffeurs
Auteur : Jonathan K-N

  GET   /api/chauffeurs        -> liste (avec filtres recherche/statut)
  GET   /api/chauffeurs/<code> -> fiche d un chauffeur (code style 'c1')
  POST  /api/chauffeurs        -> creation (reserve a 'fleet.admin')
  PATCH /api/chauffeurs/<code> -> mise a jour partielle (admin, ou le chauffeur sur sa propre fiche)
"""

from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte
from .models import Chauffeur
from .serializers import ChauffeurMajSerializer, ChauffeurSerializer


class ChauffeursView(APIView):
    def get_permissions(self):
        # Lire la liste : n importe quel utilisateur connecte. Creer : reserve a l administrateur.
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.admin')
        return [classe()]

    def get(self, request):
        chauffeurs = Chauffeur.objects.all()
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
        serializer = ChauffeurSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chauffeur = serializer.save()
        return Response({'ok': True, 'chauffeur': ChauffeurSerializer(chauffeur).data},
                         status=status.HTTP_201_CREATED)


class ChauffeurDetailView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur:
            return Response({'ok': False, 'message': 'Chauffeur introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'ok': True, 'chauffeur': ChauffeurSerializer(chauffeur).data})

    def patch(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur:
            return Response({'ok': False, 'message': 'Chauffeur introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        # Un administrateur peut modifier n importe quelle fiche ; un chauffeur
        # ne peut modifier que la sienne (ex. mettre a jour son propre statut
        # depuis chauffeur/trajet-nouveau.html).
        est_admin = request.user.a_groupe('fleet.admin')
        est_lui_meme = request.user.chauffeur_id == chauffeur.id
        if not (est_admin or est_lui_meme):
            raise PermissionDenied('Acces refuse.')

        serializer = ChauffeurMajSerializer(chauffeur, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'ok': True, 'chauffeur': ChauffeurSerializer(chauffeur).data})
