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
    city = models.CharField('Ville', max_length=100, blank=True)
    region = models.CharField('Province / région', max_length=100, blank=True)
    country = models.CharField('Pays', max_length=100, blank=True)
    postal_code = models.CharField('Code postal', max_length=30, blank=True)
    archived_at = models.DateTimeField('Archivé le', null=True, blank=True)
    contact_name = models.CharField('Nom du contact', max_length=150, blank=True)
    name = models.CharField('Nom', max_length=150)
    kind = models.CharField('Type', max_length=15, choices=choices(('customer','Client'),('supplier','Fournisseur'),('both','Client et fournisseur')), default='customer')
    email = models.EmailField('Courriel', blank=True)
    phone = models.CharField('Téléphone', max_length=40, blank=True)
    address = models.TextField('Adresse', blank=True)
    tax_number = models.CharField('Identifiant fiscal', max_length=100, blank=True)
    payment_days = models.PositiveSmallIntegerField('Délai de paiement (jours)', default=30)
    notes = models.TextField('Notes', blank=True)
    class Meta(TenantModel.Meta):
        indexes=[models.Index(fields=['organization','kind','archived_at','name'],name='erp_client_directory')]
    def __str__(self): return self.name


class PartnerContact(TenantModel):
    customer = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name='contacts')
    name = models.CharField('Nom', max_length=150)
    role = models.CharField('Fonction', max_length=100, blank=True)
    email = models.EmailField('Courriel', blank=True)
    phone = models.CharField('Téléphone', max_length=40, blank=True)
    notes = models.TextField('Notes internes', blank=True)
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
    source_quote = models.OneToOneField('Invoice', null=True, blank=True, on_delete=models.PROTECT, related_name='converted_order')
    origin_contact = models.CharField('Contact au départ', max_length=180, blank=True)
    destination_contact = models.CharField('Contact à destination', max_length=180, blank=True)
    window_start = models.DateTimeField('Début de fenêtre', null=True, blank=True)
    window_end = models.DateTimeField('Fin de fenêtre', null=True, blank=True)
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
        indexes=[models.Index(fields=['organization','customer','-created_at'],name='erp_customer_orders')]
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
    tracking_status = models.CharField(max_length=24, default="waiting", db_default="waiting")
    tracking_lost_at = models.DateTimeField(null=True, blank=True)
    tracking_started_at = models.DateTimeField(null=True, blank=True)
    tracking_ended_at = models.DateTimeField(null=True, blank=True)
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
        indexes=[models.Index(fields=['organization','status','departure'],name='erp_ops_mission_departure'),models.Index(fields=['organization','driver','departure','arrival'],name='erp_ops_driver_schedule'),models.Index(fields=['organization','vehicle','departure','arrival'],name='erp_ops_vehicle_schedule')]
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
    quote_status = models.CharField('État du devis', max_length=15, default='draft', choices=choices(('draft','Brouillon'),('sent','Envoyé'),('accepted','Accepté'),('refused','Refusé'),('expired','Expiré')))
    origin = models.CharField('Départ', max_length=180, blank=True)
    destination = models.CharField('Destination', max_length=180, blank=True)
    activity = models.CharField('Activité', max_length=20, choices=ACTIVITIES, default='freight')
    unit = models.CharField('Unité', max_length=15, choices=[(u,u) for u in ['kg','t','L','m3','colis','voyageurs','mission']], default='mission')
    mission = models.ForeignKey(Mission, verbose_name='Mission', null=True, blank=True, on_delete=models.PROTECT)
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
        indexes=[models.Index(fields=['organization','customer','kind','status'],name='erp_customer_invoices')]
    def __str__(self): return self.number or 'Brouillon'


class Payment(TenantModel):
    notes = models.TextField('Notes', blank=True)
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
    customer = models.ForeignKey(Partner, verbose_name='Client', null=True, blank=True, on_delete=models.PROTECT)
    title = models.CharField('Document', max_length=180)
    category = models.CharField('Catégorie', max_length=20, choices=choices(('vehicle','Véhicule'),('driver','Personnel'),('delivery','Livraison'),('finance','Finance'),('other','Autre')), default='other')
    vehicle = models.ForeignKey(Vehicle, verbose_name='Véhicule', null=True, blank=True, on_delete=models.PROTECT)
    mission = models.ForeignKey(Mission, verbose_name='Mission', null=True, blank=True, on_delete=models.PROTECT)
    expiry = models.DateField('Expiration', null=True, blank=True)
    shared_with_customer = models.BooleanField('Visible dans le portail client', default=False)
    file = models.FileField('Fichier', upload_to=private_path)
    def __str__(self): return self.title


class Position(TenantModel):
    accuracy = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    client_id = models.UUIDField(null=True, blank=True)
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['mission','timestamp'], name='erp_position_once'), models.UniqueConstraint(fields=['mission','client_id'], name='erp_position_client_once')]
        indexes = [models.Index(fields=['organization','mission','timestamp'])]


class AuditEvent(TenantModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    resource = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    detail = models.JSONField(default=dict)
    class Meta(TenantModel.Meta):
        indexes=[models.Index(fields=['organization','resource','object_id','-created_at'],name='erp_client_audit_lookup')]


class TeamInvitation(TenantModel):
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLES+[('client','Client externe')])
    partner = models.ForeignKey(Partner, null=True, blank=True, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)


class Sequence(TenantModel):
    key = models.CharField(max_length=30)
    value = models.PositiveIntegerField(default=0)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','key'], name='erp_sequence_key')]


class AuthLimit(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class InstalledApplication(TenantModel):
    key = models.SlugField(max_length=60)
    enabled = models.BooleanField(default=True)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','key'],name='erp_installed_app_unique')]


class CustomApplication(TenantModel):
    name = models.CharField('Application',max_length=80)
    slug = models.SlugField(max_length=80)
    description = models.CharField('Description',max_length=500,blank=True)
    icon = models.CharField(max_length=20,default='folder')
    color = models.CharField(max_length=20,default='green')
    fields = models.JSONField(default=list)
    read_roles = models.JSONField(default=list)
    write_roles = models.JSONField(default=list)
    enabled = models.BooleanField(default=True)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','slug'],name='erp_custom_app_slug')]
    def __str__(self):return self.name


class CustomRecord(TenantModel):
    application = models.ForeignKey(CustomApplication,on_delete=models.PROTECT,related_name='records')
    title = models.CharField(max_length=200)
    data = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    def __str__(self):return self.title


class TransportContract(TenantModel):
    reference = models.CharField('Référence',max_length=80)
    customer = models.ForeignKey(Partner,verbose_name='Client',on_delete=models.PROTECT)
    activity = models.CharField('Activité',max_length=20,choices=ACTIVITIES,default='freight')
    origin = models.CharField('Départ',max_length=180)
    destination = models.CharField('Destination',max_length=180)
    description = models.TextField('Prestation et conditions',blank=True)
    quantity = models.DecimalField('Quantité par prestation',max_digits=15,decimal_places=3,default=1,validators=[MinValueValidator(Decimal('.001'))])
    unit = models.CharField('Unité',max_length=15,choices=[(u,u) for u in ['kg','t','L','m3','colis','voyageurs','mission']],default='mission')
    amount = money('Prix HT par prestation')
    start_date = models.DateField('Début du contrat')
    end_date = models.DateField('Fin du contrat')
    recurrence = models.CharField('Récurrence',max_length=12,choices=choices(('once','Ponctuelle'),('weekly','Hebdomadaire'),('monthly','Mensuelle')),default='monthly')
    next_date = models.DateField('Prochaine prestation',null=True,blank=True)
    status = models.CharField('Statut',max_length=15,choices=choices(('draft','Brouillon'),('active','Actif'),('paused','Suspendu'),('closed','Clôturé')),default='draft')
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['organization','reference'],name='erp_contract_reference')]
    def __str__(self):return self.reference


class PricingRule(TenantModel):
    name = models.CharField('Grille tarifaire',max_length=120)
    activity = models.CharField('Activité',max_length=20,choices=ACTIVITIES,default='freight')
    origin = models.CharField('Départ',max_length=180)
    destination = models.CharField('Destination',max_length=180)
    unit = models.CharField('Unité',max_length=15,choices=[(u,u) for u in ['kg','t','L','m3','colis','voyageurs','mission']],default='t')
    unit_price = money('Prix HT par unité')
    minimum = money('Minimum de facturation HT')
    valid_from = models.DateField('Valable à partir du')
    valid_until = models.DateField('Valable jusqu’au')
    active = models.BooleanField('Active',default=True)
    def __str__(self):return self.name


class Subcontract(TenantModel):
    reference = models.CharField('Référence',max_length=80)
    mission = models.ForeignKey(Mission,verbose_name='Mission',on_delete=models.PROTECT)
    supplier = models.ForeignKey(Partner,verbose_name='Transporteur sous-traitant',on_delete=models.PROTECT)
    agreed_amount = money('Montant HT convenu')
    due_date = models.DateField('Échéance contractuelle')
    conditions = models.TextField('Conditions et responsabilités',blank=True)
    external_vehicle = models.CharField('Véhicule du prestataire',max_length=100,blank=True)
    external_driver = models.CharField('Chauffeur du prestataire',max_length=150,blank=True)
    completion_note = models.TextField('Bilan de prestation',blank=True)
    status = models.CharField('Statut',max_length=15,choices=choices(('draft','Brouillon'),('approved','Approuvée'),('completed','Réalisée'),('cancelled','Annulée')),default='draft')
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['organization','reference'],name='erp_subcontract_reference')]
    def __str__(self):return self.reference


class Incident(TenantModel):
    reference = models.CharField('Référence',max_length=80)
    title = models.CharField('Incident',max_length=180)
    mission = models.ForeignKey(Mission,verbose_name='Mission',null=True,blank=True,on_delete=models.PROTECT)
    vehicle = models.ForeignKey(Vehicle,verbose_name='Véhicule',on_delete=models.PROTECT)
    occurred_at = models.DateTimeField('Survenu le')
    severity = models.CharField('Gravité',max_length=15,choices=choices(('minor','Mineure'),('major','Majeure'),('critical','Critique')),default='minor')
    category = models.CharField('Nature',max_length=20,choices=choices(('breakdown','Panne'),('accident','Accident'),('cargo','Marchandise'),('delay','Retard'),('other','Autre')),default='other')
    description = models.TextField('Faits constatés')
    claim_reference = models.CharField('Dossier assurance',max_length=100,blank=True)
    estimated_cost = money('Coût estimé')
    resolution = models.TextField('Mesures prises et résolution',blank=True)
    resolved_at = models.DateTimeField(null=True,blank=True)
    status = models.CharField('Statut',max_length=15,choices=choices(('draft','Brouillon'),('reported','Signalé'),('resolved','Résolu')),default='draft')
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['organization','reference'],name='erp_incident_reference')]
    def __str__(self):return self.title


class FieldReport(TenantModel):
    mission = models.ForeignKey(Mission, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=choices(('incident','Incident'),('request','Demande atelier'),('check','Contrôle avant départ'),('mileage','Relevé compteur')))
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    checks = models.JSONField(default=dict, blank=True)
    incident = models.ForeignKey(Incident, null=True, blank=True, on_delete=models.PROTECT)
    maintenance = models.ForeignKey(Maintenance, null=True, blank=True, on_delete=models.PROTECT)


class FieldAttachment(TenantModel):
    report = models.ForeignKey(FieldReport, on_delete=models.PROTECT, related_name='attachments')
    file = models.FileField(upload_to=private_path)
    title = models.CharField(max_length=180)


class NotificationRead(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=64)
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','user','key'], name='erp_notification_read_unique')]


class SupplierBill(TenantModel):
    reference = models.CharField('Numéro fournisseur',max_length=100)
    supplier = models.ForeignKey(Partner,verbose_name='Fournisseur',on_delete=models.PROTECT)
    purchase = models.ForeignKey(Purchase,verbose_name='Commande d’achat',null=True,blank=True,on_delete=models.PROTECT)
    subcontract = models.ForeignKey(Subcontract,verbose_name='Sous-traitance',null=True,blank=True,on_delete=models.PROTECT)
    date = models.DateField('Date')
    due_date = models.DateField('Échéance')
    lines = models.JSONField('Prestations facturées',default=list)
    subtotal = money('Total HT')
    tax = money('Taxes')
    total = money('Total TTC')
    paid = money('Réglé')
    status = models.CharField('Statut',max_length=15,choices=choices(('draft','Brouillon'),('posted','Comptabilisée'),('paid','Soldée'),('cancelled','Annulée')),default='draft')
    notes = models.TextField('Notes',blank=True)
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['organization','supplier','reference'],name='erp_supplier_bill_reference'),
            models.UniqueConstraint(fields=['purchase'],condition=Q(purchase__isnull=False)&~Q(status='cancelled'),name='erp_one_bill_per_purchase'),
            models.UniqueConstraint(fields=['subcontract'],condition=Q(subcontract__isnull=False)&~Q(status='cancelled'),name='erp_one_bill_per_subcontract')]
    def __str__(self):return self.reference


class SupplierPayment(TenantModel):
    bill = models.ForeignKey(SupplierBill,verbose_name='Facture fournisseur',on_delete=models.PROTECT)
    reference = models.CharField('Référence du règlement',max_length=100)
    amount = money('Montant réglé')
    date = models.DateField('Date du règlement')
    method = models.CharField('Mode',max_length=20,choices=Payment._meta.get_field('method').choices,default='bank')
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['organization','reference'],name='erp_supplier_payment_reference')]
    def __str__(self):return self.reference


class LeaveRequest(TenantModel):
    employee = models.ForeignKey(Employee, verbose_name='Salarié', on_delete=models.PROTECT)
    start_date = models.DateField('Début')
    end_date = models.DateField('Fin incluse')
    kind = models.CharField('Nature', max_length=20, choices=choices(('annual','Congé annuel'),('unpaid','Sans solde'),('sick','Maladie'),('other','Autre')), default='annual')
    reason = models.TextField('Motif', blank=True)
    decision_note = models.TextField('Motif de décision', blank=True)
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','Brouillon'),('submitted','À approuver'),('approved','Approuvé'),('rejected','Refusé'),('cancelled','Annulé')), default='draft')
    def __str__(self): return f'{self.employee} · {self.start_date}'


class EmployeeAdvance(TenantModel):
    reference = models.CharField('Référence', max_length=80)
    employee = models.ForeignKey(Employee, verbose_name='Salarié', on_delete=models.PROTECT)
    amount = money('Montant')
    date = models.DateField('Date demandée')
    reason = models.TextField('Motif')
    payment_reference = models.CharField('Justificatif du décaissement', max_length=120, blank=True)
    payment_date = models.DateField('Date du décaissement', null=True, blank=True)
    settlement_reference = models.CharField('Justificatif du remboursement', max_length=120, blank=True)
    settlement_date = models.DateField('Date du remboursement', null=True, blank=True)
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','Brouillon'),('approved','Approuvée'),('disbursed','Versée'),('settled','Remboursée'),('cancelled','Annulée')), default='draft')
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','reference'], name='erp_advance_reference')]
    def __str__(self): return self.reference


class FiscalPeriod(TenantModel):
    name = models.CharField('Période', max_length=100)
    start_date = models.DateField('Début')
    end_date = models.DateField('Fin incluse')
    closing_note = models.TextField('Note de clôture', blank=True)
    closed_at = models.DateTimeField('Clôturée le', null=True, blank=True)
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','Ouverte'),('closed','Clôturée')), default='draft')
    def __str__(self): return self.name


class BankStatementLine(TenantModel):
    reference = models.CharField('Référence du relevé / opération', max_length=120)
    account = models.ForeignKey(Account, verbose_name='Compte de trésorerie', on_delete=models.PROTECT)
    date = models.DateField('Date de valeur')
    description = models.CharField('Libellé bancaire', max_length=180)
    amount = models.DecimalField('Montant (+ entrée / − sortie)', max_digits=18, decimal_places=2)
    journal = models.ForeignKey(JournalEntry, verbose_name='Écriture rapprochée', null=True, blank=True, on_delete=models.PROTECT)
    reconciliation_note = models.TextField('Note de rapprochement', blank=True)
    status = models.CharField('Statut', max_length=20, choices=choices(('draft','À rapprocher'),('matched','Rapprochée')), default='draft')
    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=['organization','account','reference'], name='erp_statement_reference'),
            models.UniqueConstraint(fields=['organization','account','journal'], condition=Q(status='matched'), name='erp_statement_match')]
    def __str__(self): return self.reference


class DeliveryReceipt(TenantModel):
    mission = models.OneToOneField(Mission, on_delete=models.PROTECT, related_name='receipt')
    recipient_name = models.CharField(max_length=150)
    reservations = models.TextField(blank=True)
    signature = models.JSONField()
    snapshot = models.JSONField()
    digest = models.CharField(max_length=64)
    signed_at = models.DateTimeField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    def __str__(self): return str(self.id)


class PortalAccess(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['organization','user'],name='erp_portal_user_unique')]

class ClientConversation(TenantModel):
    access = models.OneToOneField(PortalAccess, on_delete=models.PROTECT, related_name='conversation')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)


class ClientMessage(TenantModel):
    conversation = models.ForeignKey(ClientConversation, on_delete=models.PROTECT, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    client_id = models.UUIDField()
    class Meta(TenantModel.Meta):
        constraints=[models.UniqueConstraint(fields=['conversation','sender','client_id'],name='erp_client_message_retry_unique')]


from .chat_models import Conversation, ConversationParticipant, Message, MessageAttachment, GlobalNotification, NotificationPreference, PushSubscription
