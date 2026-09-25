"""TransitFlow — Schemas de l app paie (camelCase pour le front-end)
   Auteur : Jonathan K-N"""

from decimal import Decimal

from rest_framework import serializers

from .models import BulletinPaie, LigneBulletin, ParametresPaie, PeriodePaie, ProfilPaie, Retenue


def _f(d):
    return None if d is None else float(d)


def parametres_json(p: ParametresPaie) -> dict:
    return {'frequence': p.frequence, 'periodesParAn': p.periodes_par_an, 'seuilHeuresSup': _f(p.seuil_heures_sup),
            'majorationHeuresSup': _f(p.majoration_heures_sup), 'tauxVacances': _f(p.taux_vacances)}


def retenue_json(r: Retenue) -> dict:
    return {'id': r.id, 'code': r.code, 'libelle': r.libelle, 'tauxSalarie': _f(r.taux_salarie),
            'tauxEmployeur': _f(r.taux_employeur), 'plancherAnnuel': _f(r.plancher_annuel),
            'plafondAnnuel': _f(r.plafond_annuel), 'exemptionAnnuelle': _f(r.exemption_annuelle),
            'note': r.note, 'actif': r.actif, 'ordre': r.ordre}


def profil_json(chauffeur, profil: ProfilPaie | None) -> dict:
    return {'chauffeurId': chauffeur.code, 'nom': chauffeur.nom_complet, 'statut': chauffeur.statut,
            'profil': None if not profil else {
                'mode': profil.mode, 'tauxHoraire': _f(profil.taux_horaire), 'tauxTrajet': _f(profil.taux_trajet),
                'salairePeriode': _f(profil.salaire_periode), 'actif': profil.actif}}


def periode_json(p: PeriodePaie, avec_totaux=True) -> dict:
    d = {'id': p.code, 'debut': p.debut.isoformat(), 'fin': p.fin.isoformat(),
         'datePaiement': p.date_paiement.isoformat(), 'statut': p.statut,
         'calculeeLe': p.calculee_le.isoformat() if p.calculee_le else None}
    if avec_totaux:
        bulletins = list(p.bulletins.all())
        d['totaux'] = {k: round(sum(float(getattr(b, champ)) for b in bulletins), 2) for k, champ in
                       [('brut', 'brut'), ('retenues', 'retenues'), ('net', 'net'),
                        ('cotisationsEmployeur', 'cotisations_employeur')]}
        d['totaux']['bulletins'] = len(bulletins)
        d['totaux']['coutEmployeur'] = round(d['totaux']['brut'] + d['totaux']['cotisationsEmployeur'], 2)
    return d


def ligne_json(l: LigneBulletin) -> dict:
    return {'id': l.id, 'genre': l.genre, 'code': l.code, 'libelle': l.libelle, 'quantite': _f(l.quantite),
            'taux': _f(l.taux), 'montant': _f(l.montant), 'imposable': l.imposable, 'manuelle': l.manuelle}


def bulletin_json(b: BulletinPaie, lignes=False) -> dict:
    d = {'id': b.code, 'periode': periode_json(b.periode, avec_totaux=False), 'chauffeurId': b.chauffeur.code,
         'chauffeur': b.chauffeur.nom_complet, 'mode': b.mode, 'nombreTrajets': b.nombre_trajets,
         'heuresRegulieres': _f(b.heures_regulieres), 'heuresSup': _f(b.heures_sup), 'brut': _f(b.brut),
         'brutImposable': _f(b.brut_imposable), 'retenues': _f(b.retenues), 'net': _f(b.net),
         'cotisationsEmployeur': _f(b.cotisations_employeur), 'coutEmployeur': _f(b.cout_employeur)}
    if lignes:
        d['lignes'] = [ligne_json(l) for l in b.lignes.all()]
    return d


DECIMAL = {'max_digits': 10, 'decimal_places': 3, 'min_value': 0}


class ParametresSerializer(serializers.Serializer):
    frequence = serializers.ChoiceField(choices=[c for c, _ in ParametresPaie.FREQUENCES], required=False)
    seuilHeuresSup = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=80,
                                              required=False)
    majorationHeuresSup = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=1, max_value=3,
                                                   required=False)
    tauxVacances = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=20,
                                            required=False)


class RetenueSerializer(serializers.Serializer):
    code = serializers.RegexField(r'^[A-Z0-9_-]{1,20}$', required=False,
                                  error_messages={'invalid': 'Code : majuscules, chiffres, - ou _ (20 max).'})
    libelle = serializers.CharField(max_length=120, required=False)
    tauxSalarie = serializers.DecimalField(max_value=100, required=False, **DECIMAL)
    tauxEmployeur = serializers.DecimalField(max_value=100, required=False, **DECIMAL)
    plancherAnnuel = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    plafondAnnuel = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False,
                                             allow_null=True)
    exemptionAnnuelle = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    actif = serializers.BooleanField(required=False)
    ordre = serializers.IntegerField(min_value=0, max_value=999, required=False)

    CHAMPS = {'code': 'code', 'libelle': 'libelle', 'tauxSalarie': 'taux_salarie', 'tauxEmployeur': 'taux_employeur',
              'plancherAnnuel': 'plancher_annuel', 'plafondAnnuel': 'plafond_annuel',
              'exemptionAnnuelle': 'exemption_annuelle', 'note': 'note', 'actif': 'actif', 'ordre': 'ordre'}

    def validate(self, d):
        plancher, plafond = d.get('plancherAnnuel'), d.get('plafondAnnuel')
        if plancher is not None and plafond is not None and plafond <= plancher:
            raise serializers.ValidationError({'plafondAnnuel': 'Le plafond doit depasser le plancher.'})
        return d


class ProfilSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=[c for c, _ in ProfilPaie.MODES])
    tauxHoraire = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0, required=False, default=0)
    tauxTrajet = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0, required=False, default=0)
    salairePeriode = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False,
                                              default=0)
    actif = serializers.BooleanField(required=False, default=True)

    def validate(self, d):
        requis = {'horaire': 'tauxHoraire', 'trajet': 'tauxTrajet', 'fixe': 'salairePeriode'}[d['mode']]
        if d['actif'] and not d.get(requis):
            raise serializers.ValidationError({requis: 'Indiquez le montant de la remuneration.'})
        return d


class PeriodeSerializer(serializers.Serializer):
    debut = serializers.DateField()
    fin = serializers.DateField()
    datePaiement = serializers.DateField()

    def validate(self, d):
        if d['fin'] < d['debut']:
            raise serializers.ValidationError({'fin': 'La fin precede le debut.'})
        if (d['fin'] - d['debut']).days > 31:
            raise serializers.ValidationError({'fin': 'Une periode de paie dure au plus un mois.'})
        if d['datePaiement'] < d['fin']:
            raise serializers.ValidationError({'datePaiement': 'Le paiement suit la fin de la periode.'})
        if PeriodePaie.objects.filter(debut__lte=d['fin'], fin__gte=d['debut']).exists():
            raise serializers.ValidationError({'debut': 'Ces dates chevauchent une paie existante.'})
        return d


class LigneManuelleSerializer(serializers.Serializer):
    genre = serializers.ChoiceField(choices=['gain', 'retenue'])
    libelle = serializers.CharField(max_length=150)
    montant = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    imposable = serializers.BooleanField(required=False, default=True)
