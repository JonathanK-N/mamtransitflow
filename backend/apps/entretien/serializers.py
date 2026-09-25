"""TransitFlow — Schemas de l app entretien (plans preventifs, bons de travail)
   Auteur : Jonathan K-N

   Les montants sont renvoyes en nombres (pas en chaines, contrairement au
   defaut de DRF pour les DecimalField) : le front-end les additionne et
   les formate directement."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.fleet.models import Vehicule
from .models import TYPES_ENTRETIEN, BonTravail, PlanEntretien

CODES_TYPES = [code for code, _ in TYPES_ENTRETIEN]
MONTANT_MAXIMAL = Decimal('99999999.99')


def _montant(**kwargs):
    return serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'),
                                    max_value=MONTANT_MAXIMAL, coerce_to_string=False, **kwargs)


def _vehicule_par_plaque(plaque):
    vehicule = Vehicule.objects.filter(plaque__iexact=(plaque or '').strip()).first()
    if not vehicule:
        raise serializers.ValidationError('Vehicule introuvable pour cette plaque.')
    return vehicule


# ---- Plans preventifs -----------------------------------------------------

class PlanEntretienSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code', read_only=True)
    vehicule = serializers.CharField(source='vehicule.plaque', read_only=True)
    intervalleKm = serializers.IntegerField(source='intervalle_km', allow_null=True, required=False,
                                            min_value=100, max_value=1_000_000)
    intervalleJours = serializers.IntegerField(source='intervalle_jours', allow_null=True, required=False,
                                               min_value=1, max_value=3650)
    dernierKm = serializers.IntegerField(source='dernier_km', required=False, min_value=0)
    derniereDate = serializers.DateField(source='derniere_date', required=False)
    prochainKm = serializers.IntegerField(source='prochain_km', read_only=True)
    prochaineDate = serializers.DateField(source='prochaine_date', read_only=True)
    echeance = serializers.SerializerMethodField()
    bonOuvert = serializers.SerializerMethodField()

    class Meta:
        model = PlanEntretien
        fields = ['id', 'vehicule', 'type', 'libelle', 'intervalleKm', 'intervalleJours', 'dernierKm',
                  'derniereDate', 'prochainKm', 'prochaineDate', 'actif', 'echeance', 'bonOuvert']
        read_only_fields = ['actif']

    def get_echeance(self, plan):
        return plan.echeance(timezone.localdate())

    def get_bonOuvert(self, plan):
        # `bons_ouverts` est precharge par les vues (Prefetch) pour eviter une requete par plan.
        bons = getattr(plan, 'bons_ouverts', None)
        if bons is None:
            bons = list(plan.bons_travail.filter(statut__in=BonTravail.STATUTS_OUVERTS).order_by('date_prevue'))
        return bons[0].code if bons else None

    def validate_libelle(self, valeur):
        valeur = valeur.strip()
        if not valeur:
            raise serializers.ValidationError('Le libelle est obligatoire.')
        return valeur

    def validate_derniereDate(self, valeur):
        if valeur and valeur > timezone.localdate():
            raise serializers.ValidationError('La date du dernier entretien ne peut pas etre dans le futur.')
        return valeur

    def validate(self, donnees):
        instance = self.instance
        intervalle_km = donnees.get('intervalle_km', instance.intervalle_km if instance else None)
        intervalle_jours = donnees.get('intervalle_jours', instance.intervalle_jours if instance else None)
        if not intervalle_km and not intervalle_jours:
            raise serializers.ValidationError(
                'Indiquez au moins un intervalle : en kilometres, en jours, ou les deux.')
        return donnees


class PlanCreationSerializer(PlanEntretienSerializer):
    vehicule = serializers.CharField(write_only=True)

    class Meta(PlanEntretienSerializer.Meta):
        pass

    def validate_vehicule(self, valeur):
        return _vehicule_par_plaque(valeur)

    def validate(self, donnees):
        donnees = super().validate(donnees)
        vehicule = donnees['vehicule']
        if donnees['type'] != 'autre' and PlanEntretien.objects.filter(
                vehicule=vehicule, type=donnees['type'], actif=True).exists():
            raise serializers.ValidationError(
                {'type': 'Un plan actif de ce type existe deja pour ce vehicule : modifiez-le plutot.'})
        # Sans historique, le plan part du compteur et de la date d aujourd hui.
        donnees.setdefault('dernier_km', vehicule.kilometrage)
        donnees.setdefault('derniere_date', timezone.localdate())
        if donnees['dernier_km'] > vehicule.kilometrage:
            raise serializers.ValidationError(
                {'dernierKm': f'Superieur au compteur actuel du vehicule ({vehicule.kilometrage} km).'})
        return donnees


class PlanMajSerializer(PlanEntretienSerializer):
    actif = serializers.BooleanField(required=False)

    class Meta(PlanEntretienSerializer.Meta):
        read_only_fields = ['type']

    def validate_dernierKm(self, valeur):
        if self.instance and valeur > self.instance.vehicule.kilometrage:
            raise serializers.ValidationError(
                f'Superieur au compteur actuel du vehicule ({self.instance.vehicule.kilometrage} km).')
        return valeur


# ---- Bons de travail ------------------------------------------------------

class BonTravailSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code', read_only=True)
    vehicule = serializers.CharField(source='vehicule.plaque', read_only=True)
    modele = serializers.CharField(source='vehicule.modele', read_only=True)
    planId = serializers.SerializerMethodField()
    incidentId = serializers.SerializerMethodField()
    datePrevue = serializers.DateField(source='date_prevue')
    coutPieces = _montant(source='cout_pieces', required=False)
    coutMainOeuvre = _montant(source='cout_main_oeuvre', required=False)
    coutTotal = serializers.DecimalField(source='cout_total', max_digits=11, decimal_places=2, read_only=True,
                                         coerce_to_string=False)
    notesCloture = serializers.CharField(source='notes_cloture', read_only=True)
    creePar = serializers.SerializerMethodField()
    creeLe = serializers.DateTimeField(source='cree_le', read_only=True)
    enRetard = serializers.SerializerMethodField()

    class Meta:
        model = BonTravail
        fields = ['id', 'vehicule', 'modele', 'planId', 'incidentId', 'categorie', 'type', 'titre', 'description',
                  'priorite', 'statut', 'datePrevue', 'debut', 'fin', 'kilometrage', 'fournisseur', 'coutPieces',
                  'coutMainOeuvre', 'coutTotal', 'notesCloture', 'creePar', 'creeLe', 'enRetard']
        read_only_fields = ['categorie', 'statut', 'debut', 'fin', 'kilometrage']

    def get_planId(self, bon):
        return bon.plan.code if bon.plan_id else None

    def get_incidentId(self, bon):
        return bon.incident.code if bon.incident_id else None

    def get_creePar(self, bon):
        if not bon.cree_par:
            return None
        return bon.cree_par.nom or bon.cree_par.courriel

    def get_enRetard(self, bon):
        return bon.en_retard(timezone.localdate())

    def validate_titre(self, valeur):
        valeur = valeur.strip()
        if not valeur:
            raise serializers.ValidationError('Le titre est obligatoire.')
        return valeur


class BonCreationSerializer(serializers.Serializer):
    """
    Trois facons de creer un bon de travail :
      - a partir d un plan preventif (planId)   -> vehicule et type repris du plan ;
      - a partir d un incident technique (incidentId) -> vehicule du trajet de l incident ;
      - librement (vehicule + type + titre).
    """
    vehicule = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    planId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    incidentId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    type = serializers.ChoiceField(choices=CODES_TYPES, required=False, allow_null=True, allow_blank=True)
    titre = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    priorite = serializers.ChoiceField(choices=[p for p, _ in BonTravail.PRIORITES], default='normale')
    datePrevue = serializers.DateField(required=False)
    fournisseur = serializers.CharField(required=False, allow_blank=True, max_length=150, default='')
    coutPieces = _montant(required=False, default=Decimal('0'))
    coutMainOeuvre = _montant(required=False, default=Decimal('0'))

    def validate(self, donnees):
        from apps.maintenance.models import Incident

        plan = incident = None
        if donnees.get('planId'):
            plan = PlanEntretien.depuis_code(donnees['planId'])
            if not plan:
                raise serializers.ValidationError({'planId': 'Plan d entretien introuvable.'})
            if not plan.actif:
                raise serializers.ValidationError({'planId': 'Ce plan d entretien est desactive.'})
        if donnees.get('incidentId'):
            incident = Incident.depuis_code(donnees['incidentId'])
            if not incident:
                raise serializers.ValidationError({'incidentId': 'Incident introuvable.'})
            if incident.type != 'technique':
                raise serializers.ValidationError(
                    {'incidentId': 'Seul un incident technique peut donner lieu a un bon de travail.'})
            if BonTravail.objects.filter(incident=incident).exists():
                raise serializers.ValidationError(
                    {'incidentId': 'Un bon de travail existe deja pour cet incident.'})
        if plan and incident:
            raise serializers.ValidationError('Un bon de travail vient soit d un plan, soit d un incident, pas des deux.')

        # Vehicule : celui du plan, sinon celui envoye, sinon celui du trajet de l incident.
        if plan:
            vehicule = plan.vehicule
            if donnees.get('vehicule') and donnees['vehicule'].strip().upper() != vehicule.plaque.upper():
                raise serializers.ValidationError({'vehicule': 'Le vehicule ne correspond pas a celui du plan.'})
        elif donnees.get('vehicule'):
            try:
                vehicule = _vehicule_par_plaque(donnees['vehicule'])
            except serializers.ValidationError as erreur:
                raise serializers.ValidationError({'vehicule': erreur.detail})
        elif incident and incident.trajet_id:
            vehicule = Vehicule.objects.filter(plaque=incident.trajet.plaque).first()
            if not vehicule:
                raise serializers.ValidationError({'vehicule': 'Le vehicule du trajet n existe plus : choisissez-en un.'})
        else:
            raise serializers.ValidationError({'vehicule': 'Choisissez le vehicule concerne.'})

        type_ = plan.type if plan else donnees.get('type') or ('reparation' if incident else None)
        if not type_:
            raise serializers.ValidationError({'type': 'Choisissez le type d intervention.'})
        titre = (donnees.get('titre') or '').strip() or \
            (plan.libelle if plan else (incident.titre if incident else ''))
        if not titre:
            raise serializers.ValidationError({'titre': 'Le titre est obligatoire.'})
        description = donnees.get('description') or (incident.description if incident else '')

        priorite = donnees['priorite']
        if incident and 'priorite' not in self.initial_data:
            priorite = 'haute'

        return {
            'vehicule': vehicule, 'plan': plan, 'incident': incident,
            'categorie': 'preventif' if plan else 'correctif', 'type': type_, 'titre': titre[:150],
            'description': description, 'priorite': priorite,
            'date_prevue': donnees.get('datePrevue') or timezone.localdate(),
            'fournisseur': donnees.get('fournisseur', '').strip(),
            'cout_pieces': donnees['coutPieces'], 'cout_main_oeuvre': donnees['coutMainOeuvre'],
        }


class BonMajSerializer(BonTravailSerializer):
    """PATCH d un bon encore ouvert : planification, description, fournisseur, couts estimes."""

    class Meta(BonTravailSerializer.Meta):
        read_only_fields = BonTravailSerializer.Meta.read_only_fields + ['type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.required = False


class TerminerSerializer(serializers.Serializer):
    kilometrage = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=5_000_000)
    dateFin = serializers.DateField(required=False, allow_null=True)
    coutPieces = _montant(required=False, allow_null=True)
    coutMainOeuvre = _montant(required=False, allow_null=True)
    fournisseur = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=150)
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_dateFin(self, valeur):
        if valeur and valeur > timezone.localdate():
            raise serializers.ValidationError('La date de fin ne peut pas etre dans le futur.')
        return valeur


class AnnulerSerializer(serializers.Serializer):
    motif = serializers.CharField(required=False, allow_blank=True, default='')
