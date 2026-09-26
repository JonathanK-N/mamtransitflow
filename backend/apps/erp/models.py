"""Domaines de l'ERP. Auteur : Jonathan Kakesa (JonathanK-N)."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


def choices(*values):
    return [(v, label) for v, label in values]


ACTIVITIES = choices(('freight', 'Marchandises'), ('passengers', 'Voyageurs'),
    ('shuttle', 'Navettes et scolaire'), ('fuel', 'Carburants'), ('cold', 'Frigorifique'), ('bulk', 'Vrac'))
ROLES = choices(('owner', 'Propriétaire'), ('admin', 'Administrateur'), ('operations', 'Exploitation'),
    ('finance', 'Finance'), ('workshop', 'Atelier'), ('driver', 'Chauffeur'), ('viewer', 'Lecture seule'))
COUNTRIES = choices(('GN', 'Guinée'), ('CM', 'Cameroun'), ('CG', 'Congo'), ('CD', 'RDC'),
    ('SN', 'Sénégal'), ('CI', "Côte d'Ivoire"), ('ML', 'Mali'), ('BF', 'Burkina Faso'),
    ('BJ', 'Bénin'), ('TG', 'Togo'), ('NE', 'Niger'), ('GA', 'Gabon'), ('TD', 'Tchad'),
    ('CF', 'Centrafrique'), ('MG', 'Madagascar'), ('DJ', 'Djibouti'), ('MR', 'Mauritanie'))


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Entreprise', max_length=150)
    slug = models.SlugField('Identifiant', unique=True, max_length=80)
    country = models.CharField('Pays', max_length=2, choices=COUNTRIES, default='GN')
    currency = models.CharField('Devise', max_length=3, choices=[(c,c) for c in ['GNF','XAF','XOF','CDF','EUR','USD','MGA','MRU','DJF']], default='GNF')
    timezone = models.CharField('Fuseau horaire', max_length=60, default='Africa/Conakry')
    activities = models.JSONField('Activités', default=list)
    address = models.TextField('Adresse', blank=True)
    phone = models.CharField('Téléphone', max_length=40, blank=True)
    email = models.EmailField('Courriel', blank=True)
    registration = models.CharField('Immatriculation / registre', max_length=100, blank=True)
    tax_number = models.CharField('Identifiant fiscal', max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name


class Membership(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES, default='viewer')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization','user'], name='erp_membership_unique')]


class TenantModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        for field in self._meta.fields:
            if isinstance(field, models.ForeignKey) and field.name != 'organization' and getattr(self, field.attname):
                related = getattr(self, field.name)
                if hasattr(related, 'organization_id') and related.organization_id != self.organization_id:
                    raise ValidationError({field.name: 'Cette référence appartient à une autre entreprise.'})


def money(label, default=0):
    return models.DecimalField(label, max_digits=18, decimal_places=2, default=default, validators=[MinValueValidator(0)])


class Partner(TenantModel):
    name = models.CharField('Nom', max_length=150)
    kind = models.CharField('Type', max_length=15, choices=choices(('customer','Client'),('supplier','Fournisseur'),('both','Client et fournisseur')), default='customer')
    email = models.EmailField('Courriel', blank=True)
    phone = models.CharField('Téléphone', max_length=40, blank=True)
    address = models.TextField('Adresse', blank=True)
    tax_number = models.CharField('Identifiant fiscal', max_length=100, blank=True)
    payment_days = models.PositiveSmallIntegerField('Délai de paiement (jours)', default=30)
    notes = models.TextField('Notes', blank=True)
    def __str__(self): return self.name


class Employee(TenantModel):
    name = models.CharField('Nom complet', max_length=150)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    job = models.CharField('Fonction', max_length=20, choices=choices(('driver','Chauffeur'),('dispatcher','Exploitant'),('mechanic','Mécanicien'),('office','Administration')), default='driver')
    phone = models.CharField('Téléphone', max_length=40, blank=True)
    email = models.EmailField('Courriel', blank=True)
    license_number = models.CharField('Numéro de permis', max_length=80, blank=True)
    license_expiry = models.DateField('Expiration du permis', null=True, blank=True)
    active = models.BooleanField('Actif', default=True)
    notes = models.TextField('Notes', blank=True)
    def __str__(self): return self.name


class Vehicle(TenantModel):
    plate = models.CharField('Immatriculation', max_length=40)
    name = models.CharField('Marque / modèle', max_length=120)
    kind = models.CharField('Catégorie', max_length=20, choices=choices(('truck','Camion'),('tractor','Tracteur'),('trailer','Remorque'),('tanker','Citerne'),('bus','Autobus'),('minibus','Minibus'),('van','Fourgon'),('refrigerated','Frigorifique')), default='truck')
    status = models.CharField('Statut', max_length=20, choices=choices(('available','Disponible'),('maintenance','Atelier'),('retired','Hors service')), default='available')
    capacity = models.DecimalField('Capacité de chargement', max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    capacity_unit = models.CharField('Unité de capacité', max_length=10, choices=[(u,u) for u in ['kg','t','L','m3']], default='kg')
    seats = models.PositiveSmallIntegerField('Places voyageurs', default=0)
    mileage = models.PositiveIntegerField('Compteur (km)', default=0)
    insurance_expiry = models.DateField('Échéance assurance', null=True, blank=True)
    inspection_expiry = models.DateField('Échéance visite technique', null=True, blank=True)
    compartments = models.JSONField('Compartiments', default=list, blank=True)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','plate'], name='erp_vehicle_plate_tenant')]
    def __str__(self): return f'{self.plate} · {self.name}'


class TransportOrder(TenantModel):
    reference = models.CharField('Référence client', max_length=80)
    customer = models.ForeignKey(Partner, verbose_name='Client', on_delete=models.PROTECT)
    activity = models.CharField('Activité', max_length=20, choices=ACTIVITIES, default='freight')
    origin = models.CharField('Départ', max_length=180)
    destination = models.CharField('Destination', max_length=180)
    product = models.CharField('Marchandise / prestation', max_length=180, blank=True)
    quantity = models.DecimalField('Quantité', max_digits=15, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    unit = models.CharField('Unité', max_length=15, choices=[(u,u) for u in ['kg','t','L','m3','colis','voyageurs','mission']], default='t')
    amount = money('Prix convenu HT')
    planned_date = models.DateField('Date prévue')
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','Brouillon'),('confirmed','Confirmée'),('completed','Réalisée'),('cancelled','Annulée')), default='draft')
    notes = models.TextField('Consignes', blank=True)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_order_reference')]
    def __str__(self): return self.reference


class Route(TenantModel):
    name = models.CharField('Ligne / circuit', max_length=150)
    origin = models.CharField('Départ', max_length=180)
    destination = models.CharField('Arrivée', max_length=180)
    activity = models.CharField('Activité', max_length=20, choices=ACTIVITIES, default='passengers')
    fare = money('Tarif par place')
    stops = models.TextField('Arrêts desservis', blank=True)
    active = models.BooleanField('Active', default=True)
    def __str__(self): return self.name


class Mission(TenantModel):
    reference = models.CharField('Référence', max_length=80)
    order = models.ForeignKey(TransportOrder, verbose_name='Commande', null=True, blank=True, on_delete=models.PROTECT)
    route = models.ForeignKey(Route, verbose_name='Ligne / circuit', null=True, blank=True, on_delete=models.PROTECT)
    vehicle = models.ForeignKey(Vehicle, verbose_name='Véhicule', on_delete=models.PROTECT)
    driver = models.ForeignKey(Employee, verbose_name='Chauffeur', on_delete=models.PROTECT)
    origin = models.CharField('Départ', max_length=180)
    destination = models.CharField('Destination', max_length=180)
    departure = models.DateTimeField('Départ prévu')
    arrival = models.DateTimeField('Arrivée prévue')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField('Statut', max_length=20, choices=choices(('planned','Planifiée'),('active','En cours'),('completed','Terminée'),('cancelled','Annulée')), default='planned')
    loaded_quantity = models.DecimalField('Quantité chargée', max_digits=15, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    delivered_quantity = models.DecimalField('Quantité livrée', max_digits=15, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    delivery_note = models.TextField('Preuve / réserves de livraison', blank=True)
    notes = models.TextField('Instructions', blank=True)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_mission_reference'),
            models.UniqueConstraint(fields=['vehicle'], condition=Q(status='active'), name='erp_one_active_vehicle'),
            models.UniqueConstraint(fields=['driver'], condition=Q(status='active'), name='erp_one_active_driver'),
            models.CheckConstraint(condition=Q(arrival__gt=models.F('departure')), name='erp_mission_dates')]
    def __str__(self): return self.reference


class Booking(TenantModel):
    mission = models.ForeignKey(Mission, verbose_name='Départ / mission', on_delete=models.PROTECT)
    passenger = models.CharField('Voyageur / responsable', max_length=150)
    phone = models.CharField('Téléphone', max_length=40)
    seats = models.PositiveSmallIntegerField('Nombre de places', default=1, validators=[MinValueValidator(1)])
    amount = money('Montant')
    status = models.CharField('Statut', max_length=20, choices=choices(('confirmed','Confirmée'),('boarded','Embarqué'),('cancelled','Annulée')), default='confirmed')
    def __str__(self): return self.passenger


class Maintenance(TenantModel):
    vehicle = models.ForeignKey(Vehicle, verbose_name='Véhicule', on_delete=models.PROTECT)
    title = models.CharField('Intervention', max_length=180)
    due_date = models.DateField('Échéance', null=True, blank=True)
    due_mileage = models.PositiveIntegerField('Échéance compteur', null=True, blank=True)
    supplier = models.ForeignKey(Partner, verbose_name='Prestataire', null=True, blank=True, on_delete=models.PROTECT)
    cost = money('Coût')
    status = models.CharField('Statut', max_length=20, choices=choices(('planned','Planifiée'),('active','En cours'),('completed','Terminée'),('cancelled','Annulée')), default='planned')
    notes = models.TextField('Compte rendu', blank=True)
    def __str__(self): return self.title


class Expense(TenantModel):
    title = models.CharField('Libellé', max_length=180)
    mission = models.ForeignKey(Mission, verbose_name='Mission', null=True, blank=True, on_delete=models.PROTECT)
    category = models.CharField('Catégorie', max_length=20, choices=choices(('fuel','Carburant véhicule'),('toll','Péage'),('allowance','Frais de mission'),('repair','Réparation'),('other','Autre')), default='other')
    amount = money('Montant')
    date = models.DateField('Date')
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','À valider'),('approved','Validée')), default='draft')
    notes = models.TextField('Justificatif / notes', blank=True)
    def __str__(self): return self.title


class Invoice(TenantModel):
    number = models.CharField('Numéro', max_length=80, blank=True)
    customer = models.ForeignKey(Partner, verbose_name='Client', on_delete=models.PROTECT)
    order = models.ForeignKey(TransportOrder, verbose_name='Commande', null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField('Type', max_length=15, choices=choices(('quote','Devis'),('invoice','Facture'),('credit','Avoir')), default='invoice')
    original = models.ForeignKey('self', verbose_name="Facture d'origine", null=True, blank=True, on_delete=models.PROTECT)
    date = models.DateField('Date')
    due_date = models.DateField('Échéance')
    lines = models.JSONField('Lignes', default=list)
    subtotal = money('Total HT')
    tax = money('Taxes')
    total = money('Total TTC')
    paid = money('Réglé')
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','Brouillon'),('issued','Émise'),('paid','Soldée'),('cancelled','Annulée')), default='draft')
    notes = models.TextField('Conditions / notes', blank=True)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','number'], condition=~Q(number=''), name='erp_invoice_number')]
    def __str__(self): return self.number or 'Brouillon'


class Payment(TenantModel):
    invoice = models.ForeignKey(Invoice, verbose_name='Facture', on_delete=models.PROTECT)
    amount = money('Montant')
    date = models.DateField('Date')
    method = models.CharField('Mode', max_length=20, choices=choices(('bank','Virement'),('cash','Espèces'),('mobile','Mobile money'),('cheque','Chèque')), default='bank')
    reference = models.CharField('Référence du règlement', max_length=120)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_payment_reference')]
    def __str__(self): return self.reference


class Account(TenantModel):
    code = models.CharField('Compte', max_length=20)
    name = models.CharField('Libellé', max_length=150)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','code'], name='erp_account_code')]
        ordering = ['code']
    def __str__(self): return f'{self.code} · {self.name}'


class JournalEntry(TenantModel):
    reference = models.CharField('Référence', max_length=100)
    date = models.DateField('Date')
    description = models.CharField('Libellé', max_length=180)
    lines = models.JSONField('Écritures', default=list)
    status = models.CharField('Statut', max_length=12, choices=choices(('draft','Brouillon'),('posted','Comptabilisée')), default='draft')
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_journal_reference')]
    def __str__(self): return self.reference


class StockItem(TenantModel):
    code = models.CharField('Référence', max_length=80)
    name = models.CharField('Article', max_length=150)
    unit = models.CharField('Unité', max_length=20, default='pièce')
    quantity = models.DecimalField('Stock', max_digits=15, decimal_places=3, default=0)
    minimum = models.DecimalField('Seuil minimum', max_digits=15, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    unit_cost = money('Coût unitaire')
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','code'], name='erp_stock_code'),
            models.CheckConstraint(condition=Q(quantity__gte=0), name='erp_stock_nonnegative')]
    def __str__(self): return f'{self.code} · {self.name}'


class StockMovement(TenantModel):
    item = models.ForeignKey(StockItem, verbose_name='Article', on_delete=models.PROTECT)
    quantity = models.DecimalField('Quantité (+ entrée / - sortie)', max_digits=15, decimal_places=3)
    reason = models.CharField('Motif', max_length=180)
    reference = models.CharField('Référence unique', max_length=100)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_stock_movement_reference')]


class Purchase(TenantModel):
    reference = models.CharField('Référence', max_length=80)
    supplier = models.ForeignKey(Partner, verbose_name='Fournisseur', on_delete=models.PROTECT)
    date = models.DateField('Date')
    lines = models.JSONField('Articles commandés', default=list)
    total = money('Montant')
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','Brouillon'),('ordered','Commandée'),('received','Reçue'),('cancelled','Annulée')), default='draft')
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_purchase_reference')]
    def __str__(self): return self.reference


def private_path(instance, filename):
    from pathlib import Path
    return f'organizations/{instance.organization_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class Document(TenantModel):
    title = models.CharField('Document', max_length=180)
    category = models.CharField('Catégorie', max_length=20, choices=choices(('vehicle','Véhicule'),('driver','Personnel'),('delivery','Livraison'),('finance','Finance'),('other','Autre')), default='other')
    vehicle = models.ForeignKey(Vehicle, verbose_name='Véhicule', null=True, blank=True, on_delete=models.PROTECT)
    mission = models.ForeignKey(Mission, verbose_name='Mission', null=True, blank=True, on_delete=models.PROTECT)
    expiry = models.DateField('Expiration', null=True, blank=True)
    file = models.FileField('Fichier', upload_to=private_path)
    def __str__(self): return self.title


class Position(TenantModel):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['mission','timestamp'], name='erp_position_once')]
        indexes = [models.Index(fields=['organization','mission','timestamp'])]


class AuditEvent(TenantModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    resource = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    detail = models.JSONField(default=dict)


class TeamInvitation(TenantModel):
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLES)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class Sequence(TenantModel):
    key = models.CharField(max_length=30)
    value = models.PositiveIntegerField(default=0)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','key'], name='erp_sequence_key')]


class AuthLimit(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
