# Phase 2

La phase 2 prolonge le MVP par increments installables. Les integrations externes restent
optionnelles, desactivees par defaut et sans contenu sensible.

## Lot 7 - Notifications internes

- rappels de taches en retard ou arrivant a echeance sous 48 heures ;
- transmissions importantes ou urgentes non lues ;
- compteur personnel, lecture et masquage ;
- calcul a la demande dans le perimetre courant, sans copie du contenu metier ;
- aucun email, service cloud ou notification tierce.

## Lot 9 - Planning d'equipe

- presences et absences generiques par unite ;
- vue hebdomadaire accessible a l'equipe ;
- gestion reservee au chef de service et a l'administrateur ;
- refus des chevauchements et des periodes superieures a sept jours ;
- aucune donnee medicale ou motif RH detaille.

## Lot 10 - Indicateurs agreges de pilotage

- synthese sur 7, 30 ou 90 jours dans les unites autorisees ;
- volumes de transmissions et de taches, urgences, retards et taux de realisation ;
- acces reserve au chef de service et a l'administrateur ;
- aucun contenu metier, nom de professionnel ou classement individuel ;
- calcul local a la demande, sans telemetrie externe.

## Lot 11 - Pieces jointes securisees

- ajout sur un brouillon par son auteur, dans son perimetre autorise ;
- PDF, JPEG et PNG limites a 5 Mo avec verification de signature ;
- analyse obligatoire par ClamAV local avant conservation ;
- empreinte SHA-256, telechargements et suppressions audites ;
- stockage transactionnel dans PostgreSQL et aucune URL publique.

## Lot 12 - Integrations locales optionnelles

- connecteurs HTTP locaux generiques, desactives par defaut ;
- destinations bornees par une liste blanche d'hotes configuree au deploiement ;
- test manuel avec message versionne sans donnee metier ni identifiant de personne ;
- administration reservee et actions auditees ;
- activation des flux metier differee jusqu'a validation du format et du systeme cible.

## Lots proposes ensuite

| Lot | Perimetre | Prealable |
|---|---|---|
| 8 | Gestion avancee des comptes et rattachements dans l'application | gouvernance Keycloak |

L'ordre peut etre ajuste par l'organisme. Les pieces jointes et integrations ne doivent pas etre
activees sans mise a jour du modele de menaces et de l'AIPD.
