"""
TransitFlow — Routes de l entretien de la flotte (reservees a 'fleet.admin')
Auteur : Jonathan K-N

Plans preventifs
  GET    /api/entretien/plans               -> liste (?vehicule=, ?etat=, ?inactifs=1)
  POST   /api/entretien/plans               -> creation
  GET    /api/entretien/plans/<P-1>         -> detail
  PATCH  /api/entretien/plans/<P-1>         -> modification (intervalles, recalage, actif)
  DELETE /api/entretien/plans/<P-1>         -> desactivation (l historique est conserve)
  GET    /api/entretien/echeances           -> plans 'bientot' / 'en-retard', les plus urgents d abord

Bons de travail
  GET    /api/entretien/bons                -> liste (?statut=, ?vehicule=, ?categorie=, ?debut=, ?fin=, ?recherche=)
  POST   /api/entretien/bons                -> creation (libre, depuis un plan ou un incident technique)
  GET    /api/entretien/bons/<BT-1>         -> detail
  PATCH  /api/entretien/bons/<BT-1>         -> modification d un bon ouvert
  POST   /api/entretien/bons/<BT-1>/demarrer
  POST   /api/entretien/bons/<BT-1>/terminer
  POST   /api/entretien/bons/<BT-1>/annuler

Analyse
  GET    /api/entretien/couts               -> couts des bons termines sur une periode (?debut=, ?fin=)
  GET    /api/entretien/export.csv          -> memes filtres que la liste des bons, au format CSV (Excel)
"""

import csv
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, F, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe
from . import services
from .models import TYPES_ENTRETIEN, BonTravail, PlanEntretien
from .serializers import (AnnulerSerializer, BonCreationSerializer, BonMajSerializer, BonTravailSerializer,
                          PlanCreationSerializer, PlanEntretienSerializer, PlanMajSerializer, TerminerSerializer)

ORDRE_ETATS = {'en-retard': 0, 'bientot': 1, 'a-jour': 2}
LIBELLES_TYPES = dict(TYPES_ENTRETIEN)


def _erreur(message, code):
    return Response({'ok': False, 'message': message}, status=code)


def _date_param(request, nom):
    """Date AAAA-MM-JJ d un parametre de requete ; None si absente ; ValueError si invalide."""
    valeur = request.query_params.get(nom)
    if not valeur:
        return None
    return date.fromisoformat(valeur)


def _plans():
    ouverts = BonTravail.objects.filter(statut__in=BonTravail.STATUTS_OUVERTS).order_by('date_prevue', 'id')
    return PlanEntretien.objects.select_related('vehicule').prefetch_related(
        Prefetch('bons_travail', queryset=ouverts, to_attr='bons_ouverts'))


def _bons():
    return BonTravail.objects.select_related('vehicule', 'plan', 'incident', 'cree_par')


class AdminSeulement(APIView):
    permission_classes = [DansGroupe('fleet.admin')]


# ---- Plans preventifs -----------------------------------------------------

class PlansView(AdminSeulement):
    def get(self, request):
        plans = _plans()
        if request.query_params.get('inactifs') not in ('1', 'true'):
            plans = plans.filter(actif=True)
        vehicule = request.query_params.get('vehicule')
        if vehicule:
            plans = plans.filter(vehicule__plaque__iexact=vehicule.strip())
        donnees = PlanEntretienSerializer(plans, many=True).data
        etat = request.query_params.get('etat')
        if etat and etat != 'tous':
            donnees = [p for p in donnees if p['echeance']['etat'] == etat]
        return Response({'ok': True, 'plans': donnees})

    def post(self, request):
        serializer = PlanCreationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response({'ok': True, 'plan': PlanEntretienSerializer(plan).data}, status=status.HTTP_201_CREATED)


class PlanDetailView(AdminSeulement):
    def _plan(self, code):
        plan = PlanEntretien.depuis_code(code)
        return plan

    def get(self, request, code):
        plan = self._plan(code)
        if not plan:
            return _erreur('Plan d entretien introuvable.', status.HTTP_404_NOT_FOUND)
        return Response({'ok': True, 'plan': PlanEntretienSerializer(plan).data})

    def patch(self, request, code):
        plan = self._plan(code)
        if not plan:
            return _erreur('Plan d entretien introuvable.', status.HTTP_404_NOT_FOUND)
        serializer = PlanMajSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('actif') and not plan.actif and plan.type != 'autre' and \
                PlanEntretien.objects.filter(vehicule=plan.vehicule, type=plan.type, actif=True).exists():
            return _erreur('Un autre plan actif de ce type existe deja pour ce vehicule.', status.HTTP_409_CONFLICT)
        serializer.save()
        return Response({'ok': True, 'plan': PlanEntretienSerializer(plan).data})

    def delete(self, request, code):
        plan = self._plan(code)
        if not plan:
            return _erreur('Plan d entretien introuvable.', status.HTTP_404_NOT_FOUND)
        plan.actif = False
        plan.save(update_fields=['actif'])
        return Response({'ok': True, 'plan': PlanEntretienSerializer(plan).data})


class EcheancesView(AdminSeulement):
    def get(self, request):
        plans = PlanEntretienSerializer(_plans().filter(actif=True, vehicule__statut__in=['actif', 'maintenance']),
                                        many=True).data
        tous = request.query_params.get('tous') in ('1', 'true')
        echeances = [p for p in plans if tous or p['echeance']['etat'] != 'a-jour']

        def urgence(plan):
            e = plan['echeance']
            # Ramene km et jours restants sur une echelle comparable (~ 50 km par jour de service).
            restes = [v for v in (e['joursRestants'], None if e['kmRestants'] is None else e['kmRestants'] / 50)
                      if v is not None]
            return ORDRE_ETATS[e['etat']], min(restes) if restes else 0

        echeances.sort(key=urgence)
        return Response({
            'ok': True,
            'echeances': echeances,
            'resume': {
                'enRetard': sum(1 for p in plans if p['echeance']['etat'] == 'en-retard'),
                'bientot': sum(1 for p in plans if p['echeance']['etat'] == 'bientot'),
                'aJour': sum(1 for p in plans if p['echeance']['etat'] == 'a-jour'),
            },
        })


# ---- Bons de travail ------------------------------------------------------

def _filtrer_bons(request, bons):
    """Filtres communs a la liste et a l export CSV. Leve ValueError si une date est invalide."""
    statut = request.query_params.get('statut')
    if statut == 'ouverts':
        bons = bons.filter(statut__in=BonTravail.STATUTS_OUVERTS)
    elif statut == 'en-retard':
        bons = bons.filter(statut='planifie', date_prevue__lt=timezone.localdate())
    elif statut and statut != 'tous':
        bons = bons.filter(statut=statut)
    vehicule = request.query_params.get('vehicule')
    if vehicule:
        bons = bons.filter(vehicule__plaque__iexact=vehicule.strip())
    categorie = request.query_params.get('categorie')
    if categorie and categorie != 'tous':
        bons = bons.filter(categorie=categorie)
    type_ = request.query_params.get('type')
    if type_ and type_ != 'tous':
        bons = bons.filter(type=type_)
    debut, fin = _date_param(request, 'debut'), _date_param(request, 'fin')
    if debut:
        bons = bons.filter(date_prevue__gte=debut)
    if fin:
        bons = bons.filter(date_prevue__lte=fin)
    recherche = (request.query_params.get('recherche') or '').strip()
    if recherche:
        filtre = Q(titre__icontains=recherche) | Q(description__icontains=recherche) | \
            Q(fournisseur__icontains=recherche) | Q(vehicule__plaque__icontains=recherche)
        code = BonTravail.depuis_code(recherche)
        if code:
            filtre |= Q(pk=code.pk)
        bons = bons.filter(filtre)
    return bons


class BonsView(AdminSeulement):
    def get(self, request):
        try:
            bons = _filtrer_bons(request, _bons())
        except ValueError:
            return _erreur('Date invalide (format attendu AAAA-MM-JJ).', status.HTTP_400_BAD_REQUEST)
        return Response({'ok': True, 'bons': BonTravailSerializer(bons, many=True).data})

    def post(self, request):
        entree = BonCreationSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        with transaction.atomic():
            bon = BonTravail.objects.create(cree_par=request.user, **entree.validated_data)
        return Response({'ok': True, 'bon': BonTravailSerializer(bon).data}, status=status.HTTP_201_CREATED)


class BonDetailView(AdminSeulement):
    def get(self, request, code):
        bon = BonTravail.depuis_code(code)
        if not bon:
            return _erreur('Bon de travail introuvable.', status.HTTP_404_NOT_FOUND)
        return Response({'ok': True, 'bon': BonTravailSerializer(bon).data})

    def patch(self, request, code):
        bon = BonTravail.depuis_code(code)
        if not bon:
            return _erreur('Bon de travail introuvable.', status.HTTP_404_NOT_FOUND)
        if not bon.ouvert:
            return _erreur('Ce bon de travail est clos : il ne peut plus etre modifie.', status.HTTP_409_CONFLICT)
        serializer = BonMajSerializer(bon, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'ok': True, 'bon': BonTravailSerializer(bon).data})


class _TransitionView(AdminSeulement):
    """Base des actions demarrer / terminer / annuler : 404, puis 409 si la regle metier refuse."""

    def appliquer(self, request, bon):
        raise NotImplementedError

    def post(self, request, code):
        bon = BonTravail.depuis_code(code)
        if not bon:
            return _erreur('Bon de travail introuvable.', status.HTTP_404_NOT_FOUND)
        try:
            bon = self.appliquer(request, bon)
        except services.ConflitMetier as conflit:
            return _erreur(str(conflit), status.HTTP_409_CONFLICT)
        bon = _bons().get(pk=bon.pk)
        return Response({'ok': True, 'bon': BonTravailSerializer(bon).data})


class DemarrerBonView(_TransitionView):
    def appliquer(self, request, bon):
        return services.demarrer(bon)


class TerminerBonView(_TransitionView):
    def appliquer(self, request, bon):
        entree = TerminerSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        d = entree.validated_data
        return services.terminer(
            bon, auteur=request.user, kilometrage=d.get('kilometrage'), date_fin=d.get('dateFin'),
            cout_pieces=d.get('coutPieces'), cout_main_oeuvre=d.get('coutMainOeuvre'),
            fournisseur=None if d.get('fournisseur') is None else d['fournisseur'].strip(),
            notes=d.get('notes'),
        )


class AnnulerBonView(_TransitionView):
    def appliquer(self, request, bon):
        entree = AnnulerSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        return services.annuler(bon, entree.validated_data['motif'].strip())


# ---- Analyse --------------------------------------------------------------

def _somme(champ):
    return Coalesce(Sum(champ), Value(Decimal('0')), output_field=DecimalField(max_digits=12, decimal_places=2))


class CoutsView(AdminSeulement):
    """
    Couts des bons TERMINES dont la fin tombe dans la periode (par defaut :
    depuis le 1er janvier de l annee en cours). Le cout au kilometre de
    chaque vehicule rapporte ses couts d entretien aux kilometres releves
    sur la meme periode.
    """

    def get(self, request):
        aujourdhui = timezone.localdate()
        try:
            debut = _date_param(request, 'debut') or aujourdhui.replace(month=1, day=1)
            fin = _date_param(request, 'fin') or aujourdhui
        except ValueError:
            return _erreur('Date invalide (format attendu AAAA-MM-JJ).', status.HTTP_400_BAD_REQUEST)
        if fin < debut:
            return _erreur('La fin de la periode precede son debut.', status.HTTP_400_BAD_REQUEST)

        bons = BonTravail.objects.filter(statut='termine', fin__date__gte=debut, fin__date__lte=fin)
        total = F('cout_pieces') + F('cout_main_oeuvre')

        global_ = bons.aggregate(nombre=Count('id'), pieces=_somme('cout_pieces'),
                                 mainOeuvre=_somme('cout_main_oeuvre'), total=_somme(total))
        par_categorie = {c: {'nombre': 0, 'total': 0.0} for c, _ in BonTravail.CATEGORIES}
        for ligne in bons.values('categorie').annotate(nombre=Count('id'), total=_somme(total)):
            par_categorie[ligne['categorie']] = {'nombre': ligne['nombre'], 'total': float(ligne['total'])}

        par_type = [
            {'type': l['type'], 'libelle': LIBELLES_TYPES.get(l['type'], l['type']), 'nombre': l['nombre'],
             'total': float(l['total'])}
            for l in bons.values('type').annotate(nombre=Count('id'), total=_somme(total)).order_by('-total')
        ]

        par_vehicule = []
        for l in bons.values('vehicule__plaque', 'vehicule__modele', 'vehicule_id').annotate(
                nombre=Count('id'), pieces=_somme('cout_pieces'), mainOeuvre=_somme('cout_main_oeuvre'),
                total=_somme(total)).order_by('-total'):
            premier_cout = bons.filter(vehicule_id=l['vehicule_id']).order_by('fin') \
                .values_list('fin', flat=True).first()
            parcourus = _km_parcourus(l['vehicule_id'], debut, fin, couvrir_depuis=premier_cout)
            par_vehicule.append({
                'vehicule': l['vehicule__plaque'], 'modele': l['vehicule__modele'], 'nombre': l['nombre'],
                'pieces': float(l['pieces']), 'mainOeuvre': float(l['mainOeuvre']), 'total': float(l['total']),
                'kmParcourus': parcourus,
                'coutParKm': round(float(l['total']) / parcourus, 3) if parcourus else None,
                # Faux quand les releves de compteur ne couvrent pas toute la periode
                # ou les couts ont ete engages : le cout au km n est pas calcule.
                'historiqueKmSuffisant': parcourus is not None,
            })

        return Response({
            'ok': True,
            'periode': {'debut': debut.isoformat(), 'fin': fin.isoformat()},
            'total': {'nombre': global_['nombre'], 'pieces': float(global_['pieces']),
                      'mainOeuvre': float(global_['mainOeuvre']), 'total': float(global_['total'])},
            'parCategorie': par_categorie,
            'parType': par_type,
            'parVehicule': par_vehicule,
        })


def _km_parcourus(vehicule_id, debut, fin, couvrir_depuis=None):
    """
    Kilometres parcourus sur la periode : dernier releve de la periode moins
    le dernier releve connu AVANT la periode (ou, a defaut, le premier releve
    de la periode). Le compteur ne reculant jamais, la difference est >= 0.

    couvrir_depuis (datetime, optionnel) : instant a partir duquel la distance
    doit etre connue, en pratique la cloture du premier bon de la periode. Sans
    releve anterieur a la periode, si le premier releve de la periode est
    posterieur a cet instant, les kilometres mesures ne couvrent qu une partie
    des couts : on renvoie None plutot qu une distance trop courte (qui
    donnerait un cout au km aberrant, ex. 577 $ / 176 km).
    """
    from apps.fleet.models import ReleveKilometrage

    releves = ReleveKilometrage.objects.filter(vehicule_id=vehicule_id)
    dans_periode = releves.filter(releve_le__date__gte=debut, releve_le__date__lte=fin)
    arrivee = dans_periode.order_by('-kilometrage').values_list('kilometrage', flat=True).first()
    if arrivee is None:
        return None if couvrir_depuis is not None else 0
    depart = releves.filter(releve_le__date__lt=debut).order_by('-kilometrage') \
        .values_list('kilometrage', flat=True).first()
    if depart is None:
        premier = dans_periode.order_by('releve_le', 'kilometrage').values_list('kilometrage', 'releve_le').first()
        if couvrir_depuis is not None and premier[1] > couvrir_depuis:
            return None
        depart = premier[0]
    return max(0, arrivee - depart)


class ExportBonsView(AdminSeulement):
    ENTETES = ['Bon', 'Vehicule', 'Modele', 'Categorie', 'Type', 'Titre', 'Priorite', 'Statut', 'Date prevue',
               'Debut', 'Fin', 'Kilometrage', 'Fournisseur', 'Pieces', 'Main-d oeuvre', 'Total', 'Plan',
               'Incident']

    def get(self, request):
        try:
            bons = _filtrer_bons(request, _bons())
        except ValueError:
            return _erreur('Date invalide (format attendu AAAA-MM-JJ).', status.HTTP_400_BAD_REQUEST)

        def horodatage(valeur):
            return timezone.localtime(valeur).strftime('%Y-%m-%d %H:%M') if valeur else ''

        reponse = HttpResponse(content_type='text/csv; charset=utf-8')
        reponse['Content-Disposition'] = f'attachment; filename="bons-de-travail-{timezone.localdate()}.csv"'
        reponse.write('﻿')  # BOM : Excel detecte l UTF-8 et affiche correctement les accents
        ecrivain = csv.writer(reponse, delimiter=';')
        ecrivain.writerow(self.ENTETES)
        for b in bons:
            ecrivain.writerow([
                b.code, b.vehicule.plaque, b.vehicule.modele, b.get_categorie_display(), b.get_type_display(),
                _cellule(b.titre), b.get_priorite_display(), b.get_statut_display(), b.date_prevue.isoformat(),
                horodatage(b.debut), horodatage(b.fin), b.kilometrage if b.kilometrage is not None else '',
                _cellule(b.fournisseur), _decimal(b.cout_pieces), _decimal(b.cout_main_oeuvre),
                _decimal(b.cout_total), b.plan.code if b.plan_id else '', b.incident.code if b.incident_id else '',
            ])
        return reponse


def _decimal(valeur):
    # Virgule decimale : format attendu par Excel en francais (separateur de colonnes ';').
    return f'{valeur:.2f}'.replace('.', ',')


def _cellule(texte):
    """Neutralise l injection de formules dans Excel (=, +, -, @ en debut de cellule)."""
    texte = texte or ''
    return "'" + texte if texte[:1] in ('=', '+', '-', '@', '\t', '\r') else texte
