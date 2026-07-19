# Matrice des habilitations

## 1. Rôles de référence

| Code | Rôle | Périmètre habituel | Accès au contenu métier |
|---|---|---|---|
| `professional` | Professionnel | Une ou plusieurs unités | Oui, dans ses unités actives |
| `team_manager` | Responsable d'équipe | Unités supervisées | Oui, avec actions de coordination |
| `establishment_admin` | Administrateur d'établissement | Établissement | Non par défaut |
| `organization_admin` | Administrateur d'organisation | Organisation | Non par défaut |
| `auditor` | Auditeur/conformité | Organisation ou établissement | Métadonnées d'audit ; contenu sur permission séparée |
| `technical_operator` | Exploitant technique | Installation | Aucun accès applicatif métier |

Un même utilisateur MAY cumuler des rôles, mais chaque attribution est datée et limitée à un périmètre. Les cumuls `technical_operator` + rôle métier ou `auditor` + administrateur d'habilitations SHOULD déclencher un avertissement et une revue.

## 2. Actions

Légende : `✓` accord de référence dans le périmètre, `C` accord conditionnel, `—` refus par défaut.

| Ressource / action | Professionnel | Responsable | Admin établissement | Admin organisation | Auditeur | Exploitant |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Structure : lire | ✓ | ✓ | ✓ | ✓ | C | — |
| Structure : créer/modifier/désactiver | — | — | ✓ | ✓ | — | — |
| Compte : lire le profil minimal | C | C | ✓ | ✓ | C | — |
| Rattachement : gérer | — | — | ✓ | ✓ | — | — |
| Rôle : attribuer dans son périmètre | — | — | C | ✓ | — | — |
| Personne active : rechercher/lire | ✓ | ✓ | — | — | — | — |
| Personne : créer/modifier | C | ✓ | — | — | — | — |
| Personne : archiver | — | ✓ | — | — | — | — |
| Personne archivée : lire | C | ✓ | — | — | C | — |
| Transmission : lire | ✓ | ✓ | — | — | — | — |
| Transmission : brouillon/créer/publier | ✓ | ✓ | — | — | — | — |
| Transmission : corriger sa publication | C | ✓ | — | — | — | — |
| Accusé : créer pour soi | ✓ | ✓ | — | — | — | — |
| Accusés : voir agrégat | C | ✓ | — | — | C | — |
| Accusés : voir nominatif | — | ✓ | — | — | C | — |
| Tâche : créer/mettre à jour | ✓ | ✓ | — | — | — | — |
| Tâche : réattribuer hors de soi | C | ✓ | — | — | — | — |
| Relève : lire/participer | ✓ | ✓ | — | — | — | — |
| Relève : créer/clôturer/rouvrir | — | ✓ | — | — | — | — |
| Référentiels métier : gérer | — | C | ✓ | ✓ | — | — |
| Audit : rechercher/lire | — | — | — | C | ✓ | — |
| Audit : vérifier/exporter | — | — | — | C | ✓ | — |
| Export métier | — | C | — | — | C | — |
| Politique de conservation : gérer | — | — | — | C | C | — |
| Opération technique de sauvegarde | — | — | — | — | — | ✓ |

## 3. Conditions de périmètre

### Ressource d'unité

Un utilisateur métier peut agir si :

1. son compte est actif ;
2. une attribution de rôle active donne l'action ;
3. son rattachement actif couvre l'unité ou un ancêtre autorisé ;
4. la ressource appartient à la même organisation ;
5. aucune règle métier supplémentaire ne refuse l'action.

### Personne active

La lecture courante requiert une `person_assignment` active vers une unité couverte. Un professionnel ne conserve pas automatiquement l'accès après transfert. Une lecture historique utilise `archive.read` ou `history.read`, un motif et un audit renforcé.

### Transmission

- Lire : accès à la personne et à l'unité capturée par la transmission.
- Publier : accès actif à la personne et permission `transmission.publish`.
- Corriger : auteur dans une fenêtre `PILOTE`, ou responsable ; motif obligatoire.
- Accuser : droit de lecture de la version au moment de l'action.

### Tâche

Le créateur ne peut assigner qu'un utilisateur actif rattaché au périmètre, ou l'unité elle-même. La clôture est permise à l'assigné actif, au créateur si encore habilité, ou au responsable.

## 4. Permissions atomiques initiales

```text
organization.read
structure.read, structure.manage
user.read_minimal, membership.manage
role.read, role.assign, role.manage
person.search, person.read, person.create, person.update, person.archive
person.history.read, person.archive.read
transmission.read, transmission.create, transmission.publish, transmission.correct
acknowledgement.create_self, acknowledgement.read_aggregate, acknowledgement.read_named
task.read, task.create, task.update, task.assign, task.cancel
handover.read, handover.create, handover.update, handover.close, handover.reopen
taxonomy.read, taxonomy.manage
audit.read, audit.verify, audit.export
retention.read, retention.manage, archive.execute
export.request, export.download
```

## 5. Algorithme de décision

```text
authorize(actor, action, resource):
  refuser si acteur absent ou compte inactif
  charger les attributions actives à l'instant serveur
  refuser si aucune attribution ne donne action
  calculer les périmètres couverts sans donnée fournie par le client
  refuser si l'organisation ou le périmètre de resource n'est pas couvert
  appliquer la règle métier spécifique
  auditer les refus sensibles et les accès désignés
  autoriser
```

Les méthodes de liste reçoivent un `SecurityContext` et construisent un prédicat SQL. Elles ne chargent jamais toutes les lignes avant filtrage.

## 6. Cas de tests obligatoires

- Même rôle, autre unité du même service : refus sauf portée de service explicite.
- Même rôle, autre établissement : refus.
- UUID valide d'une ressource invisible : même statut et même forme d'erreur qu'un UUID inconnu.
- Rattachement expiré pendant une session : refus à la requête suivante.
- Compte désactivé avec session et jeton encore valides : refus.
- Administrateur de structure sans rôle métier : aucune lecture de personne ou transmission.
- Auditeur sans permission de contenu : aucune restitution du corps métier.
- Liste, compteur, recherche et export : aucun élément ou total hors périmètre.
- Attribution d'un rôle plus large que le périmètre de l'administrateur : refus.
- Tâche assignée à un utilisateur hors unité : refus transactionnel.
