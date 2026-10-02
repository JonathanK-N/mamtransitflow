# TransitFlow ERP - Modèle relationnel logique

Jonathan Kakesa Nayaba, CPI_CEO Cognito Inc.

Version : b51ce1638be67af030f961a42f07ba74e6baf348 ; migration ERP 0013_field_tenant_integrity.

- Schéma reconstruit à partir des migrations du code livré. Aucun enregistrement utilisateur ni secret de connexion n’est inclus.
- Les migrations ERP locales 0014 et 0015, non livrées, sont exclues.
- Les politiques de suppression affichées sont celles de Django. Elles ne doivent pas être interprétées comme des clauses SQL ON DELETE.
- Une référence obligatoire donne une cible 1 ; une référence nullable donne une cible 0..1. La présence d’enfants reste 0..N, ou 0..1 si la référence est unique.
- Les clés étrangères composites PostgreSQL protègent les liens au sein d’une même entreprise.
- Les tables historiques sont conservées dans le schéma mais leurs routes globales sont désactivées par défaut dans le SaaS.
- Le contenu des champs JSON relève du modèle applicatif : il ne crée pas automatiquement des tables ni des clés étrangères.

## auth_group - groups

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | integer | PK | non |  |
| name | varchar(150) | UNIQUE | non |  |

## auth_group_permissions - Relations group-permission

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| group_id | integer | FK | non | auth_group.id ; Django CASCADE |
| permission_id | integer | FK | non | auth_permission.id ; Django CASCADE |

Contrainte : `unique_together` - Unicité du groupe

## auth_permission - permissions

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | integer | PK | non |  |
| name | varchar(255) |  | non |  |
| content_type_id | integer | FK | non | django_content_type.id ; Django CASCADE |
| codename | varchar(100) |  | non |  |

Contrainte : `unique_together` - Unicité du groupe

## comptes_invitation - invitations

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| type | varchar(20) |  | non |  |
| courriel | varchar(254) |  | non |  |
| empreinte | varchar(64) | UNIQUE | non |  |
| expire_le | timestamp with time zone |  | non |  |
| utilisee_le | timestamp with time zone |  | oui |  |
| revoquee | boolean |  | non |  |
| courriel_envoye | boolean |  | non |  |
| cree_le | timestamp with time zone |  | non |  |
| chauffeur_id | bigint | FK | oui | drivers_chauffeur.id ; Django CASCADE |
| cree_par_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| utilisateur_id | bigint | FK | oui | comptes_utilisateur.id ; Django CASCADE |

## comptes_utilisateur - Utilisateurs

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| password | varchar(128) |  | non |  |
| last_login | timestamp with time zone |  | oui |  |
| is_superuser | boolean |  | non |  |
| courriel | varchar(254) | UNIQUE | non |  |
| nom | varchar(150) |  | non |  |
| is_active | boolean |  | non |  |
| is_staff | boolean |  | non |  |
| cree_le | timestamp with time zone |  | non |  |
| chauffeur_id | bigint | FK, UNIQUE | oui | drivers_chauffeur.id ; Django SET_NULL |

## comptes_utilisateur_groups - Relations utilisateur-group

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| utilisateur_id | bigint | FK | non | comptes_utilisateur.id ; Django CASCADE |
| group_id | integer | FK | non | auth_group.id ; Django CASCADE |

Contrainte : `unique_together` - Unicité du groupe

## comptes_utilisateur_user_permissions - Relations utilisateur-permission

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| utilisateur_id | bigint | FK | non | comptes_utilisateur.id ; Django CASCADE |
| permission_id | integer | FK | non | auth_permission.id ; Django CASCADE |

Contrainte : `unique_together` - Unicité du groupe

## dispatch_arret - arrets

Groupe : Historique / dispatch

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| lieu | varchar(150) |  | non |  |
| heure | varchar(5) |  | non |  |
| note | varchar(255) |  | non |  |
| trajet_id | bigint | FK | non | dispatch_trajet.id ; Django CASCADE |

## dispatch_trajet - trajets

Groupe : Historique / dispatch

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| plaque | varchar(20) |  | non |  |
| depart | varchar(150) |  | non |  |
| depart_adresse | varchar(255) |  | oui |  |
| arrivee | varchar(150) |  | non |  |
| debut | timestamp with time zone |  | non |  |
| fin_prevue | timestamp with time zone |  | non |  |
| fin | timestamp with time zone |  | oui |  |
| statut | varchar(20) |  | non |  |
| chauffeur_id | bigint | FK | non | drivers_chauffeur.id ; Django CASCADE |

## django_admin_log - log entries

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | integer | PK | non |  |
| action_time | timestamp with time zone |  | non |  |
| object_id | text |  | oui |  |
| object_repr | varchar(200) |  | non |  |
| action_flag | smallint |  | non |  |
| change_message | text |  | non |  |
| content_type_id | integer | FK | oui | django_content_type.id ; Django SET_NULL |
| user_id | bigint | FK | non | comptes_utilisateur.id ; Django CASCADE |

## django_content_type - content types

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | integer | PK | non |  |
| app_label | varchar(100) |  | non |  |
| model | varchar(100) |  | non |  |

Contrainte : `unique_together` - Unicité du groupe

## django_migrations - migrations

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| app | varchar(255) |  | non |  |
| name | varchar(255) |  | non |  |
| applied | timestamp with time zone |  | non |  |

## django_session - sessions

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| session_key | varchar(40) | PK | non |  |
| session_data | text |  | non |  |
| expire_date | timestamp with time zone |  | non |  |

## drivers_chauffeur - chauffeurs

Groupe : Historique / drivers

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| prenom | varchar(100) |  | non |  |
| nom | varchar(100) |  | non |  |
| age | smallint |  | non |  |
| telephone | varchar(30) |  | non |  |
| courriel | varchar(254) |  | non |  |
| adresse | varchar(255) |  | non |  |
| permis_numero | varchar(50) |  | non |  |
| permis_expiration | date |  | non |  |
| statut | varchar(20) |  | non |  |
| cree_le | timestamp with time zone |  | non |  |
| plaque_habituelle | varchar(20) | FK | oui | fleet_vehicule.plaque ; Django SET_NULL |

## entretien_bontravail - bon travails

Groupe : Historique / entretien

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| categorie | varchar(20) |  | non |  |
| type | varchar(20) |  | non |  |
| titre | varchar(150) |  | non |  |
| description | text |  | non |  |
| priorite | varchar(20) |  | non |  |
| statut | varchar(20) |  | non |  |
| date_prevue | date |  | non |  |
| debut | timestamp with time zone |  | oui |  |
| fin | timestamp with time zone |  | oui |  |
| kilometrage | integer |  | oui |  |
| fournisseur | varchar(150) |  | non |  |
| cout_pieces | numeric(10, 2) |  | non |  |
| cout_main_oeuvre | numeric(10, 2) |  | non |  |
| notes_cloture | text |  | non |  |
| cree_le | timestamp with time zone |  | non |  |
| modifie_le | timestamp with time zone |  | non |  |
| cree_par_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| incident_id | bigint | FK, UNIQUE | oui | maintenance_incident.id ; Django SET_NULL |
| vehicule_id | bigint | FK | non | fleet_vehicule.id ; Django PROTECT |
| plan_id | bigint | FK | oui | entretien_planentretien.id ; Django SET_NULL |

## entretien_planentretien - plan entretiens

Groupe : Historique / entretien

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| type | varchar(20) |  | non |  |
| libelle | varchar(150) |  | non |  |
| intervalle_km | integer |  | oui |  |
| intervalle_jours | integer |  | oui |  |
| dernier_km | integer |  | non |  |
| derniere_date | date |  | non |  |
| actif | boolean |  | non |  |
| cree_le | timestamp with time zone |  | non |  |
| vehicule_id | bigint | FK | non | fleet_vehicule.id ; Django CASCADE |

Contrainte : `plan_entretien_intervalle_requis` - <CheckConstraint: condition=(OR: ('intervalle_km__isnull', False), ('intervalle_jours__isnull', False)) name='plan_entretien_intervalle_requis'>

## erp_account - Comptes comptables

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| code | varchar(20) |  | non |  |
| name | varchar(150) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_account_code` - <UniqueConstraint: fields=('organization', 'code') name='erp_account_code'>

```sql
ALTER TABLE "erp_account" ADD CONSTRAINT "erp_account_tenant_identity" UNIQUE (organization_id,id);
```

## erp_auditevent - Événements d’audit

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| action | varchar(40) |  | non |  |
| resource | varchar(80) |  | non |  |
| object_id | varchar(80) |  | non |  |
| detail | jsonb |  | non |  |
| actor_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_auditevent" ADD CONSTRAINT "erp_auditevent_tenant_identity" UNIQUE (organization_id,id);
```

## erp_authlimit - Limites d’authentification

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| key | varchar(64) | UNIQUE | non |  |
| count | integer |  | non |  |
| expires_at | timestamp with time zone |  | non |  |

## erp_bankstatementline - Lignes de relevé

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(120) |  | non |  |
| date | date |  | non |  |
| description | varchar(180) |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| reconciliation_note | text |  | non |  |
| status | varchar(20) |  | non |  |
| account_id | uuid | FK | non | erp_account.id ; Django PROTECT |
| journal_id | uuid | FK | oui | erp_journalentry.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_statement_reference` - <UniqueConstraint: fields=('organization', 'account', 'reference') name='erp_statement_reference'>

Contrainte : `erp_statement_match` - <UniqueConstraint: fields=('organization', 'account', 'journal') name='erp_statement_match' condition=(AND: ('status', 'matched'))>

```sql
ALTER TABLE "erp_bankstatementline" ADD CONSTRAINT "erp_bankstatementline_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_bankstatementline" ADD CONSTRAINT "erp_tenant_fk_1d0f7aa53000c71c" FOREIGN KEY (organization_id,"account_id") REFERENCES "erp_account" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_bankstatementline" ADD CONSTRAINT "erp_tenant_fk_48f644f95a385d9e" FOREIGN KEY (organization_id,"journal_id") REFERENCES "erp_journalentry" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_booking - Réservations

Groupe : Flotte et transport

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| passenger | varchar(150) |  | non |  |
| phone | varchar(40) |  | non |  |
| seats | smallint |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| status | varchar(20) |  | non |  |
| mission_id | uuid | FK | non | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_booking" ADD CONSTRAINT "erp_booking_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_booking" ADD CONSTRAINT "erp_tenant_fk_fca7eba1531c7a29" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_customapplication - Applications personnalisées

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| name | varchar(80) |  | non |  |
| slug | varchar(80) |  | non |  |
| description | varchar(500) |  | non |  |
| icon | varchar(20) |  | non |  |
| color | varchar(20) |  | non |  |
| fields | jsonb |  | non |  |
| read_roles | jsonb |  | non |  |
| write_roles | jsonb |  | non |  |
| enabled | boolean |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_custom_app_slug` - <UniqueConstraint: fields=('organization', 'slug') name='erp_custom_app_slug'>

```sql
ALTER TABLE "erp_customapplication" ADD CONSTRAINT "erp_customapplication_tenant_identity" UNIQUE (organization_id,id);
```

## erp_customrecord - Fiches personnalisées

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| title | varchar(200) |  | non |  |
| data | jsonb |  | non |  |
| revision | integer |  | non |  |
| application_id | uuid | FK | non | erp_customapplication.id ; Django PROTECT |
| created_by_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_customrecord" ADD CONSTRAINT "erp_customrecord_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_customrecord" ADD CONSTRAINT "erp_tenant_fk_9cfaaaafae441909" FOREIGN KEY (organization_id,"application_id") REFERENCES "erp_customapplication" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_deliveryreceipt - Preuves de livraison

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| recipient_name | varchar(150) |  | non |  |
| reservations | text |  | non |  |
| signature | jsonb |  | non |  |
| snapshot | jsonb |  | non |  |
| digest | varchar(64) |  | non |  |
| signed_at | timestamp with time zone |  | non |  |
| mission_id | uuid | FK, UNIQUE | non | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| recorded_by_id | bigint | FK | non | comptes_utilisateur.id ; Django PROTECT |

```sql
ALTER TABLE "erp_deliveryreceipt" ADD CONSTRAINT "erp_deliveryreceipt_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_deliveryreceipt" ADD CONSTRAINT "erp_tenant_fk_e4534ded5bbb6a4c" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_document - Documents

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| title | varchar(180) |  | non |  |
| category | varchar(20) |  | non |  |
| expiry | date |  | oui |  |
| file | varchar(100) |  | non |  |
| mission_id | uuid | FK | oui | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| vehicle_id | uuid | FK | oui | erp_vehicle.id ; Django PROTECT |
| shared_with_customer | boolean |  | non |  |

```sql
ALTER TABLE "erp_document" ADD CONSTRAINT "erp_document_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_document" ADD CONSTRAINT "erp_tenant_fk_ea458c8551219df4" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_document" ADD CONSTRAINT "erp_tenant_fk_bf0d6f4425966793" FOREIGN KEY (organization_id,"vehicle_id") REFERENCES "erp_vehicle" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_employee - Personnel

Groupe : Flotte et transport

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| name | varchar(150) |  | non |  |
| job | varchar(20) |  | non |  |
| phone | varchar(40) |  | non |  |
| email | varchar(254) |  | non |  |
| license_number | varchar(80) |  | non |  |
| license_expiry | date |  | oui |  |
| active | boolean |  | non |  |
| notes | text |  | non |  |
| user_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_employee" ADD CONSTRAINT "erp_employee_tenant_identity" UNIQUE (organization_id,id);
```

## erp_employeeadvance - Avances au personnel

Groupe : Personnel

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| date | date |  | non |  |
| reason | text |  | non |  |
| payment_reference | varchar(120) |  | non |  |
| payment_date | date |  | oui |  |
| settlement_reference | varchar(120) |  | non |  |
| settlement_date | date |  | oui |  |
| status | varchar(20) |  | non |  |
| employee_id | uuid | FK | non | erp_employee.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_advance_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_advance_reference'>

```sql
ALTER TABLE "erp_employeeadvance" ADD CONSTRAINT "erp_employeeadvance_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_employeeadvance" ADD CONSTRAINT "erp_tenant_fk_201b8bd20008cffa" FOREIGN KEY (organization_id,"employee_id") REFERENCES "erp_employee" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_expense - Dépenses

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| title | varchar(180) |  | non |  |
| category | varchar(20) |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| date | date |  | non |  |
| status | varchar(20) |  | non |  |
| notes | text |  | non |  |
| mission_id | uuid | FK | oui | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_expense" ADD CONSTRAINT "erp_expense_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_expense" ADD CONSTRAINT "erp_tenant_fk_abb0d26b18a88738" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_fieldattachment - Pièces terrain

Groupe : Terrain et atelier

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| file | varchar(100) |  | non |  |
| title | varchar(180) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| report_id | uuid | FK | non | erp_fieldreport.id ; Django PROTECT |

```sql
ALTER TABLE "erp_fieldattachment" ADD CONSTRAINT "erp_fieldattachment_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_fieldattachment" ADD CONSTRAINT "erp_tenant_fk_a11c2f39af4e70d8" FOREIGN KEY (organization_id,"report_id") REFERENCES "erp_fieldreport" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_fieldreport - Déclarations terrain

Groupe : Terrain et atelier

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| kind | varchar(20) |  | non |  |
| title | varchar(180) |  | non |  |
| description | text |  | non |  |
| mileage | integer |  | oui |  |
| checks | jsonb |  | non |  |
| actor_id | bigint | FK | non | comptes_utilisateur.id ; Django PROTECT |
| incident_id | uuid | FK | oui | erp_incident.id ; Django PROTECT |
| maintenance_id | uuid | FK | oui | erp_maintenance.id ; Django PROTECT |
| mission_id | uuid | FK | non | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_fieldreport" ADD CONSTRAINT "erp_fieldreport_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_fieldreport" ADD CONSTRAINT "erp_tenant_fk_85b5f06063f1f40b" FOREIGN KEY (organization_id,"incident_id") REFERENCES "erp_incident" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_fieldreport" ADD CONSTRAINT "erp_tenant_fk_09de38a3804ea131" FOREIGN KEY (organization_id,"maintenance_id") REFERENCES "erp_maintenance" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_fieldreport" ADD CONSTRAINT "erp_tenant_fk_ffe1c3f04207be35" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_fiscalperiod - Périodes comptables

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| name | varchar(100) |  | non |  |
| start_date | date |  | non |  |
| end_date | date |  | non |  |
| closing_note | text |  | non |  |
| closed_at | timestamp with time zone |  | oui |  |
| status | varchar(20) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_fiscalperiod" ADD CONSTRAINT "erp_fiscalperiod_tenant_identity" UNIQUE (organization_id,id);
```

## erp_incident - Incidents

Groupe : Terrain et atelier

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| title | varchar(180) |  | non |  |
| occurred_at | timestamp with time zone |  | non |  |
| severity | varchar(15) |  | non |  |
| category | varchar(20) |  | non |  |
| description | text |  | non |  |
| claim_reference | varchar(100) |  | non |  |
| estimated_cost | numeric(18, 2) |  | non |  |
| resolution | text |  | non |  |
| resolved_at | timestamp with time zone |  | oui |  |
| status | varchar(15) |  | non |  |
| mission_id | uuid | FK | oui | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| vehicle_id | uuid | FK | non | erp_vehicle.id ; Django PROTECT |

Contrainte : `erp_incident_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_incident_reference'>

```sql
ALTER TABLE "erp_incident" ADD CONSTRAINT "erp_incident_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_incident" ADD CONSTRAINT "erp_tenant_fk_fbc1d5fdd3443194" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_incident" ADD CONSTRAINT "erp_tenant_fk_c5cd16d5246cec5b" FOREIGN KEY (organization_id,"vehicle_id") REFERENCES "erp_vehicle" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_installedapplication - Applications installées

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| key | varchar(60) |  | non |  |
| enabled | boolean |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_installed_app_unique` - <UniqueConstraint: fields=('organization', 'key') name='erp_installed_app_unique'>

```sql
ALTER TABLE "erp_installedapplication" ADD CONSTRAINT "erp_installedapplication_tenant_identity" UNIQUE (organization_id,id);
```

## erp_invoice - Factures clients

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| number | varchar(80) |  | non |  |
| kind | varchar(15) |  | non |  |
| date | date |  | non |  |
| due_date | date |  | non |  |
| lines | jsonb |  | non |  |
| subtotal | numeric(18, 2) |  | non |  |
| tax | numeric(18, 2) |  | non |  |
| total | numeric(18, 2) |  | non |  |
| paid | numeric(18, 2) |  | non |  |
| status | varchar(20) |  | non |  |
| notes | text |  | non |  |
| original_id | uuid | FK | oui | erp_invoice.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| customer_id | uuid | FK | non | erp_partner.id ; Django PROTECT |
| order_id | uuid | FK | oui | erp_transportorder.id ; Django PROTECT |

Contrainte : `erp_invoice_number` - <UniqueConstraint: fields=('organization', 'number') name='erp_invoice_number' condition=(NOT (AND: ('number', '')))>

```sql
ALTER TABLE "erp_invoice" ADD CONSTRAINT "erp_invoice_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_invoice" ADD CONSTRAINT "erp_tenant_fk_12e93d0b80df764c" FOREIGN KEY (organization_id,"original_id") REFERENCES "erp_invoice" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_invoice" ADD CONSTRAINT "erp_tenant_fk_5884fc3d0f15d093" FOREIGN KEY (organization_id,"customer_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_invoice" ADD CONSTRAINT "erp_tenant_fk_26c0d12d19e40f7c" FOREIGN KEY (organization_id,"order_id") REFERENCES "erp_transportorder" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_journalentry - Écritures comptables

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(100) |  | non |  |
| date | date |  | non |  |
| description | varchar(180) |  | non |  |
| lines | jsonb |  | non |  |
| status | varchar(12) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_journal_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_journal_reference'>

```sql
ALTER TABLE "erp_journalentry" ADD CONSTRAINT "erp_journalentry_tenant_identity" UNIQUE (organization_id,id);
```

## erp_leaverequest - Demandes de congé

Groupe : Personnel

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| start_date | date |  | non |  |
| end_date | date |  | non |  |
| kind | varchar(20) |  | non |  |
| reason | text |  | non |  |
| decision_note | text |  | non |  |
| status | varchar(20) |  | non |  |
| employee_id | uuid | FK | non | erp_employee.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_leaverequest" ADD CONSTRAINT "erp_leaverequest_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_leaverequest" ADD CONSTRAINT "erp_tenant_fk_06828a0749cb2c79" FOREIGN KEY (organization_id,"employee_id") REFERENCES "erp_employee" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_maintenance - Entretiens

Groupe : Terrain et atelier

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| title | varchar(180) |  | non |  |
| due_date | date |  | oui |  |
| due_mileage | integer |  | oui |  |
| cost | numeric(18, 2) |  | non |  |
| status | varchar(20) |  | non |  |
| notes | text |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| supplier_id | uuid | FK | oui | erp_partner.id ; Django PROTECT |
| vehicle_id | uuid | FK | non | erp_vehicle.id ; Django PROTECT |

```sql
ALTER TABLE "erp_maintenance" ADD CONSTRAINT "erp_maintenance_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_maintenance" ADD CONSTRAINT "erp_tenant_fk_405b540608cffe80" FOREIGN KEY (organization_id,"supplier_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_maintenance" ADD CONSTRAINT "erp_tenant_fk_0b5dae13f848188e" FOREIGN KEY (organization_id,"vehicle_id") REFERENCES "erp_vehicle" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_membership - Adhésions et rôles

Groupe : Organisation

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| role | varchar(20) |  | non |  |
| active | boolean |  | non |  |
| created_at | timestamp with time zone |  | non |  |
| user_id | bigint | FK | non | comptes_utilisateur.id ; Django CASCADE |
| organization_id | uuid | FK | non | erp_organization.id ; Django CASCADE |

Contrainte : `erp_membership_unique` - <UniqueConstraint: fields=('organization', 'user') name='erp_membership_unique'>

## erp_mission - Missions

Groupe : Flotte et transport

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| origin | varchar(180) |  | non |  |
| destination | varchar(180) |  | non |  |
| departure | timestamp with time zone |  | non |  |
| arrival | timestamp with time zone |  | non |  |
| started_at | timestamp with time zone |  | oui |  |
| completed_at | timestamp with time zone |  | oui |  |
| status | varchar(20) |  | non |  |
| loaded_quantity | numeric(15, 3) |  | non |  |
| delivered_quantity | numeric(15, 3) |  | non |  |
| delivery_note | text |  | non |  |
| notes | text |  | non |  |
| driver_id | uuid | FK | non | erp_employee.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| route_id | uuid | FK | oui | erp_route.id ; Django PROTECT |
| order_id | uuid | FK | oui | erp_transportorder.id ; Django PROTECT |
| vehicle_id | uuid | FK | non | erp_vehicle.id ; Django PROTECT |

Contrainte : `erp_mission_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_mission_reference'>

Contrainte : `erp_one_active_vehicle` - <UniqueConstraint: fields=('vehicle',) name='erp_one_active_vehicle' condition=(AND: ('status', 'active'))>

Contrainte : `erp_one_active_driver` - <UniqueConstraint: fields=('driver',) name='erp_one_active_driver' condition=(AND: ('status', 'active'))>

Contrainte : `erp_mission_dates` - <CheckConstraint: condition=(AND: ('arrival__gt', F(departure))) name='erp_mission_dates'>

```sql
ALTER TABLE "erp_mission" ADD CONSTRAINT "erp_mission_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_mission" ADD CONSTRAINT "erp_tenant_fk_322736a5fe69fb11" FOREIGN KEY (organization_id,"driver_id") REFERENCES "erp_employee" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_mission" ADD CONSTRAINT "erp_tenant_fk_009eae43021b6621" FOREIGN KEY (organization_id,"route_id") REFERENCES "erp_route" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_mission" ADD CONSTRAINT "erp_tenant_fk_9cff329ce3a8731c" FOREIGN KEY (organization_id,"order_id") REFERENCES "erp_transportorder" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_mission" ADD CONSTRAINT "erp_tenant_fk_22abcf4c6a7a22f0" FOREIGN KEY (organization_id,"vehicle_id") REFERENCES "erp_vehicle" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_notificationread - Notifications lues

Groupe : Terrain et atelier

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| key | varchar(64) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| user_id | bigint | FK | non | comptes_utilisateur.id ; Django CASCADE |

Contrainte : `erp_notification_read_unique` - <UniqueConstraint: fields=('organization', 'user', 'key') name='erp_notification_read_unique'>

```sql
ALTER TABLE "erp_notificationread" ADD CONSTRAINT "erp_notificationread_tenant_identity" UNIQUE (organization_id,id);
```

## erp_organization - Entreprises

Groupe : Organisation

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| name | varchar(150) |  | non |  |
| slug | varchar(80) | UNIQUE | non |  |
| country | varchar(2) |  | non |  |
| currency | varchar(3) |  | non |  |
| timezone | varchar(60) |  | non |  |
| activities | jsonb |  | non |  |
| address | text |  | non |  |
| phone | varchar(40) |  | non |  |
| email | varchar(254) |  | non |  |
| registration | varchar(100) |  | non |  |
| tax_number | varchar(100) |  | non |  |
| created_at | timestamp with time zone |  | non |  |

## erp_partner - Partenaires

Groupe : Partenaires et ventes

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| name | varchar(150) |  | non |  |
| kind | varchar(15) |  | non |  |
| email | varchar(254) |  | non |  |
| phone | varchar(40) |  | non |  |
| address | text |  | non |  |
| tax_number | varchar(100) |  | non |  |
| payment_days | smallint |  | non |  |
| notes | text |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_partner" ADD CONSTRAINT "erp_partner_tenant_identity" UNIQUE (organization_id,id);
```

## erp_payment - Règlements clients

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| date | date |  | non |  |
| method | varchar(20) |  | non |  |
| reference | varchar(120) |  | non |  |
| invoice_id | uuid | FK | non | erp_invoice.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_payment_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_payment_reference'>

```sql
ALTER TABLE "erp_payment" ADD CONSTRAINT "erp_payment_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_payment" ADD CONSTRAINT "erp_tenant_fk_e3d2b764f5dd1545" FOREIGN KEY (organization_id,"invoice_id") REFERENCES "erp_invoice" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_portalaccess - Accès clients

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| active | boolean |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| partner_id | uuid | FK | non | erp_partner.id ; Django PROTECT |
| user_id | bigint | FK | non | comptes_utilisateur.id ; Django PROTECT |

Contrainte : `erp_portal_user_unique` - <UniqueConstraint: fields=('organization', 'user') name='erp_portal_user_unique'>

```sql
ALTER TABLE erp_portalaccess ADD CONSTRAINT erp_portalaccess_tenant_identity UNIQUE (organization_id,id);
```

```sql
ALTER TABLE erp_portalaccess ADD CONSTRAINT erp_portal_partner_tenant FOREIGN KEY (organization_id,partner_id) REFERENCES erp_partner (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_position - Positions

Groupe : Flotte et transport

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| timestamp | timestamp with time zone |  | non |  |
| latitude | numeric(9, 6) |  | non |  |
| longitude | numeric(9, 6) |  | non |  |
| mission_id | uuid | FK | non | erp_mission.id ; Django CASCADE |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_position_once` - <UniqueConstraint: fields=('mission', 'timestamp') name='erp_position_once'>

```sql
ALTER TABLE "erp_position" ADD CONSTRAINT "erp_position_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_position" ADD CONSTRAINT "erp_tenant_fk_b9998ab15391d4e3" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_pricingrule - Règles tarifaires

Groupe : Partenaires et ventes

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| name | varchar(120) |  | non |  |
| activity | varchar(20) |  | non |  |
| origin | varchar(180) |  | non |  |
| destination | varchar(180) |  | non |  |
| unit | varchar(15) |  | non |  |
| unit_price | numeric(18, 2) |  | non |  |
| minimum | numeric(18, 2) |  | non |  |
| valid_from | date |  | non |  |
| valid_until | date |  | non |  |
| active | boolean |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_pricingrule" ADD CONSTRAINT "erp_pricingrule_tenant_identity" UNIQUE (organization_id,id);
```

## erp_purchase - Achats

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| date | date |  | non |  |
| lines | jsonb |  | non |  |
| total | numeric(18, 2) |  | non |  |
| status | varchar(20) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| supplier_id | uuid | FK | non | erp_partner.id ; Django PROTECT |

Contrainte : `erp_purchase_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_purchase_reference'>

```sql
ALTER TABLE "erp_purchase" ADD CONSTRAINT "erp_purchase_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_purchase" ADD CONSTRAINT "erp_tenant_fk_304f1c2d4b51fa44" FOREIGN KEY (organization_id,"supplier_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_route - Lignes et itinéraires

Groupe : Flotte et transport

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| name | varchar(150) |  | non |  |
| origin | varchar(180) |  | non |  |
| destination | varchar(180) |  | non |  |
| activity | varchar(20) |  | non |  |
| fare | numeric(18, 2) |  | non |  |
| stops | text |  | non |  |
| active | boolean |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

```sql
ALTER TABLE "erp_route" ADD CONSTRAINT "erp_route_tenant_identity" UNIQUE (organization_id,id);
```

## erp_sequence - Séquences

Groupe : Applications et documents

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| key | varchar(30) |  | non |  |
| value | integer |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_sequence_key` - <UniqueConstraint: fields=('organization', 'key') name='erp_sequence_key'>

```sql
ALTER TABLE "erp_sequence" ADD CONSTRAINT "erp_sequence_tenant_identity" UNIQUE (organization_id,id);
```

## erp_stockitem - Articles de stock

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| code | varchar(80) |  | non |  |
| name | varchar(150) |  | non |  |
| unit | varchar(20) |  | non |  |
| quantity | numeric(15, 3) |  | non |  |
| minimum | numeric(15, 3) |  | non |  |
| unit_cost | numeric(18, 2) |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_stock_code` - <UniqueConstraint: fields=('organization', 'code') name='erp_stock_code'>

Contrainte : `erp_stock_nonnegative` - <CheckConstraint: condition=(AND: ('quantity__gte', 0)) name='erp_stock_nonnegative'>

```sql
ALTER TABLE "erp_stockitem" ADD CONSTRAINT "erp_stockitem_tenant_identity" UNIQUE (organization_id,id);
```

## erp_stockmovement - Mouvements de stock

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| quantity | numeric(15, 3) |  | non |  |
| reason | varchar(180) |  | non |  |
| reference | varchar(100) |  | non |  |
| item_id | uuid | FK | non | erp_stockitem.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_stock_movement_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_stock_movement_reference'>

```sql
ALTER TABLE "erp_stockmovement" ADD CONSTRAINT "erp_stockmovement_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_stockmovement" ADD CONSTRAINT "erp_tenant_fk_27cba4b13acfbed0" FOREIGN KEY (organization_id,"item_id") REFERENCES "erp_stockitem" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_subcontract - Sous-traitance

Groupe : Partenaires et ventes

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| agreed_amount | numeric(18, 2) |  | non |  |
| due_date | date |  | non |  |
| conditions | text |  | non |  |
| external_vehicle | varchar(100) |  | non |  |
| external_driver | varchar(150) |  | non |  |
| completion_note | text |  | non |  |
| status | varchar(15) |  | non |  |
| mission_id | uuid | FK | non | erp_mission.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| supplier_id | uuid | FK | non | erp_partner.id ; Django PROTECT |

Contrainte : `erp_subcontract_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_subcontract_reference'>

```sql
ALTER TABLE "erp_subcontract" ADD CONSTRAINT "erp_subcontract_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_subcontract" ADD CONSTRAINT "erp_tenant_fk_0fc81a0c78c6904d" FOREIGN KEY (organization_id,"mission_id") REFERENCES "erp_mission" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_subcontract" ADD CONSTRAINT "erp_tenant_fk_d1c6cc719c4aaa9c" FOREIGN KEY (organization_id,"supplier_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_supplierbill - Factures fournisseurs

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(100) |  | non |  |
| date | date |  | non |  |
| due_date | date |  | non |  |
| lines | jsonb |  | non |  |
| subtotal | numeric(18, 2) |  | non |  |
| tax | numeric(18, 2) |  | non |  |
| total | numeric(18, 2) |  | non |  |
| paid | numeric(18, 2) |  | non |  |
| status | varchar(15) |  | non |  |
| notes | text |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| purchase_id | uuid | FK | oui | erp_purchase.id ; Django PROTECT |
| subcontract_id | uuid | FK | oui | erp_subcontract.id ; Django PROTECT |
| supplier_id | uuid | FK | non | erp_partner.id ; Django PROTECT |

Contrainte : `erp_supplier_bill_reference` - <UniqueConstraint: fields=('organization', 'supplier', 'reference') name='erp_supplier_bill_reference'>

Contrainte : `erp_one_bill_per_purchase` - <UniqueConstraint: fields=('purchase',) name='erp_one_bill_per_purchase' condition=(AND: ('purchase__isnull', False), (NOT (AND: ('status', 'cancelled'))))>

Contrainte : `erp_one_bill_per_subcontract` - <UniqueConstraint: fields=('subcontract',) name='erp_one_bill_per_subcontract' condition=(AND: ('subcontract__isnull', False), (NOT (AND: ('status', 'cancelled'))))>

```sql
ALTER TABLE "erp_supplierbill" ADD CONSTRAINT "erp_supplierbill_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_supplierbill" ADD CONSTRAINT "erp_tenant_fk_32fb2abfc36c8fe5" FOREIGN KEY (organization_id,"purchase_id") REFERENCES "erp_purchase" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_supplierbill" ADD CONSTRAINT "erp_tenant_fk_d82524310add43c3" FOREIGN KEY (organization_id,"subcontract_id") REFERENCES "erp_subcontract" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

```sql
ALTER TABLE "erp_supplierbill" ADD CONSTRAINT "erp_tenant_fk_7c95bda4f1dcf454" FOREIGN KEY (organization_id,"supplier_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_supplierpayment - Règlements fournisseurs

Groupe : Finance et achats

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(100) |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| date | date |  | non |  |
| method | varchar(20) |  | non |  |
| bill_id | uuid | FK | non | erp_supplierbill.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_supplier_payment_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_supplier_payment_reference'>

```sql
ALTER TABLE "erp_supplierpayment" ADD CONSTRAINT "erp_supplierpayment_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_supplierpayment" ADD CONSTRAINT "erp_tenant_fk_369d860d9b66c2b5" FOREIGN KEY (organization_id,"bill_id") REFERENCES "erp_supplierbill" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_teaminvitation - Invitations

Groupe : Organisation

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| email | varchar(254) |  | non |  |
| role | varchar(20) |  | non |  |
| digest | varchar(64) | UNIQUE | non |  |
| expires_at | timestamp with time zone |  | non |  |
| used_at | timestamp with time zone |  | oui |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |
| partner_id | uuid | FK | oui | erp_partner.id ; Django PROTECT |

```sql
ALTER TABLE "erp_teaminvitation" ADD CONSTRAINT "erp_teaminvitation_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE erp_teaminvitation ADD CONSTRAINT erp_invite_partner_tenant FOREIGN KEY (organization_id,partner_id) REFERENCES erp_partner (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_transportcontract - Contrats de transport

Groupe : Partenaires et ventes

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| activity | varchar(20) |  | non |  |
| origin | varchar(180) |  | non |  |
| destination | varchar(180) |  | non |  |
| description | text |  | non |  |
| quantity | numeric(15, 3) |  | non |  |
| unit | varchar(15) |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| start_date | date |  | non |  |
| end_date | date |  | non |  |
| recurrence | varchar(12) |  | non |  |
| next_date | date |  | oui |  |
| status | varchar(15) |  | non |  |
| customer_id | uuid | FK | non | erp_partner.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_contract_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_contract_reference'>

```sql
ALTER TABLE "erp_transportcontract" ADD CONSTRAINT "erp_transportcontract_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_transportcontract" ADD CONSTRAINT "erp_tenant_fk_48c4eba959094d8a" FOREIGN KEY (organization_id,"customer_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_transportorder - Commandes de transport

Groupe : Partenaires et ventes

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| reference | varchar(80) |  | non |  |
| activity | varchar(20) |  | non |  |
| origin | varchar(180) |  | non |  |
| destination | varchar(180) |  | non |  |
| product | varchar(180) |  | non |  |
| quantity | numeric(15, 3) |  | non |  |
| unit | varchar(15) |  | non |  |
| amount | numeric(18, 2) |  | non |  |
| planned_date | date |  | non |  |
| status | varchar(20) |  | non |  |
| notes | text |  | non |  |
| customer_id | uuid | FK | non | erp_partner.id ; Django PROTECT |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_order_reference` - <UniqueConstraint: fields=('organization', 'reference') name='erp_order_reference'>

```sql
ALTER TABLE "erp_transportorder" ADD CONSTRAINT "erp_transportorder_tenant_identity" UNIQUE (organization_id,id);
```

```sql
ALTER TABLE "erp_transportorder" ADD CONSTRAINT "erp_tenant_fk_05d87333f194a650" FOREIGN KEY (organization_id,"customer_id") REFERENCES "erp_partner" (organization_id,id) DEFERRABLE INITIALLY IMMEDIATE;
```

## erp_vehicle - Véhicules

Groupe : Flotte et transport

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | uuid | PK | non |  |
| created_at | timestamp with time zone |  | non |  |
| updated_at | timestamp with time zone |  | non |  |
| plate | varchar(40) |  | non |  |
| name | varchar(120) |  | non |  |
| kind | varchar(20) |  | non |  |
| status | varchar(20) |  | non |  |
| capacity | numeric(12, 3) |  | non |  |
| capacity_unit | varchar(10) |  | non |  |
| seats | smallint |  | non |  |
| mileage | integer |  | non |  |
| insurance_expiry | date |  | oui |  |
| inspection_expiry | date |  | oui |  |
| compartments | jsonb |  | non |  |
| organization_id | uuid | FK | non | erp_organization.id ; Django PROTECT |

Contrainte : `erp_vehicle_plate_tenant` - <UniqueConstraint: fields=('organization', 'plate') name='erp_vehicle_plate_tenant'>

```sql
ALTER TABLE "erp_vehicle" ADD CONSTRAINT "erp_vehicle_tenant_identity" UNIQUE (organization_id,id);
```

## fleet_relevekilometrage - releve kilometrages

Groupe : Historique / fleet

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| kilometrage | integer |  | non |  |
| source | varchar(20) |  | non |  |
| note | varchar(255) |  | non |  |
| releve_le | timestamp with time zone |  | non |  |
| auteur_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| vehicule_id | bigint | FK | non | fleet_vehicule.id ; Django CASCADE |

## fleet_vehicule - vehicules

Groupe : Historique / fleet

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| plaque | varchar(20) | UNIQUE | non |  |
| modele | varchar(100) |  | non |  |
| annee | smallint |  | oui |  |
| kilometrage | integer |  | non |  |
| mise_en_service | date |  | oui |  |
| numero_serie | varchar(17) |  | non |  |
| statut | varchar(20) |  | non |  |

## maintenance_incident - Incidents

Groupe : Historique / maintenance

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| type | varchar(20) |  | non |  |
| titre | varchar(150) |  | non |  |
| description | text |  | non |  |
| lieu | varchar(150) |  | non |  |
| date | date |  | non |  |
| heure | varchar(5) |  | non |  |
| statut | varchar(20) |  | non |  |
| chauffeur_id | bigint | FK | non | drivers_chauffeur.id ; Django CASCADE |
| trajet_id | bigint | FK | oui | dispatch_trajet.id ; Django SET_NULL |

## paie_bulletinpaie - bulletin paies

Groupe : Historique / paie

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| mode | varchar(10) |  | non |  |
| nombre_trajets | integer |  | non |  |
| heures_regulieres | numeric(7, 2) |  | non |  |
| heures_sup | numeric(7, 2) |  | non |  |
| brut | numeric(10, 2) |  | non |  |
| brut_imposable | numeric(10, 2) |  | non |  |
| retenues | numeric(10, 2) |  | non |  |
| net | numeric(10, 2) |  | non |  |
| cotisations_employeur | numeric(10, 2) |  | non |  |
| chauffeur_id | bigint | FK | non | drivers_chauffeur.id ; Django PROTECT |
| periode_id | bigint | FK | non | paie_periodepaie.id ; Django CASCADE |

Contrainte : `un_bulletin_par_periode` - <UniqueConstraint: fields=('periode', 'chauffeur') name='un_bulletin_par_periode'>

## paie_lignebulletin - ligne bulletins

Groupe : Historique / paie

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| genre | varchar(10) |  | non |  |
| code | varchar(20) |  | non |  |
| libelle | varchar(150) |  | non |  |
| quantite | numeric(9, 2) |  | oui |  |
| taux | numeric(10, 3) |  | oui |  |
| montant | numeric(10, 2) |  | non |  |
| imposable | boolean |  | non |  |
| manuelle | boolean |  | non |  |
| ordre | smallint |  | non |  |
| bulletin_id | bigint | FK | non | paie_bulletinpaie.id ; Django CASCADE |

## paie_parametrespaie - parametres paies

Groupe : Historique / paie

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| frequence | varchar(20) |  | non |  |
| seuil_heures_sup | numeric(5, 2) |  | non |  |
| majoration_heures_sup | numeric(4, 2) |  | non |  |
| taux_vacances | numeric(5, 2) |  | non |  |

## paie_periodepaie - periode paies

Groupe : Historique / paie

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| debut | date |  | non |  |
| fin | date |  | non |  |
| date_paiement | date |  | non |  |
| statut | varchar(10) |  | non |  |
| calculee_le | timestamp with time zone |  | oui |  |
| cree_le | timestamp with time zone |  | non |  |

## paie_profilpaie - profil paies

Groupe : Historique / paie

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| mode | varchar(10) |  | non |  |
| taux_horaire | numeric(8, 2) |  | non |  |
| taux_trajet | numeric(8, 2) |  | non |  |
| salaire_periode | numeric(10, 2) |  | non |  |
| actif | boolean |  | non |  |
| chauffeur_id | bigint | FK, UNIQUE | non | drivers_chauffeur.id ; Django CASCADE |

## paie_retenue - retenues

Groupe : Historique / paie

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| code | varchar(20) | UNIQUE | non |  |
| libelle | varchar(120) |  | non |  |
| taux_salarie | numeric(6, 3) |  | non |  |
| taux_employeur | numeric(6, 3) |  | non |  |
| plancher_annuel | numeric(10, 2) |  | non |  |
| plafond_annuel | numeric(10, 2) |  | oui |  |
| exemption_annuelle | numeric(10, 2) |  | non |  |
| note | varchar(255) |  | non |  |
| actif | boolean |  | non |  |
| ordre | smallint |  | non |  |

## societe_entreprise - Entreprises

Groupe : Historique / societe

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| nom | varchar(150) |  | non |  |
| courriel | varchar(254) |  | non |  |
| telephone | varchar(30) |  | non |  |
| adresse | varchar(255) |  | non |  |
| ville | varchar(100) |  | non |  |
| province | varchar(50) |  | non |  |
| code_postal | varchar(10) |  | non |  |
| neq | varchar(20) |  | non |  |
| module_entretien | boolean |  | non |  |
| module_suivi | boolean |  | non |  |
| module_paie | boolean |  | non |  |
| portail_trajets | boolean |  | non |  |
| portail_incidents | boolean |  | non |  |
| portail_vehicule | boolean |  | non |  |
| portail_paie | boolean |  | non |  |
| portail_profil | boolean |  | non |  |
| modifie_le | timestamp with time zone |  | non |  |

## suivi_positiongps - position gpss

Groupe : Historique / suivi

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| plaque | varchar(20) |  | non |  |
| latitude | numeric(9, 6) |  | non |  |
| longitude | numeric(9, 6) |  | non |  |
| precision_m | double precision |  | oui |  |
| vitesse_kmh | double precision |  | oui |  |
| cap | double precision |  | oui |  |
| horodatage | timestamp with time zone |  | non |  |
| recu_le | timestamp with time zone |  | non |  |
| chauffeur_id | bigint | FK | non | drivers_chauffeur.id ; Django CASCADE |
| trajet_id | bigint | FK | non | dispatch_trajet.id ; Django CASCADE |

Contrainte : `position_unique_par_instant` - <UniqueConstraint: fields=('trajet', 'horodatage') name='position_unique_par_instant'>

## token_blacklist_blacklistedtoken - Blacklisted Tokens

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| blacklisted_at | timestamp with time zone |  | non |  |
| token_id | bigint | FK, UNIQUE | non | token_blacklist_outstandingtoken.id ; Django CASCADE |

## token_blacklist_outstandingtoken - Outstanding Tokens

Groupe : Identité et système

| Colonne | Type PostgreSQL | Clé | NULL | Référence |
|---|---|---|---|---|
| id | bigint | PK | non |  |
| token | text |  | non |  |
| created_at | timestamp with time zone |  | oui |  |
| expires_at | timestamp with time zone |  | non |  |
| user_id | bigint | FK | oui | comptes_utilisateur.id ; Django SET_NULL |
| jti | varchar(255) | UNIQUE | non |  |
