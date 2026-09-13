"""TransitFlow — donnees de depart (equivalent de TF_SEED cote client)"""

SEED = {
    'chauffeurs': [
        {
            'id': 'c1',
            'prenom': 'Aminata',
            'nom': 'Diallo',
            'age': 34,
            'telephone': '819-555-0142',
            'courriel': 'a.diallo@transitflow.ca',
            'adresse': '12 rue King Ouest, Sherbrooke, QC',
            'permisNumero': 'D1234-560912-01',
            'permisExpiration': '2027-03-15',
            'statut': 'disponible',
            'plaqueHabituelle': 'F7X 213',
            'creeLe': '2025-01-10'
        },
        {
            'id': 'c2',
            'prenom': 'Moussa',
            'nom': 'Traore',
            'age': 41,
            'telephone': '819-555-0198',
            'courriel': 'm.traore@transitflow.ca',
            'adresse': '45 rue Belvedere Sud, Sherbrooke, QC',
            'permisNumero': 'D2210-411204-02',
            'permisExpiration': '2026-10-05',
            'statut': 'en-trajet',
            'plaqueHabituelle': 'K2B 884',
            'creeLe': '2025-02-18'
        },
        {
            'id': 'c3',
            'prenom': 'Sophie',
            'nom': 'Fortin',
            'age': 29,
            'telephone': '819-555-0223',
            'courriel': 's.fortin@transitflow.ca',
            'adresse': '78 rue Galt Ouest, Sherbrooke, QC',
            'permisNumero': 'D3305-970622-03',
            'permisExpiration': '2028-06-30',
            'statut': 'disponible',
            'plaqueHabituelle': 'L9M 356',
            'creeLe': '2025-03-02'
        },
        {
            'id': 'c4',
            'prenom': 'Mamadou',
            'nom': 'Barry',
            'age': 26,
            'telephone': '819-555-0261',
            'courriel': 'm.barry@transitflow.ca',
            'adresse': '300 rue Alexandre, Sherbrooke, QC',
            'permisNumero': 'D4090-000715-04',
            'permisExpiration': '2027-01-20',
            'statut': 'hors-service',
            'plaqueHabituelle': 'R4P 902',
            'creeLe': '2025-04-22'
        }
    ],

    'vehicules': [
        {'plaque': 'F7X 213', 'modele': 'Ford Transit 2023'},
        {'plaque': 'K2B 884', 'modele': 'Mercedes Sprinter 2022'},
        {'plaque': 'L9M 356', 'modele': 'Ford Transit 2021'},
        {'plaque': 'R4P 902', 'modele': 'Dodge Grand Caravan 2020'}
    ],

    'trajets': [
        {
            'id': 'T-2091',
            'chauffeurId': 'c2',
            'plaque': 'K2B 884',
            'depart': 'Sherbrooke',
            'departAdresse': 'Terminus Sherbrooke, 20 rue King Ouest',
            'arrivee': 'Magog',
            'debut': '2026-09-12T07:30',
            'finPrevue': '2026-09-12T08:45',
            'fin': None,
            'statut': 'en-cours',
            'arrets': [
                {'lieu': 'Rock Forest', 'heure': '07:52', 'note': 'Arret regulier'}
            ]
        },
        {
            'id': 'T-2092',
            'chauffeurId': 'c1',
            'plaque': 'F7X 213',
            'depart': 'Sherbrooke',
            'departAdresse': 'Terminus Sherbrooke, 20 rue King Ouest',
            'arrivee': 'Coaticook',
            'debut': '2026-09-11T14:00',
            'finPrevue': '2026-09-11T15:20',
            'fin': '2026-09-11T15:24',
            'statut': 'termine',
            'arrets': [
                {'lieu': 'Waterville', 'heure': '14:35', 'note': 'Arret regulier'}
            ]
        },
        {
            'id': 'T-2093',
            'chauffeurId': 'c3',
            'plaque': 'L9M 356',
            'depart': 'Sherbrooke',
            'departAdresse': 'Terminus Sherbrooke, 20 rue King Ouest',
            'arrivee': 'Granby',
            'debut': '2026-09-10T09:00',
            'finPrevue': '2026-09-10T10:30',
            'fin': '2026-09-10T10:28',
            'statut': 'termine',
            'arrets': []
        }
    ],

    'incidents': [
        {
            'id': 'I-1',
            'trajetId': 'T-2091',
            'chauffeurId': 'c2',
            'type': 'technique',
            'titre': 'Voyant moteur allume',
            'description': 'Le voyant moteur s est allume pendant le trajet, vehicule ramene au garage apres l arrivee.',
            'lieu': 'Route 220, Rock Forest',
            'date': '2026-09-12',
            'heure': '07:55',
            'statut': 'ouvert'
        },
        {
            'id': 'I-2',
            'trajetId': 'T-2093',
            'chauffeurId': 'c3',
            'type': 'route',
            'titre': 'Route fermee pour travaux',
            'description': 'Deviation necessaire en raison de travaux routiers sur le trajet prevu.',
            'lieu': 'Sortie 68, autoroute 10',
            'date': '2026-09-10',
            'heure': '09:20',
            'statut': 'traite'
        }
    ]
}
