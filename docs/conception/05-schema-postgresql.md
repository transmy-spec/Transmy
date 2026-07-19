# Schéma relationnel PostgreSQL

## 1. Conventions physiques

- PostgreSQL 16 ou version LTS/supportée retenue au moment du build.
- Schémas : `app`, `audit`, `jobs` et `auth_session`.
- UUID via fonction PostgreSQL approuvée ; `timestamptz NOT NULL` pour tous les instants.
- Colonnes `created_at`, `updated_at` et `row_version bigint` sur les agrégats modifiables.
- Codes stables en `text` avec contraintes de format ; états en types texte contraints plutôt qu'en enum PostgreSQL pour faciliter les migrations.
- Aucun déclencheur ne remplace une règle métier nécessitant l'identité de l'acteur. Les contraintes de cohérence restent en base.

## 2. Tables par module

### Organisation et habilitations

```text
app.organization(id PK, name, slug UQ, status, timestamps, row_version)
app.establishment(id PK, organization_id FK, code, name, timezone, status, ..., UQ(org, code))
app.service(id PK, establishment_id FK, code, name, status, ..., UQ(establishment, code))
app.unit(id PK, service_id FK, code, name, status, ..., UQ(service, code))

app.user_account(id PK, oidc_issuer, oidc_subject, display_name, email, status,
                 authorization_version, last_login_at, ..., UQ(issuer, subject))
app.user_unit_membership(id PK, user_id FK, unit_id FK, starts_at, ends_at, status, ...)
app.user_service_membership(id PK, user_id FK, service_id FK, starts_at, ends_at, status, ...)
app.user_establishment_membership(id PK, user_id FK, establishment_id FK, starts_at, ends_at, status, ...)
app.role(id PK, organization_id FK NULL, code, name, is_system, status, ...)
app.permission(id PK, code UQ, resource_type, action, description)
app.role_permission(role_id FK, permission_id FK, PK(role_id, permission_id))
app.role_assignment(id PK, user_id FK, role_id FK, scope_kind, unit_id/service_id/
                    establishment_id/organization_id, starts_at, ends_at,
                    granted_by FK, granted_at, revoked_by FK NULL, revoked_at NULL)
```

`role_assignment` possède une contrainte garantissant qu'une seule colonne de périmètre correspond à `scope_kind`. Une modification incrémente `user_account.authorization_version`.

### Personnes

```text
app.supported_person(id PK, organization_id FK, internal_reference,
                     family_name, given_name, preferred_name, birth_date,
                     status, archived_at, archived_by FK, archive_reason,
                     timestamps, row_version, UQ(organization_id, internal_reference))
app.person_assignment(id PK, person_id FK, unit_id FK, starts_at, ends_at,
                      is_primary, created_by FK, timestamps, row_version)
```

Les références croisées d'organisation sont empêchées par clés composites ou déclencheurs de contrainte testés. Les affectations peuvent se chevaucher ; une seule peut être primaire à un instant donné via contrainte d'exclusion si cette règle est confirmée au pilote.

### Transmissions

```text
app.transmission_category(id PK, organization_id FK, code, label, description,
                          color, sort_order, status, ..., UQ(org, code))
app.importance_level(id PK, organization_id FK, code, label, rank,
                     requires_acknowledgement, status, ..., UQ(org, code), UQ(org, rank))
app.transmission(id PK, organization_id FK, unit_id FK, person_id FK,
                 category_id FK, importance_level_id FK, status, author_id FK,
                 published_at, current_version_id, selected_for_handover,
                 timestamps, row_version)
app.transmission_version(id PK, transmission_id FK, version_number,
                         content, change_reason, created_by FK, created_at,
                         previous_version_id FK, content_hash,
                         UQ(transmission_id, version_number))
app.transmission_acknowledgement(id PK, transmission_id FK,
                                transmission_version_id FK, user_id FK,
                                acknowledged_at,
                                UQ(transmission_version_id, user_id))
```

La création initiale insère transmission et version dans une transaction. `current_version_id` est ajouté après création ou différé pour éviter le cycle de clés. Une contrainte différée vérifie que la version courante appartient à la transmission.

### Tâches et relèves

```text
app.task(id PK, organization_id FK, unit_id FK, person_id FK NULL,
         transmission_id FK NULL, title, description, status, due_at,
         priority, created_by FK, completed_by FK NULL, completed_at NULL,
         timestamps, row_version)
app.task_user_assignment(id PK, task_id FK, user_id FK, assigned_by FK,
                         assigned_at, unassigned_at)
app.task_unit_assignment(id PK, task_id FK, unit_id FK, assigned_by FK,
                         assigned_at, unassigned_at)
app.task_event(id PK, task_id FK, event_type, actor_id FK, occurred_at,
               from_state, to_state, metadata jsonb)

app.handover(id PK, organization_id FK, unit_id FK, period_start, period_end,
             status, created_by FK, created_at, closed_by FK NULL,
             closed_at NULL, row_version)
app.handover_transmission_item(id PK, handover_id FK, transmission_id FK,
                               reason, added_by FK, added_at, reviewed_by FK NULL,
                               reviewed_at NULL, sort_order, UQ(handover, transmission))
app.handover_task_item(id PK, handover_id FK, task_id FK, reason, added_by FK,
                       added_at, reviewed_by FK NULL, reviewed_at NULL,
                       sort_order, UQ(handover, task))
```

Deux tables de liaison évitent des clés étrangères polymorphes. Une tâche n'a qu'une attribution active, vérifiée par transaction et index unique partiel dans chaque table ; le service empêche une attribution simultanée user/unité.

### Session, travaux et audit

```text
auth_session.session(id_hash PK, user_id FK, encrypted_tokens,
                     key_version, csrf_secret_hash, authorization_version,
                     created_at, last_seen_at, idle_expires_at, absolute_expires_at,
                     revoked_at)

jobs.job(id PK, kind, payload jsonb, status, priority, run_after,
         attempt_count, max_attempts, locked_by, locked_at,
         last_error_code, created_at, updated_at)

audit.event(sequence_id bigint, chain_partition, id UUID,
            occurred_at, recorded_at, actor_type, actor_id,
            action, target_type, target_id, organization_id, scope_kind,
            scope_id, outcome, reason_code, correlation_id, metadata jsonb,
            previous_hash, event_hash, key_version,
            PK(chain_partition, sequence_id), UQ(id))
audit.anchor(id PK, chain_partition, first_sequence, last_sequence,
             head_hash, signature, key_version, created_at, exported_at)
```

Les valeurs de `payload` et `metadata` sont validées par type avant insertion. Aucun contenu de transmission ni jeton n'y est autorisé.

## 3. Contraintes importantes

- `ends_at IS NULL OR ends_at > starts_at`.
- Une archive a `archived_at`, `archived_by` et un motif non vide.
- Une transmission `published` a `published_at` et une version courante.
- Une version 1 n'a pas de précédente ; une version N référence N-1 de la même transmission.
- `content` non vide, longueur bornée et absence de caractère NUL.
- Une tâche `done` a `completed_at` et `completed_by` ; les autres états n'en ont pas.
- Une relève clôturée a auteur et date de clôture.
- `period_end > period_start`.
- Les événements d'audit ne sont jamais modifiés par le rôle d'exécution.

## 4. Index initiaux

```text
person_assignment(unit_id, starts_at, ends_at)
supported_person(organization_id, status, family_name, given_name)
transmission(unit_id, published_at DESC, id)
transmission(person_id, published_at DESC, id)
transmission(category_id, importance_level_id, published_at DESC)
transmission_acknowledgement(user_id, transmission_version_id)
task(unit_id, status, due_at, id)
handover(unit_id, period_start DESC, id)
audit.event(organization_id, occurred_at DESC, sequence_id)
audit.event(target_type, target_id, occurred_at DESC)
audit.event(correlation_id)
jobs.job(status, run_after, priority)
```

Les index de recherche textuelle sur les transmissions ne sont ajoutés qu'après mesure : ils augmentent l'exposition en cas d'accès DB et le coût d'écriture.

## 5. Rôles PostgreSQL

| Rôle | Pouvoirs |
|---|---|
| `app_migrator` | DDL contrôlé pendant migration, pas utilisé par le runtime |
| `app_runtime` | CRUD limité sur `app`, insert/select requis sur audit, sessions et jobs |
| `app_worker` | Accès aux travaux et cas d'usage explicitement nécessaires |
| `audit_verifier` | Lecture audit et insertion des résultats/ancrages, aucune mutation d'événement |
| `backup_operator` | Droits de sauvegarde selon outil, aucun login applicatif |

Le propriétaire des tables n'est jamais le rôle runtime. Les privilèges sont testés en CI par tentatives de `UPDATE`/`DELETE` interdites sur `audit.event`.

## 6. RLS

Le prototype porte sur `supported_person`, `transmission`, `task` et les listes de relève. Il doit démontrer :

- contexte de sécurité fixé localement à la transaction et impossible à réutiliser entre requêtes ;
- rôle runtime sans `BYPASSRLS` et non propriétaire ;
- comportement sûr des workers et migrations ;
- tests croisés unité, service et établissement ;
- absence de divergence entre politique Python et politique SQL.

Sans preuve concluante, RLS reste désactivée et aucune documentation ne la présente comme une protection active.

## 7. Migrations

- Migration forward versionnée et immuable une fois publiée.
- Sauvegarde vérifiée avant migration destructive ou longue.
- Ajouts compatibles d'abord, remplissage idempotent ensuite, contraintes finales en dernier.
- Aucun retrait de colonne sensible avant expiration de la compatibilité et validation de conservation.
- Chaque migration possède un test sur base vide et sur jeu synthétique de version précédente.
