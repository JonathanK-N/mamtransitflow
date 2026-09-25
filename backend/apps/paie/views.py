"""
TransitFlow — Routes de la paie (module 'paie', desactivable dans les parametres)
Auteur : Jonathan K-N

  Administrateur
  GET/PATCH  /api/paie/parametres                  frequence, heures sup, vacances + retenues
  POST       /api/paie/retenues                     ajouter une retenue
  PATCH/DEL  /api/paie/retenues/<id>
  GET        /api/paie/profils                       remuneration de chaque chauffeur
  PUT        /api/paie/profils/<chauffeur>
  GET/POST   /api/paie/periodes
  GET/DEL    /api/paie/periodes/<PP-n>              (suppression : brouillon seulement)
  POST       /api/paie/periodes/<PP-n>/<action>     calculer | valider | payer | rouvrir
  GET        /api/paie/periodes/<PP-n>/export.csv   journal de paie
  POST       /api/paie/bulletins/<BP-n>/lignes      ligne manuelle (prime, remboursement, avance)
  DELETE     /api/paie/lignes/<id>

  Administrateur ou chauffeur (portail 'paie' ouvert, paie validee ou payee)
  GET        /api/paie/mes-bulletins
  GET        /api/paie/bulletins/<BP-n>
"""

import csv

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte, est_admin
from apps.drivers.models import Chauffeur
from apps.societe.permissions import ModuleActif, PortailAutorise
from . import services
from .models import BulletinPaie, LigneBulletin, ParametresPaie, PeriodePaie, ProfilPaie, Retenue
from .serializers import (LigneManuelleSerializer, ParametresSerializer, PeriodeSerializer, ProfilSerializer,
                          RetenueSerializer, bulletin_json, ligne_json, parametres_json, periode_json,
                          profil_json, retenue_json)


def _erreur(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'ok': False, 'message': message}, status=code)


class _Admin(APIView):
    permission_classes = [ModuleActif('paie'), DansGroupe('fleet.admin')]


class ParametresView(_Admin):
    def get(self, request):
        return Response({'ok': True, 'parametres': parametres_json(ParametresPaie.courants()),
                         'retenues': [retenue_json(r) for r in Retenue.objects.all()]})

    def patch(self, request):
        entree = ParametresSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        p = ParametresPaie.courants()
        for cle, champ in [('frequence', 'frequence'), ('seuilHeuresSup', 'seuil_heures_sup'),
                           ('majorationHeuresSup', 'majoration_heures_sup'), ('tauxVacances', 'taux_vacances')]:
            if cle in entree.validated_data:
                setattr(p, champ, entree.validated_data[cle])
        p.save()
        return Response({'ok': True, 'parametres': parametres_json(p)})


class RetenuesView(_Admin):
    def post(self, request):
        entree = RetenueSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        d = entree.validated_data
        if not d.get('code') or not d.get('libelle'):
            return _erreur('Code et libelle obligatoires.')
        if Retenue.objects.filter(code=d['code']).exists():
            return _erreur('Ce code existe deja.')
        r = Retenue.objects.create(**{RetenueSerializer.CHAMPS[k]: v for k, v in d.items()})
        return Response({'ok': True, 'retenue': retenue_json(r)}, status=status.HTTP_201_CREATED)


class RetenueDetailView(_Admin):
    def patch(self, request, pk):
        r = Retenue.objects.filter(pk=pk).first()
        if not r:
            return _erreur('Retenue introuvable.', status.HTTP_404_NOT_FOUND)
        entree = RetenueSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        for cle, valeur in entree.validated_data.items():
            setattr(r, RetenueSerializer.CHAMPS[cle], valeur)
        if r.plafond_annuel is not None and r.plafond_annuel <= r.plancher_annuel:
            return _erreur('Le plafond doit depasser le plancher.')
        try:
            r.save()
        except IntegrityError:
            return _erreur('Ce code existe deja.')
        return Response({'ok': True, 'retenue': retenue_json(r)})

    def delete(self, request, pk):
        Retenue.objects.filter(pk=pk).delete()
        return Response({'ok': True})


class ProfilsView(_Admin):
    def get(self, request):
        profils = {p.chauffeur_id: p for p in ProfilPaie.objects.all()}
        return Response({'ok': True, 'profils': [profil_json(c, profils.get(c.id))
                                                 for c in Chauffeur.objects.all()]})


class ProfilDetailView(_Admin):
    def put(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur:
            return _erreur('Chauffeur introuvable.', status.HTTP_404_NOT_FOUND)
        entree = ProfilSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        d = entree.validated_data
        profil, _ = ProfilPaie.objects.update_or_create(chauffeur=chauffeur, defaults={
            'mode': d['mode'], 'taux_horaire': d['tauxHoraire'], 'taux_trajet': d['tauxTrajet'],
            'salaire_periode': d['salairePeriode'], 'actif': d['actif']})
        return Response({'ok': True, 'profil': profil_json(chauffeur, profil)})


class PeriodesView(_Admin):
    def get(self, request):
        periodes = PeriodePaie.objects.prefetch_related('bulletins')
        return Response({'ok': True, 'periodes': [periode_json(p) for p in periodes]})

    def post(self, request):
        entree = PeriodeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        d = entree.validated_data
        periode = PeriodePaie.objects.create(debut=d['debut'], fin=d['fin'], date_paiement=d['datePaiement'])
        services.calculer_periode(periode)
        periode.refresh_from_db()
        return Response({'ok': True, 'periode': periode_json(periode)}, status=status.HTTP_201_CREATED)


def _periode_ou_404(code):
    return PeriodePaie.depuis_code(code)


class PeriodeDetailView(_Admin):
    def get(self, request, code):
        periode = _periode_ou_404(code)
        if not periode:
            return _erreur('Paie introuvable.', status.HTTP_404_NOT_FOUND)
        bulletins = periode.bulletins.select_related('chauffeur', 'periode')
        return Response({'ok': True, 'periode': periode_json(periode),
                         'bulletins': [bulletin_json(b) for b in bulletins]})

    def delete(self, request, code):
        periode = _periode_ou_404(code)
        if not periode:
            return _erreur('Paie introuvable.', status.HTTP_404_NOT_FOUND)
        if periode.statut != 'brouillon':
            return _erreur('Seule une paie en brouillon peut etre supprimee.', status.HTTP_409_CONFLICT)
        periode.delete()
        return Response({'ok': True})


class PeriodeActionView(_Admin):
    def post(self, request, code, action):
        periode = _periode_ou_404(code)
        if not periode:
            return _erreur('Paie introuvable.', status.HTTP_404_NOT_FOUND)
        try:
            if action == 'calculer':
                services.calculer_periode(periode)
            elif action in services.TRANSITIONS:
                services.changer_statut(periode, action)
            else:
                return _erreur('Action inconnue.', status.HTTP_404_NOT_FOUND)
        except services.ErreurPaie as e:
            return _erreur(str(e), status.HTTP_409_CONFLICT)
        periode.refresh_from_db()
        bulletins = periode.bulletins.select_related('chauffeur', 'periode')
        return Response({'ok': True, 'periode': periode_json(periode),
                         'bulletins': [bulletin_json(b) for b in bulletins]})


def _cellule(valeur):
    texte = str(valeur)
    return "'" + texte if texte[:1] in ('=', '+', '-', '@') and not texte.replace('.', '').lstrip('-').isdigit() \
        else texte


def _montant(valeur):
    return f'{valeur:.2f}'.replace('.', ',')


class ExportPeriodeView(_Admin):
    def get(self, request, code):
        periode = _periode_ou_404(code)
        if not periode:
            return _erreur('Paie introuvable.', status.HTTP_404_NOT_FOUND)
        reponse = HttpResponse(content_type='text/csv; charset=utf-8')
        reponse['Content-Disposition'] = f'attachment; filename="paie-{periode.code}-{periode.fin}.csv"'
        reponse.write('\ufeff')
        codes = list(Retenue.objects.values_list('code', flat=True))
        ecrivain = csv.writer(reponse, delimiter=';')
        ecrivain.writerow(['Bulletin', 'Chauffeur', 'Mode', 'Trajets', 'Heures regulieres', 'Heures sup', 'Brut',
                           *[f'Retenue {c}' for c in codes], 'Autres retenues', 'Net', 'Cotisations employeur',
                           'Cout employeur'])
        for b in periode.bulletins.select_related('chauffeur').prefetch_related('lignes'):
            par_code = {l.code: l.montant for l in b.lignes.all() if l.genre == 'retenue' and not l.manuelle}
            autres = sum((l.montant for l in b.lignes.all() if l.genre == 'retenue' and l.manuelle), 0)
            ecrivain.writerow([b.code, _cellule(b.chauffeur.nom_complet), b.mode, b.nombre_trajets,
                               _montant(b.heures_regulieres), _montant(b.heures_sup), _montant(b.brut),
                               *[_montant(par_code.get(c, 0)) for c in codes], _montant(autres),
                               _montant(b.net), _montant(b.cotisations_employeur), _montant(b.cout_employeur)])
        return reponse


class LignesBulletinView(_Admin):
    def post(self, request, code):
        bulletin = BulletinPaie.depuis_code(code)
        if not bulletin:
            return _erreur('Bulletin introuvable.', status.HTTP_404_NOT_FOUND)
        if bulletin.periode.statut != 'brouillon':
            return _erreur('La paie est validee : rouvrez-la pour la modifier.', status.HTTP_409_CONFLICT)
        entree = LigneManuelleSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        d = entree.validated_data
        with transaction.atomic():
            LigneBulletin.objects.create(
                bulletin=bulletin, genre=d['genre'], code='MAN', libelle=d['libelle'], montant=d['montant'],
                imposable=d['imposable'] if d['genre'] == 'gain' else True, manuelle=True, ordre=100)
            services.recalculer_bulletin(bulletin)
        bulletin.refresh_from_db()
        return Response({'ok': True, 'bulletin': bulletin_json(bulletin, lignes=True)}, status=status.HTTP_201_CREATED)


class LigneDetailView(_Admin):
    def delete(self, request, pk):
        ligne = LigneBulletin.objects.select_related('bulletin__periode').filter(pk=pk, manuelle=True).first()
        if not ligne:
            return _erreur('Ligne introuvable (seules les lignes manuelles se suppriment).', status.HTTP_404_NOT_FOUND)
        if ligne.bulletin.periode.statut != 'brouillon':
            return _erreur('La paie est validee : rouvrez-la pour la modifier.', status.HTTP_409_CONFLICT)
        bulletin = ligne.bulletin
        with transaction.atomic():
            ligne.delete()
            services.recalculer_bulletin(bulletin)
        bulletin.refresh_from_db()
        return Response({'ok': True, 'bulletin': bulletin_json(bulletin, lignes=True)})


class MesBulletinsView(APIView):
    permission_classes = [EstConnecte, ModuleActif('paie'), PortailAutorise('paie')]

    def get(self, request):
        if not request.user.chauffeur_id:
            return Response({'ok': True, 'bulletins': []})
        bulletins = BulletinPaie.objects.filter(chauffeur_id=request.user.chauffeur_id) \
            .exclude(periode__statut='brouillon').select_related('chauffeur', 'periode') \
            .order_by('-periode__date_paiement')
        return Response({'ok': True, 'bulletins': [bulletin_json(b) for b in bulletins]})


class BulletinDetailView(APIView):
    permission_classes = [EstConnecte, ModuleActif('paie'), PortailAutorise('paie')]

    def get(self, request, code):
        bulletin = BulletinPaie.depuis_code(code)
        visible = bulletin and (est_admin(request.user) or (
            bulletin.chauffeur_id == request.user.chauffeur_id and bulletin.periode.statut != 'brouillon'))
        if not visible:
            return _erreur('Bulletin introuvable.', status.HTTP_404_NOT_FOUND)
        from apps.societe.models import Entreprise
        from apps.societe.serializers import entreprise_en_json
        e = entreprise_en_json(Entreprise.courante())
        return Response({'ok': True, 'bulletin': bulletin_json(bulletin, lignes=True),
                         'employeur': {k: e[k] for k in ('nom', 'adresse', 'ville', 'province', 'codePostal', 'neq')},
                         'employe': {'nom': bulletin.chauffeur.nom_complet, 'adresse': bulletin.chauffeur.adresse}})
