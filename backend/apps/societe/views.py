"""
TransitFlow — Routes de l entreprise
Auteur : Jonathan K-N

  GET   /api/entreprise/publique -> {nom} : page de connexion et d invitation (sans compte)
  GET   /api/entreprise          -> fiche, modules et portail (tout compte connecte : le
                                    front construit ses menus avec)
  PATCH /api/entreprise          -> modification (administrateur)
"""

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import EstConnecte, est_admin
from .models import Entreprise
from .serializers import EntrepriseMajSerializer, entreprise_en_json


class EntreprisePubliqueView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'ok': True, 'nom': Entreprise.courante().nom})


class EntrepriseView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request):
        donnees = entreprise_en_json(Entreprise.courante())
        if est_admin(request.user):
            donnees['courrielConfigure'] = settings.TF_COURRIEL_CONFIGURE
        return Response({'ok': True, 'entreprise': donnees})

    def patch(self, request):
        if not est_admin(request.user):
            return Response({'ok': False, 'message': 'Acces refuse.'}, status=403)
        entree = EntrepriseMajSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        entreprise = entree.appliquer(Entreprise.courante())
        donnees = entreprise_en_json(entreprise)
        donnees['courrielConfigure'] = settings.TF_COURRIEL_CONFIGURE
        return Response({'ok': True, 'entreprise': donnees})
