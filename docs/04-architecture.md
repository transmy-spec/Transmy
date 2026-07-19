# Architecture proposée

## 1. Style architectural

Pour le MVP, un monolithe modulaire est recommandé : une API FastAPI unique structurée par domaines, un frontend Vue 3, PostgreSQL et Keycloak. Ce choix réduit la complexité opérationnelle d'un produit auto-hébergé tout en maintenant des frontières internes qui permettront d'extraire un composant si un besoin réel apparaît.

```text
Navigateur
   │ HTTPS
   ▼
Reverse proxy / terminaison TLS
   ├────────► Frontend Vue 3 (fichiers statiques)
   ├────────► API FastAPI
   │              ├─ identité et autorisation
   │              ├─ personnes et structures
   │              ├─ transmissions et lectures
   │              ├─ tâches et relèves
   │              ├─ audit, archives et exports
   │              └────────► PostgreSQL
   └────────► Keycloak ───────────────────► PostgreSQL dédié/logiquement séparé

Tâches internes planifiées ─► échéances, archivage, exports, maintenance audit
Sauvegarde locale ──────────► dumps chiffrés + configuration nécessaire
```

## 2. Composants

### Frontend Vue 3

- Application responsive utilisant Vue Router, une gestion d'état limitée et un client API généré ou typé depuis OpenAPI.
- Aucun secret, rôle de confiance ou règle d'autorisation définitive dans le navigateur.
- Contenus servis localement : pas de CDN, police, script d'analyse ou ressource tierce obligatoire.
- Accessibilité intégrée aux composants, navigation clavier et annonces de changements d'état.
- Stratégie de rendu recommandée : SPA servie par le reverse proxy. Un backend-for-frontend peut être préféré pour mieux protéger les jetons ; voir la décision d'authentification.

### API FastAPI

Organisation interne proposée :

```text
api/             routes, schémas d'entrée/sortie, gestion HTTP
application/     cas d'usage, transactions, orchestration
domain/          entités, règles et politiques d'autorisation
infrastructure/  PostgreSQL, OIDC, stockage d'exports, horloge
audit/           création et vérification des événements
workers/         traitements planifiés et bornés
```

Règles :

- les routes n'accèdent pas directement aux tables ;
- un contexte de sécurité vérifié est construit à partir du jeton et du compte applicatif ;
- chaque cas d'usage appelle une politique d'autorisation avant l'accès aux données ;
- les requêtes filtrent le périmètre, y compris pour les listes et agrégats ;
- les opérations métier et l'audit associé partagent une transaction ;
- les erreurs externes ne révèlent ni existence d'objet non autorisé ni détail interne.

### PostgreSQL

- Base transactionnelle unique pour les données applicatives du MVP.
- Schémas ou bases distincts recommandés pour l'application et Keycloak ; comptes et secrets distincts.
- Migrations versionnées exécutées par un rôle dédié, jamais par le rôle d'exécution courant.
- Chiffrement des volumes assuré par l'hôte ou l'infrastructure ; TLS vers PostgreSQL si le trafic traverse un réseau non fiable.
- Défense en profondeur RLS à évaluer après prototype.

### Keycloak

- Keycloak gère authentification, sessions, MFA et éventuelle fédération.
- L'application conserve les profils minimaux, rattachements et habilitations métier.
- Le lien stable repose sur (`issuer`, `subject`).
- Les rôles de realm Keycloak ne remplacent pas la vérification des permissions et périmètres applicatifs.
- Un realm dédié est recommandé ; l'accès d'administration Keycloak n'est pas exposé publiquement sans protection supplémentaire.

### Reverse proxy

- Seul point public en production.
- Terminaison TLS, redirection HTTP, limites de taille, en-têtes de sécurité et limitation de débit complémentaire.
- L'API, PostgreSQL et l'interface d'administration Keycloak ne sont pas exposés directement à Internet.
- Caddy est le reverse proxy de référence du déploiement Docker Compose. Le contrat HTTP sera documenté afin de permettre son remplacement par Traefik ou Nginx.

### Traitements différés

Pour le MVP, un processus worker utilisant la même base et une table de travaux peut gérer exports, échéances et purges. Cela évite une dépendance obligatoire à Redis ou à un courtier de messages. Les travaux doivent être idempotents, réessayables, bornés et auditables.

## 3. Authentification recommandée

Deux modèles sont possibles :

1. **Backend-for-frontend avec cookie de session sécurisé** : le backend effectue Authorization Code + PKCE, conserve ou chiffre les jetons côté serveur et donne au navigateur un cookie `HttpOnly`. Cela limite l'exposition des jetons au JavaScript, mais ajoute une gestion de session et une protection CSRF.
2. **SPA publique avec Authorization Code + PKCE** : le navigateur détient les jetons en mémoire. C'est plus direct, mais une XSS peut les exfiltrer et la gestion du renouvellement demande une grande rigueur.

Le modèle backend-for-frontend est recommandé pour ce contexte sensible. Dans les deux cas : validation stricte des URI de redirection, état, nonce, PKCE, émetteur et audience ; déconnexion cohérente ; durée de session courte et MFA configurable.

## 4. Autorisation

Le modèle proposé combine RBAC et périmètre :

```text
autorisé = compte actif
         ∧ rattachement actif
         ∧ rôle actif donnant l'action
         ∧ ressource dans le périmètre autorisé
         ∧ contraintes métier satisfaites
```

Une bibliothèque interne unique expose des décisions explicites, par exemple `can_read_transmission(context, transmission)`. Pour les listes, elle produit des critères de requête plutôt qu'un filtrage après chargement. Les tests utilisent une matrice rôle × action × périmètre et vérifient les refus.

Le cache d'autorisation, s'il existe, doit être court, lié à une version d'habilitation et invalidé lors d'un retrait. Le MVP peut éviter ce cache pour privilégier la justesse.

## 5. Audit immuable

Trois niveaux sont distingués :

- **Append-only applicatif** : aucun `UPDATE` ou `DELETE` exposé ; privilèges SQL du compte applicatif limités.
- **Détection d'altération** : chaque événement inclut le hachage du précédent et son propre hachage authentifié ; une vérification planifiée signale les ruptures.
- **Résistance à l'administrateur** : ancrage périodique hors de la base ou stockage WORM géré par l'organisme.

Le MVP devrait fournir les deux premiers niveaux. Le troisième dépend de l'infrastructure et doit rester possible sans service cloud, par exemple export signé vers un support séparé. Une chaîne globale crée de la contention ; une chaîne par organisation et partition temporelle, avec manifestes d'ancrage, est plus exploitable.

Les clés de hachage ou signature sont fournies comme secrets montés, versionnées et sauvegardées séparément. L'audit ne contient pas les corps métier.

## 6. Archivage et sauvegarde

### Archivage fonctionnel

- Statut d'archive et métadonnées de décision dans la base.
- Exclusion des parcours courants et permission spécifique de consultation.
- Politiques de conservation paramétrées, mais purge automatique désactivée tant que règles et contrôles ne sont pas validés.
- Export ouvert et vérifiable lorsque nécessaire.

### Sauvegarde

- Sauvegarde cohérente PostgreSQL avec outil natif ou solution compatible auto-hébergée.
- Chiffrement avant stockage, somme de contrôle, manifeste de versions et politique de rétention.
- Sauvegarde distincte de la configuration Keycloak, des paramètres non secrets et des secrets/clefs par une procédure sécurisée.
- Cible locale, NAS, SSH/SFTP ou stockage objet compatible S3 auto-hébergé ; aucune cible cloud obligatoire.
- Restauration testée automatiquement autant que possible dans un environnement isolé.

Les objectifs RPO et RTO déterminent le choix entre dumps périodiques et archivage continu WAL.

## 7. Docker Compose

Services envisagés :

- `proxy` : point d'entrée HTTPS ;
- `frontend` : fichiers Vue compilés, ou servis directement par le proxy ;
- `api` : FastAPI avec plusieurs workers selon capacité ;
- `worker` : traitements différés sur la même image que l'API ;
- `postgres-app` : base applicative ;
- `keycloak` : fournisseur OIDC ;
- `postgres-keycloak` : séparation recommandée des données Keycloak ;
- profil optionnel `backup` pour les sauvegardes ;
- profil optionnel de supervision locale, sans export externe.

Les réseaux séparent exposition publique et données. Les volumes sont nommés, les secrets montés depuis des fichiers hors dépôt, les services utilisent des utilisateurs non privilégiés et des versions d'images verrouillées par digest pour les déploiements de production.

Le Compose de développement et la configuration de production de référence doivent être distincts afin de ne pas présenter des valeurs faibles comme sûres.

## 8. Observabilité sans télémétrie

- Journaux JSON locaux avec identifiant de corrélation, sans contenu métier ni jeton.
- Niveaux de journalisation configurables ; traces détaillées désactivées en production.
- Métriques techniques locales facultatives, non nominatives et sans export par défaut.
- Tableau de santé pour l'exploitant : disponibilité, migrations, file de travaux, sauvegardes et vérification de chaîne d'audit.
- Alertes possibles vers un système local choisi par l'organisme, jamais requises pour fonctionner.

## 9. Stratégie de livraison

- Images reproductibles et minimales, dépendances verrouillées, SBOM et signatures d'artefacts lorsque l'infrastructure le permet.
- CI sans données réelles : analyse statique, tests, scan des secrets, dépendances et images.
- Migrations sauvegardées et testées sur un volume restauré avant publication.
- Versions sémantiques, notes de mise à jour, compatibilité de schéma et procédure de retour documentée.
- AGPL-3.0 envisagée ; inventaire des licences et validation juridique requis avant publication.

## 10. Évolutions possibles, non requises au MVP

- Haute disponibilité PostgreSQL et déploiement orchestré.
- Fédération d'identité avec l'annuaire de l'organisme.
- Interopérabilité avec les référentiels et systèmes sectoriels validés.
- Stockage de pièces jointes auto-hébergé avec analyse antivirus.
- Réplication ou ancrage WORM du journal d'audit.
- Notifications locales ou institutionnelles configurables.
