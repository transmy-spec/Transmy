# Modèle de données proposé

## 1. Principes

- PostgreSQL est la source de vérité.
- Toutes les clés primaires sont des UUID générés côté serveur.
- Les dates sont stockées en `timestamptz` en UTC et affichées dans le fuseau de l'utilisateur ou de l'établissement.
- Les objets métier portent un périmètre explicite et ne déduisent pas leur sécurité d'un paramètre fourni par le client.
- Les suppressions physiques sont exceptionnelles ; les objets structurants sont désactivés et les objets sensibles archivés selon une politique de conservation.
- Les données d'identité Keycloak et les habilitations métier restent séparées.
- Les écritures métier importantes et leur événement d'audit sont enregistrés dans une même transaction.
- Le contenu libre n'est pas recopié dans l'audit, les notifications ou la relève.

## 2. Vue conceptuelle

```text
Organisation
 └─ Établissement
     └─ Service
         └─ Unité
             ├─ Rattachement utilisateur ─ Utilisateur ─ Attribution de rôle ─ Rôle
             └─ Séjour/Affectation ─ Personne accompagnée
                                      ├─ Transmission ─ Version ─ Accusé de lecture
                                      │                └─ Catégorie / Importance
                                      └─ Tâche ─ Historique / Attribution

Relève ─ Élément de relève ─ Transmission ou Tâche
Événement d'audit ─ acteur / cible / périmètre / chaîne d'intégrité
Politique de conservation ─ type de données / périmètre
Opération d'archivage ou d'export ─ demandeur / motif / état
```

## 3. Entités

### Structure et identité

#### `organization`

- `id`, `name`, `slug`
- `status` (`active`, `inactive`)
- `created_at`, `updated_at`

Une instance peut initialement héberger une organisation. La présence de cette table préserve l'évolution vers plusieurs organisations sans supposer une mutualisation SaaS.

#### `establishment`

- `id`, `organization_id`, `name`, `code`
- `timezone`, `status`
- `created_at`, `updated_at`, `version`

Contrainte : `code` unique au sein de l'organisation.

#### `service`

- `id`, `establishment_id`, `name`, `code`, `status`
- `created_at`, `updated_at`, `version`

#### `unit`

- `id`, `service_id`, `name`, `code`, `status`
- `created_at`, `updated_at`, `version`

La hiérarchie établissement → service → unité est stricte dans le MVP. Une évolution vers une organisation matricielle nécessitera une nouvelle décision d'architecture.

#### `user_account`

- `id`
- `oidc_issuer`, `oidc_subject`
- `display_name`, `email` facultatif
- `status` (`invited`, `active`, `disabled`)
- `last_login_at`, `created_at`, `updated_at`, `version`

Contrainte unique : (`oidc_issuer`, `oidc_subject`). Aucun mot de passe n'est stocké par l'application.

#### `user_membership`

- `id`, `user_id`
- `scope_type`, `scope_id`
- `starts_at`, `ends_at`, `status`
- `created_by`, `created_at`

Le polymorphisme de périmètre peut être implémenté par colonnes dédiées ou tables séparées afin de conserver de vraies clés étrangères ; cette seconde option est recommandée si la hiérarchie reste fixe.

#### `role`

- `id`, `organization_id` facultatif pour les rôles système
- `code`, `name`, `description`, `is_system`, `status`

#### `permission`

- `id`, `code`, `resource_type`, `action`, `description`

Exemples : `transmission.read`, `transmission.publish`, `audit.read`, `archive.read`, `authorization.manage`.

#### `role_permission`

- `role_id`, `permission_id`

#### `role_assignment`

- `id`, `user_id`, `role_id`
- `scope_type`, `scope_id`
- `starts_at`, `ends_at`
- `granted_by`, `granted_at`, `revoked_by`, `revoked_at`

Les permissions effectives sont l'intersection de l'état du compte, de la période, du rôle, de l'action et du périmètre de la ressource.

### Personnes accompagnées

#### `supported_person`

- `id`, `organization_id`
- `internal_reference` ou identifiant local non signifiant
- `family_name`, `given_name`, `preferred_name`
- `birth_date` facultative ou partielle selon besoin validé
- `status` (`active`, `archived`)
- `archived_at`, `archived_by`, `archive_reason`
- `created_at`, `updated_at`, `version`

Les champs exacts d'identification et les discriminants d'homonymie nécessitent une validation métier et une minimisation RGPD.

#### `person_assignment`

- `id`, `person_id`, `unit_id`
- `starts_at`, `ends_at`
- `is_primary`
- `created_by`, `created_at`, `version`

Cette table représente une prise en charge ou affectation datée. Une contrainte métier détermine si plusieurs affectations simultanées sont autorisées.

### Référentiels métier

#### `transmission_category`

- `id`, `organization_id` ou `establishment_id`
- `code`, `label`, `description`, `color` facultative, `sort_order`
- `status`, `created_at`, `updated_at`, `version`

#### `importance_level`

- `id`, `organization_id` facultatif
- `code`, `label`, `rank`, `requires_acknowledgement`, `status`

Le rang permet l'ordre sans coder la logique sur un libellé. Un socle possible : normal, important, urgent, à valider avec les utilisateurs.

### Transmissions et lecture

#### `transmission`

- `id`, `organization_id`, `unit_id`, `person_id`
- `category_id`, `importance_level_id`
- `status` (`draft`, `published`, `corrected`, `archived`)
- `author_id`, `published_at`
- `current_version_id`
- `selected_for_handover`
- `created_at`, `updated_at`, `version`

`unit_id` capture le périmètre au moment de la publication. Après un changement d'unité, l'accès courant suit l'affectation active ; l'accès historique requiert une permission explicite.

#### `transmission_version`

- `id`, `transmission_id`, `version_number`
- `content` en texte brut ou format riche strictement limité
- `change_reason`, `created_by`, `created_at`
- `previous_version_id`
- `content_hash`

Contrainte unique : (`transmission_id`, `version_number`). Une version publiée est non modifiable via l'application.

#### `transmission_acknowledgement`

- `id`, `transmission_id`, `transmission_version_id`, `user_id`
- `acknowledged_at`
- `context_scope_id` facultatif

Contrainte unique recommandée : (`transmission_version_id`, `user_id`). L'accusé prouve l'action dans l'application, pas la compréhension du contenu.

#### `transmission_recipient`

- `id`, `transmission_id`
- `recipient_type` (`user`, `role`, `unit`)
- référence de destinataire
- `created_at`

Cette entité est utile si l'accusé est requis pour une population déterminée. Son inclusion dans le MVP dépend de la décision sur les destinataires.

### Tâches

#### `task`

- `id`, `organization_id`, `unit_id`
- `person_id` facultatif, `transmission_id` facultatif
- `title`, `description` facultative
- `status` (`todo`, `in_progress`, `done`, `cancelled`)
- `due_at`, `priority`
- `created_by`, `completed_by`, `completed_at`
- `created_at`, `updated_at`, `version`

#### `task_assignment`

- `id`, `task_id`
- `assignee_type` (`user`, `role`, `unit`)
- référence d'assigné
- `assigned_by`, `assigned_at`, `unassigned_at`

Le modèle polymorphe doit être remplacé par des clés étrangères explicites ou tables distinctes lors de la conception physique.

#### `task_event`

- `id`, `task_id`, `event_type`
- `actor_id`, `occurred_at`
- `from_state`, `to_state`
- métadonnées strictement structurées et minimales

Cet historique métier complète l'audit de sécurité ; il sert à expliquer la vie de la tâche.

### Relève

#### `handover`

- `id`, `organization_id`, `unit_id`
- `period_start`, `period_end`
- `status` (`draft`, `open`, `closed`)
- `created_by`, `created_at`, `closed_by`, `closed_at`, `version`

#### `handover_item`

- `id`, `handover_id`
- `item_type` (`transmission`, `task`)
- référence de l'élément
- `reason` (`manual`, `important`, `unread`, `overdue`, `rule`)
- `added_by`, `added_at`, `reviewed_at`, `reviewed_by`
- `sort_order`

Les références polymorphes devront être garanties par le schéma, par exemple via deux tables de liaison distinctes.

### Audit, archivage et exports

#### `audit_event`

- `id` monotone ou UUID ordonnable
- `occurred_at`, `recorded_at`
- `actor_type`, `actor_id` facultatif pour les événements système
- `action`, `target_type`, `target_id`
- `organization_id`, `scope_type`, `scope_id`
- `outcome`, `reason_code`, `correlation_id`
- `source_ip` sous forme minimisée selon politique, `user_agent` borné si justifié
- `metadata` JSON structuré, sans contenu métier
- `previous_hash`, `event_hash`, `hash_key_version`

La table est append-only pour les rôles applicatifs. Une chaîne de hachage détecte une altération mais ne la rend pas impossible face à un administrateur de base ; un ancrage externe ou stockage WORM est nécessaire pour une garantie plus forte.

#### `retention_policy`

- `id`, `organization_id`
- `data_type`, `retention_period`, `archive_period`
- `legal_basis_reference`, `status`
- `effective_from`, `created_by`, `created_at`

#### `legal_hold`

- `id`, `organization_id`, `target_type`, `target_id`
- `reason`, `starts_at`, `ends_at`, `created_by`

Empêche une purge programmée lorsqu'une conservation exceptionnelle est justifiée.

#### `archive_operation`

- `id`, `target_type`, `target_id`
- `operation_type`, `reason`, `status`
- `requested_by`, `requested_at`, `completed_at`

#### `export_job`

- `id`, `organization_id`, `requested_by`, `reason`
- `scope`, `format`, `status`
- `created_at`, `expires_at`, `download_count`
- `file_hash`, référence de stockage temporaire

Les fichiers exportés ne devraient pas être stockés durablement en base.

## 4. Règles d'intégrité essentielles

- Une ressource ne peut référencer qu'une personne et une unité de la même organisation.
- Un auteur, assigné ou destinataire doit être actif et habilité au moment de l'opération.
- Une transmission publiée possède au moins une version et son `current_version_id` appartient à cette transmission.
- Une version publiée, un accusé et un événement d'audit sont non modifiables par les rôles applicatifs.
- Une relève ne référence que des éléments de son périmètre selon les règles approuvées.
- Les intervalles datés vérifient `starts_at < ends_at` lorsque la fin existe.
- Les mises à jour utilisent une colonne `version` pour détecter les conflits.
- Les contraintes critiques sont appliquées en base lorsqu'elles peuvent l'être, et pas uniquement dans l'interface.

## 5. Indexation et recherche

- Index sur les clés de périmètre et toutes les clés étrangères.
- Index composés sur (`unit_id`, `published_at`), (`person_id`, `published_at`) et (`status`, `due_at`).
- Index sur accusés (`user_id`, `transmission_version_id`).
- Index sur audit (`organization_id`, `occurred_at`), (`target_type`, `target_id`) et `correlation_id`.
- Recherche textuelle PostgreSQL possible uniquement sur le contenu autorisé, avec filtrage de périmètre dans la requête ; aucun moteur externe obligatoire.
- Les performances et fuites indirectes de la recherche doivent être testées, notamment comptages et suggestions.

## 6. Isolation des données

La protection principale réside dans les services d'autorisation du backend et des requêtes systématiquement filtrées. PostgreSQL Row-Level Security peut fournir une défense en profondeur, à condition que :

- le contexte utilisateur et de périmètre soit injecté de façon sûre dans chaque transaction ;
- le rôle de connexion applicatif ne puisse pas contourner RLS ;
- les migrations, tâches asynchrones et outils d'administration aient des rôles distincts ;
- les politiques soient couvertes par des tests d'isolation.

Un prototype RLS sera réalisé sur les tables critiques. RLS ne sera activée dans le MVP que si des rôles de base distincts et des tests systématiques démontrent son efficacité ; à défaut, les contrôles backend et requêtes filtrées resteront la protection principale.

## 7. Données de test

- Génération locale de personnages et structures entièrement fictifs.
- Noms clairement synthétiques et domaines réservés tels que `example.test`.
- Dates, contenus et identifiants générés sans copie de fichiers réels.
- Aucun dump, extrait de journal, capture d'écran ou sauvegarde de production dans le dépôt et la CI.
- Vérification automatique possible par détection de secrets et règle de contribution explicite.
