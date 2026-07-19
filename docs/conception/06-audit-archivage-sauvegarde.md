# Audit, archivage et sauvegarde

## 1. Événements d'audit

### Catalogue minimal

| Domaine | Événements |
|---|---|
| Session | connexion, compte inconnu/inactif, déconnexion, révocation, échec CSRF répété |
| Autorisation | refus sensible, changement de rôle ou rattachement |
| Personne | création, modification de champs identifiants, affectation, archivage, lecture d'archive |
| Transmission | création, publication, lecture sensible selon politique, correction, accusé |
| Tâche | création, attribution, changement d'état ou d'échéance, annulation |
| Relève | création, ajout/retrait, ouverture, clôture, réouverture |
| Audit | recherche, consultation, vérification, export |
| Export | demande, génération, téléchargement, expiration, échec |
| Conservation | changement de politique, legal hold, simulation et purge |
| Exploitation | migration, sauvegarde et restauration sous forme de résultat sans secret |

### Schéma canonique

```text
id, sequence, partition, occurred_at, recorded_at,
actor_type, actor_id, action,
target_type, target_id,
organization_id, scope_kind, scope_id,
outcome, reason_code, correlation_id,
metadata structurées,
previous_hash, event_hash, key_version
```

Le champ `metadata` utilise une liste blanche par type d'événement. Sont interdits : contenu libre métier, nom complet de personne si l'ID suffit, jetons, cookies, secrets, corps HTTP et traces.

## 2. Chaîne d'intégrité

Une partition mensuelle par organisation est recommandée : `organization_id:YYYY-MM`. Le premier événement contient le hash terminal de la partition précédente dans son manifeste.

```text
canonical = canonical_json(event_without_hashes)
event_hash = HMAC-SHA-256(key_version, previous_hash || canonical)
```

- La sérialisation canonique, l'encodage et l'ordre des champs MUST être spécifiés et testés par vecteurs fixes.
- La clé HMAC est distincte des clés de session et de sauvegarde.
- Un travail quotidien vérifie la chaîne et produit un résultat audité.
- À la fermeture d'une partition, un manifeste contient bornes, nombre d'événements et hash terminal.
- Le manifeste est exportable vers une cible séparée locale ; une signature asymétrique est préférable si le vérificateur doit être indépendant.

Une rupture déclenche une alerte locale de sévérité critique et bloque la purge des événements concernés, sans bloquer automatiquement les soins ou l'accompagnement.

## 3. Écritures transactionnelles

Le cas d'usage écrit l'état métier et l'événement dans une transaction. Si l'audit obligatoire échoue, la mutation métier échoue. Les événements purement techniques peuvent passer par une file durable, mais cette exception est explicitement cataloguée.

La génération du numéro de séquence verrouille uniquement la tête de la partition afin de limiter la contention. Les mesures de charge vérifieront ce point.

## 4. Consultation et export d'audit

- Filtres bornés par période ; période maximale par défaut 31 jours (`PILOTE`).
- Accès nominatif réservé aux permissions prévues.
- Export asynchrone en JSON Lines canonique plus manifeste de vérification.
- Tout export exige un motif, expire et est lui-même audité.
- L'outil de vérification futur doit fonctionner hors ligne sans accès à la production.

## 5. Archivage fonctionnel

L'archivage :

1. vérifie permission, périmètre, motif et ETag ;
2. vérifie les tâches ouvertes et avertit ou refuse selon règle métier ;
3. pose statut et métadonnées d'archive sans déplacer ni supprimer la ligne ;
4. retire la ressource des listes ordinaires ;
5. exige une permission dédiée pour toute consultation ;
6. écrit l'événement d'audit dans la même transaction.

La désarchivation n'est pas une mise à jour libre : elle utilise une commande motivée et une permission dédiée à ajouter si le pilote la requiert.

## 6. Conservation et purge

Les durées sont `PILOTE` et juridiquement validées par type : personne, transmission, tâche, relève, audit, export, session et sauvegarde.

Le moteur de purge reste désactivé jusqu'à leur validation. Ensuite, chaque exécution suit :

```text
simulation -> rapport borné -> approbation habilitée -> travail idempotent
           -> contrôle d'intégrité -> audit du résultat
```

Un `legal_hold` exclut explicitement les cibles. Les suppressions respectent l'ordre des dépendances et n'effacent jamais l'audit avant sa propre échéance. Les données d'audit devenues non nécessaires peuvent être désidentifiées si cette opération et sa valeur probante sont validées.

## 7. Exports métier

- Formats initiaux : CSV UTF-8 pour données tabulaires précisément définies et JSON pour restitution structurée.
- Aucun export générique de toutes les tables.
- Permission, finalité, motif, périmètre, volume maximal et colonnes sont fixés par type d'export.
- Fichier chiffré au repos, nom non révélateur, hash SHA-256 et expiration courte.
- Ticket de téléchargement à usage unique ; compteur et acteur audités.
- Suppression automatique après expiration, indépendamment du téléchargement.

## 8. Sauvegarde

### Contenu

- PostgreSQL applicatif et PostgreSQL Keycloak, sauvegardés de façon cohérente.
- Manifestes des versions d'images et migrations.
- Configuration non secrète nécessaire à la reconstruction.
- Secrets et clés via une procédure séparée, chiffrée et contrôlée ; jamais dans l'archive de configuration en clair.

### Stratégie

Tant que RPO/RTO et volumétrie ne sont pas mesurés, la référence est : dump logique chiffré quotidien pour la simplicité du pilote, avec plusieurs générations. Si le RPO validé est inférieur à 24 heures ou si le volume le nécessite, passer à une sauvegarde physique avec archivage WAL.

La cible est un filesystem ou stockage auto-hébergé séparé de l'hôte. Une copie hors ligne ou immuable protège contre le rançongiciel.

### Propriétés obligatoires

- Chiffrement avant sortie de l'hôte avec clé dédiée.
- Somme de contrôle et manifeste.
- Aucun secret dans le nom de fichier ou les journaux.
- Politique de rétention multi-générations.
- Échec visible dans l'état d'exploitation local.
- Accès en lecture à la cible impossible pour le compte applicatif.

## 9. Restauration

Un test de restauration :

1. crée un environnement isolé sans route vers des utilisateurs réels ;
2. restaure les deux bases et les secrets nécessaires ;
3. applique uniquement les migrations compatibles prévues ;
4. vérifie comptes techniques, intégrité référentielle et chaînes d'audit ;
5. exécute des parcours de lecture/écriture sur données synthétiques incluses dans l'environnement de test ;
6. mesure RPO et RTO obtenus ;
7. détruit l'environnement selon une procédure contrôlée ;
8. conserve un rapport sans données métier.

Une sauvegarde non restaurée avec succès dans la fréquence `PILOTE` n'est pas considérée comme fiable.
