# Contrat d'API

## 1. Conventions HTTP

- Base : `/api/v1` ; JSON UTF-8 uniquement, sauf téléchargement d'un export.
- Authentification : cookie BFF ; CSRF requis pour toute mutation.
- UUID canoniques dans les chemins ; les identifiants sont opaques.
- Listes paginées par curseur, ordre stable et limite maximale de 100.
- Filtrage par paramètres explicitement documentés ; les paramètres inconnus retournent `422`.
- Les créations acceptent `Idempotency-Key` ; sa portée est utilisateur + route pendant 24 heures (`PILOTE`).
- Les mises à jour utilisent `If-Match` avec un ETag dérivé du numéro de version.
- Les horodatages métier proviennent du serveur, sauf dates explicitement déclarées comme saisies métier.

## 2. Enveloppes

### Liste

```json
{
  "items": [],
  "next_cursor": null
}
```

### Erreur

```json
{
  "error": {
    "code": "validation_error",
    "message": "La demande est invalide.",
    "correlation_id": "00000000-0000-4000-8000-000000000001",
    "fields": []
  }
}
```

Le message public ne contient ni SQL, ni trace, ni existence d'une cible inaccessible. Codes communs : `authentication_required`, `session_expired`, `access_denied`, `not_found`, `validation_error`, `conflict`, `precondition_required`, `rate_limited`, `service_unavailable`.

## 3. Routes

### Session et contexte

| Méthode | Route | Permission | Résultat |
|---|---|---|---|
| GET | `/session` | session valide | Profil minimal, périmètre choisi, capacités UI, CSRF |
| PUT | `/session/context` | session valide | Change le contexte actif sans élargir les droits |
| POST | `/auth/logout` | session + CSRF | `204` |

### Structures et référentiels

| Méthode | Route | Permission |
|---|---|---|
| GET | `/establishments` | `structure.read` |
| GET/POST | `/establishments/{id}/services` | lecture / `structure.manage` |
| GET/POST | `/services/{id}/units` | lecture / `structure.manage` |
| PATCH | `/units/{id}` | `structure.manage` + ETag |
| GET/POST | `/transmission-categories` | lecture / `taxonomy.manage` |
| PATCH | `/transmission-categories/{id}` | `taxonomy.manage` + ETag |
| GET | `/importance-levels` | utilisateur métier |

La désactivation utilise `PATCH {"status":"inactive"}` ; aucun `DELETE` n'est exposé.

### Utilisateurs et habilitations

| Méthode | Route | Permission |
|---|---|---|
| GET | `/users?query=&unit_id=` | `user.read_minimal` |
| POST | `/users` | `membership.manage` |
| PATCH | `/users/{id}` | `membership.manage` + périmètre |
| GET/POST | `/users/{id}/memberships` | lecture / `membership.manage` |
| POST | `/users/{id}/role-assignments` | `role.assign` |
| POST | `/role-assignments/{id}/revoke` | `role.assign` |
| GET | `/roles` | `role.read` |

Les réponses utilisateur excluent les données Keycloak inutiles et toute information hors finalité.

### Personnes accompagnées

| Méthode | Route | Permission |
|---|---|---|
| GET | `/people?query=&unit_id=&status=` | `person.search` |
| POST | `/people` | `person.create` |
| GET | `/people/{id}` | `person.read` ou permission d'archive |
| PATCH | `/people/{id}` | `person.update` + ETag |
| POST | `/people/{id}/assignments` | `person.update` |
| PATCH | `/person-assignments/{id}` | `person.update` + ETag |
| POST | `/people/{id}/archive` | `person.archive` |

La recherche exige au moins 2 caractères (`PILOTE`), limite la réponse et n'offre pas d'énumération globale.

### Transmissions

| Méthode | Route | Permission |
|---|---|---|
| GET | `/transmissions?...` | `transmission.read` |
| POST | `/transmissions` | `transmission.create` |
| GET | `/transmissions/{id}` | `transmission.read` |
| PATCH | `/transmissions/{id}/draft` | auteur + ETag |
| POST | `/transmissions/{id}/publish` | `transmission.publish` + ETag |
| POST | `/transmissions/{id}/versions` | `transmission.correct` + motif |
| POST | `/transmissions/{id}/acknowledgements` | `acknowledgement.create_self` |
| GET | `/transmissions/{id}/acknowledgements` | agrégat ou nominatif selon permission |

Création minimale :

```json
{
  "person_id": "00000000-0000-4000-8000-000000000010",
  "unit_id": "00000000-0000-4000-8000-000000000020",
  "category_id": "00000000-0000-4000-8000-000000000030",
  "importance_level_id": "00000000-0000-4000-8000-000000000040",
  "content": "Contenu entièrement fictif.",
  "selected_for_handover": false
}
```

Publication fige la version courante. Une correction exige `change_reason` et crée une version ; elle ne modifie jamais la précédente.

### Tâches

| Méthode | Route | Permission |
|---|---|---|
| GET/POST | `/tasks` | `task.read` / `task.create` |
| GET/PATCH | `/tasks/{id}` | `task.read` / `task.update` + ETag |
| POST | `/tasks/{id}/assignments` | `task.assign` |
| POST | `/tasks/{id}/complete` | règle de clôture + ETag |
| POST | `/tasks/{id}/cancel` | `task.cancel` + motif |
| GET | `/tasks/{id}/events` | `task.read` |

Une mutation d'état explicite est préférée à un `PATCH` générique afin d'imposer les invariants et l'audit.

### Relèves

| Méthode | Route | Permission |
|---|---|---|
| GET/POST | `/handovers` | `handover.read` / `handover.create` |
| GET | `/handovers/{id}` | `handover.read` |
| POST | `/handovers/{id}/items` | `handover.update` |
| DELETE | `/handovers/{id}/items/{item_id}` | `handover.update`, brouillon seulement |
| POST | `/handovers/{id}/open` | `handover.update` + ETag |
| POST | `/handovers/{id}/close` | `handover.close` + ETag |
| POST | `/handovers/{id}/reopen` | `handover.reopen` + motif |

Le `DELETE` d'un élément de relève supprime uniquement une liaison de brouillon, jamais l'objet métier référencé.

### Audit, archives et exports

| Méthode | Route | Permission |
|---|---|---|
| GET | `/audit-events?...` | `audit.read` |
| POST | `/audit-verifications` | `audit.verify` |
| GET | `/audit-verifications/{id}` | `audit.verify` |
| POST | `/exports` | `export.request` + motif |
| GET | `/exports/{id}` | demandeur ou permission de contrôle |
| POST | `/exports/{id}/download-ticket` | `export.download` |
| GET | `/retention-policies` | `retention.read` |
| PUT | `/retention-policies/{data_type}` | `retention.manage` + ETag |

Le téléchargement utilise un ticket opaque à usage unique et durée courte, servi par l'application ou Caddy via mécanisme interne. Aucune URL publique durable.

## 4. États et transitions

```text
Transmission : draft -> published -> corrected -> archived
Tâche        : todo -> in_progress -> done
                         |             
                         +-----------> cancelled
Relève       : draft -> open -> closed -> open (permission de réouverture)
Export       : queued -> running -> ready -> expired
                       \-> failed
```

Toute transition non listée retourne `409 invalid_state_transition`.

## 5. Concurrence et idempotence

- `GET` d'une ressource versionnée retourne `ETag: "<version>"`.
- `PATCH` et commandes sensibles exigent `If-Match`; absence : `428`, conflit : `412`.
- Une répétition avec la même `Idempotency-Key` et le même corps retourne le résultat initial.
- Une même clé avec un corps différent retourne `409 idempotency_conflict`.
- Accusé de lecture : unicité en base et réponse idempotente `200/201`.

## 6. Pagination, tris et limites

- Curseur signé ou authentifié contenant uniquement position, ordre et empreinte des filtres.
- Ordre par défaut stable : date décroissante puis UUID.
- Taille par défaut 25, maximum 100.
- Le total exact n'est pas retourné par défaut afin de limiter coût et fuites indirectes.
- Contenu transmission : 10 000 caractères (`PILOTE`) ; titre tâche : 200 ; motif : 500.

## 7. OpenAPI et compatibilité

La future spécification OpenAPI 3.1 MUST :

- définir tous les schémas sans `additionalProperties` libre, sauf métadonnées explicitement bornées ;
- documenter permissions, erreurs et ETag par opération ;
- générer le client TypeScript du frontend ;
- être testée pour détecter toute rupture ;
- masquer en production les interfaces interactives publiques, ou les protéger par permission d'administration.
