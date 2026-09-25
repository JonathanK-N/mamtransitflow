"""
Retenues par defaut : parametres officiels 2026 pour un employe au Quebec.
Sources : Retraite Quebec (RRQ), Emploi et Developpement social Canada (AE),
Revenu Quebec (RQAP). A mettre a jour chaque 1er janvier (Parametres > Paie).
"""

from decimal import Decimal as D

from django.db import migrations

RETENUES_2026 = [
    # code, libelle, taux salarie, taux employeur, plancher, plafond, exemption, note, actif, ordre
    ('RRQ', 'Regime de rentes du Quebec', D('6.300'), D('6.300'), D('0'), D('74600'), D('3500'),
     'Base 5,3 % + supplementaire 1 %, jusqu au MGA de 74 600 $, exemption 3 500 $ (2026).', True, 10),
    ('RRQ2', 'RRQ - cotisation supplementaire', D('4.000'), D('4.000'), D('74600'), D('85000'), D('0'),
     '4 % sur les gains entre 74 600 $ et 85 000 $ (2026).', True, 20),
    ('AE', 'Assurance-emploi', D('1.300'), D('1.820'), D('0'), D('68900'), D('0'),
     'Taux Quebec 2026 ; maximum de la remuneration assurable 68 900 $.', True, 30),
    ('RQAP', 'Regime quebecois d assurance parentale', D('0.430'), D('0.602'), D('0'), D('103000'), D('0'),
     'Taux 2026 ; maximum des revenus assurables 103 000 $.', True, 40),
    ('IMP-QC', 'Impot du Quebec (estimation)', D('0'), D('0'), D('0'), None, D('0'),
     'A configurer : taux forfaitaire. Ne remplace pas la table TP-1015.F.', False, 50),
    ('IMP-FED', 'Impot federal (estimation)', D('0'), D('0'), D('0'), None, D('0'),
     'A configurer : taux forfaitaire. Ne remplace pas la table T4127.', False, 60),
]


def creer(apps, schema_editor):
    Retenue = apps.get_model('paie', 'Retenue')
    for code, libelle, ts, te, plancher, plafond, exemption, note, actif, ordre in RETENUES_2026:
        Retenue.objects.get_or_create(code=code, defaults=dict(
            libelle=libelle, taux_salarie=ts, taux_employeur=te, plancher_annuel=plancher, plafond_annuel=plafond,
            exemption_annuelle=exemption, note=note, actif=actif, ordre=ordre))
    apps.get_model('paie', 'ParametresPaie').objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('paie', '0001_initial')]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
