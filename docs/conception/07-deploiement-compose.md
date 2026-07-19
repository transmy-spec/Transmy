# Déploiement Docker Compose

## 1. Profils

Deux assemblages sont distingués :

- **développement** : ergonomie locale, données synthétiques, ports strictement nécessaires ;
- **production de référence** : Caddy seul exposé, secrets externes, images verrouillées, aucun outil de debug.

Les valeurs de développement MUST être refusées par validation de configuration si `APP_ENV=production`.

## 2. Services

| Service | Rôle | Exposition | Volume persistant |
|---|---|---|---|
| `caddy` | TLS, routage, en-têtes, limites | `80/443` | certificats et état Caddy |
| `frontend` | fichiers Vue 3 statiques | réseau web interne | aucun |
| `api` | BFF et API FastAPI | réseau web interne | aucun |
| `worker` | travaux différés | réseau données interne | aucun |
| `postgres-app` | données métier, sessions, audit, jobs | réseau données uniquement | oui |
| `keycloak` | OIDC | route publique de connexion, admin restreinte | aucun |
| `postgres-keycloak` | données Keycloak | réseau identité uniquement | oui |
| `backup` | sauvegarde chiffrée, profil optionnel | réseaux DB, cible de sauvegarde | cible montée dédiée |

## 3. Réseaux

```text
public:        caddy
web_internal:  caddy, frontend, api, keycloak
app_data:      api, worker, postgres-app, backup
identity_data: keycloak, postgres-keycloak, backup
```

Les réseaux de données sont `internal: true`. Les bases n'ont aucun port publié sur l'hôte. L'administration Keycloak passe par une route ou un réseau d'administration distinct, limité par IP/VPN selon l'organisme.

## 4. Routage de référence

| Chemin public | Destination |
|---|---|
| `/` | frontend |
| `/api/*` | api |
| `/auth/*` | api BFF |
| `/oidc/*` | Keycloak avec hostname public cohérent |

Les en-têtes de client transmis par Caddy sont écrasés, pas simplement relayés. FastAPI ne fait confiance qu'au proxy connu. La CSP de base interdit toute destination externe et autorise uniquement les ressources locales nécessaires.

## 5. Secrets

Secrets minimaux :

- mots de passe des deux bases ;
- secret du client OIDC ;
- clé de chiffrement de session ;
- clé CSRF ou de dérivation ;
- clés d'intégrité/signature d'audit ;
- clé ou configuration de chiffrement des sauvegardes ;
- compte d'amorçage Keycloak, retiré ou protégé après installation.

Ils sont fournis comme fichiers montés en lecture seule depuis un répertoire hors dépôt, permissions minimales. Les variables d'environnement peuvent contenir des chemins de secrets, pas leur valeur lorsque l'image supporte les fichiers `_FILE`.

## 6. Durcissement des conteneurs

- Utilisateur non root et UID/GID documentés.
- `read_only: true` lorsque possible ; `tmpfs` borné pour `/tmp`.
- `cap_drop: [ALL]`, puis ajout explicite exceptionnel.
- `security_opt: no-new-privileges:true`.
- Limites mémoire/CPU/PID définies selon les mesures `PILOTE`.
- Images minimales, versionnées et verrouillées par digest en production.
- Aucun socket Docker monté dans un service.
- Healthchecks sans secret et sans écriture métier.

## 7. Ordre de démarrage

`depends_on` n'est pas une garantie de disponibilité. Chaque composant réessaie avec temporisation bornée.

1. bases saines ;
2. migration applicative exécutée par une tâche ponctuelle et un compte dédié ;
3. Keycloak et API prêts ;
4. worker démarré ;
5. Caddy rend le service disponible.

Une migration n'est pas lancée simultanément par chaque réplique API. Son échec empêche la nouvelle version d'être déclarée prête.

## 8. Santé et observabilité locale

| Route | Contenu | Exposition |
|---|---|---|
| `/health/live` | processus vivant | interne/proxy |
| `/health/ready` | DB, migrations et dépendances critiques | interne/proxy, sans détail sensible |
| `/health/startup` | initialisation terminée | interne |

Les journaux JSON vont vers stdout/stderr et sont collectés par l'hôte. Champs minimaux : timestamp, niveau, service, event code, correlation ID. Aucun contenu métier, cookie, jeton ou chaîne de connexion.

Les métriques sont locales et facultatives. Aucun endpoint ne communique avec l'extérieur ; aucune télémétrie n'est intégrée aux images ou au frontend.

## 9. Disponibilité et mises à jour

Le Compose de référence sur hôte unique accepte l'indisponibilité de cet hôte. Avant mise à jour :

1. vérifier compatibilité et espace ;
2. produire et vérifier une sauvegarde ;
3. télécharger ou importer les images signées/digests attendus ;
4. exécuter les migrations ponctuelles ;
5. contrôler santé et parcours synthétique ;
6. conserver la procédure de restauration si retour applicatif impossible.

Une simple rétrogradation de l'image n'est pas promise après migration de schéma.

## 10. Mode sans Internet

- Les images peuvent être importées depuis des archives vérifiées.
- Polices, scripts, documentation d'exploitation et dépendances d'exécution sont embarqués.
- Keycloak, sauvegarde, recherche, notifications internes et audit fonctionnent localement.
- La validation des certificats TLS publics peut nécessiter un DNS et une connectivité adaptés ; un certificat institutionnel ou ACME interne doit pouvoir être configuré.

## 11. Amorçage

L'installation initiale suit une commande ponctuelle idempotente :

1. vérifier configuration et secrets ;
2. migrer la base ;
3. créer l'organisation unique ;
4. enregistrer les référentiels système ;
5. lier un premier administrateur d'organisation par son `issuer` et `subject` connus ;
6. journaliser l'amorçage sans secret.

Aucun compte métier générique ni donnée de démonstration n'est créé en production.
