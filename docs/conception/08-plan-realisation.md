# Plan de réalisation

## 1. Principes

- Construire les contrôles d'accès et l'audit avec le premier cas d'usage, pas après les fonctions métier.
- Garder chaque incrément installable avec Docker Compose et testable avec données synthétiques.
- Ne pas ouvrir un domaine tant que ses invariants, permissions et événements d'audit ne sont pas définis.
- Traiter les paramètres `PILOTE` comme des critères d'entrée en production.

## 2. Incréments

### Lot 0 — Socle reproductible

**État au 18 juillet 2026 : scaffold implémenté, exécution locale en attente d'un environnement équipé de Docker ou des runtimes Python/Node.**

- Arborescence backend/frontend/infrastructure.
- Compose de développement sans donnée réelle.
- PostgreSQL applicatif et Keycloak séparés.
- Migrations, configuration typée, gestion de secrets par fichiers.
- CI : formatage, tests, analyse statique, détection de secrets, licences et SBOM.

**Sortie :** installation locale documentée, services sains, aucune route métier.

Le dépôt contient désormais cette structure, mais la sortie du lot ne sera déclarée atteinte qu'après génération et commit du lockfile frontend, construction des images, exécution de la migration et passage de tous les contrôles documentés.

### Lot 1 — Identité et autorisation

**État au 18 juillet 2026 : incrément local implémenté et validé avec deux identités synthétiques.**

- Flux BFF OIDC complet, sessions serveur et CSRF.
- Organisation, établissements, services, unités et comptes.
- Rattachements, rôles, permissions et politiques centralisées.
- Matrice de tests positifs et négatifs.
- Audit append-only minimal et chaîne vérifiable.

**Sortie :** un utilisateur fictif authentifié ne voit que son périmètre ; le retrait d'accès est immédiat.

### Lot 2 — Personnes accompagnées

- Création, recherche bornée, fiche minimale et affectations datées.
- Gestion des homonymies selon champs validés.
- Archivage fonctionnel et lecture d'archive dédiée.

**Sortie :** aucune recherche, liste, compteur ou accès direct ne traverse un périmètre.

### Lot 3 — Transmissions et lectures

- Catégories et importance.
- Brouillon, publication, correction versionnée.
- Accusé explicite par version.
- Filtres, pagination et concurrence optimiste.

**Sortie :** parcours complet testé sur mobile et bureau, audit vérifiable, aucune mutation destructive.

### Lot 4 — Tâches et relèves

- Tâches, échéances, attribution unique et historique.
- Relèves, sélection automatique, ouverture, clôture et réouverture habilitée.
- Worker PostgreSQL idempotent.

**Sortie :** prise de poste présentant non-lus, importants, retards et échéances.

### Lot 5 — Conservation, exports et exploitation

- Politiques sans purge active tant que valeurs non validées.
- Exports finalisés, temporaires et audités.
- Sauvegarde chiffrée et restauration testée.
- Caddy durci, journaux locaux, guide de mise à jour.

**Sortie :** exercice de restauration réussi et mesuré ; rapport sans donnée métier.

### Lot 6 — Préparation du pilote

- Audit d'accessibilité WCAG 2.2 AA/RGAA.
- Tests de charge sur volumétrie validée.
- Revue de sécurité et tests d'intrusion ciblés.
- AIPD et qualification d'hébergement conduites par l'organisme.
- RPO/RTO, conservation, navigateurs et supervision renseignés.
- Documentation AGPL-3.0, contribution et sécurité.

**Sortie :** critères de sortie MVP satisfaits et risques résiduels acceptés explicitement.

## 3. Definition of Done d'une fonction

- Exigence et permission identifiées.
- Schéma d'entrée/sortie documenté dans OpenAPI.
- Autorisation testée en succès et refus sur plusieurs périmètres.
- Invariants transactionnels et concurrence testés.
- Événements d'audit et absence de données sensibles dans les logs vérifiés.
- Tests unitaires, intégration PostgreSQL et parcours critique.
- Interface clavier, lecteur d'écran et responsive vérifiée.
- Documentation d'exploitation mise à jour si nécessaire.
- Aucune donnée réelle ou pseudonymisée dans code, tests, captures ou fixtures.

## 4. Premiers artefacts à produire lors du passage au code

1. Structure du dépôt et conventions de contribution.
2. Compose local minimal et validation de configuration.
3. Migrations des structures, comptes, rôles et audit.
4. Squelette FastAPI avec contexte de sécurité et erreurs communes.
5. Flux BFF Keycloak et tests de session/CSRF.
6. Squelette Vue 3 accessible et client généré depuis OpenAPI.

Ce passage au code requiert une instruction explicite ; le présent lot reste documentaire.
