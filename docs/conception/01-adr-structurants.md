# ADR structurants

Les ADR ci-dessous sont acceptés au titre de la validation globale du 18 juillet 2026. Un changement crée un nouvel ADR ; il ne réécrit pas rétroactivement la décision.

## ADR-001 — Monolithe modulaire

**Statut :** accepté  
**Contexte :** le produit doit être simple à auto-héberger et les limites de charge ne justifient pas des services distribués.  
**Décision :** une API FastAPI forme un monolithe modulaire séparé en domaines organisation, personnes, transmissions, tâches, relèves, autorisations, audit et exploitation. Le frontend Vue 3 est déployé séparément comme fichiers statiques.  
**Conséquences :** une transaction PostgreSQL peut couvrir métier et audit ; le déploiement reste lisible. Les modules MUST communiquer par interfaces internes et ne MUST pas accéder directement aux tables d'un autre module.

## ADR-002 — Une organisation par installation

**Statut :** accepté  
**Décision :** une installation de référence héberge une organisation juridique, contenant plusieurs établissements, services et unités. `organization_id` reste présent sur les données cloisonnées afin de rendre l'invariant explicite et de permettre une évolution.  
**Conséquences :** aucune administration inter-organisations n'est fournie dans le MVP. Toute future mutualisation exigera une nouvelle analyse de menaces et des tests d'isolation.

## ADR-003 — BFF et session serveur

**Statut :** accepté  
**Décision :** le navigateur ne détient pas les jetons Keycloak. FastAPI agit comme backend-for-frontend, réalise Authorization Code avec PKCE, conserve la session côté serveur et expose un cookie opaque `HttpOnly`.  
**Conséquences :** toutes les mutations MUST être protégées contre CSRF. Le frontend et l'API SHOULD partager la même origine publique.

## ADR-004 — RBAC limité par périmètre

**Statut :** accepté  
**Décision :** une permission effective combine l'état du compte, un rôle, une action, une ressource, un rattachement daté et le périmètre organisationnel. Le refus est la valeur par défaut.  
**Conséquences :** les listes MUST être filtrées dans la requête ; le frontend n'est jamais une frontière de sécurité. RLS fera l'objet d'un prototype avant activation.

## ADR-005 — Versions métier non destructives

**Statut :** accepté  
**Décision :** une transmission publiée est non modifiable. Une correction produit une nouvelle version motivée. Les accusés portent sur une version.  
**Conséquences :** le modèle distingue l'identité stable d'une transmission et ses versions. Aucun endpoint de suppression ordinaire n'existe.

## ADR-006 — Audit append-only vérifiable

**Statut :** accepté  
**Décision :** les événements d'audit sont écrits dans la transaction métier, sans contenu libre, et reliés par une chaîne cryptographique partitionnée. Un manifeste signé ou authentifié peut être exporté vers une cible séparée.  
**Conséquences :** le compte applicatif ne possède ni `UPDATE` ni `DELETE` sur l'audit. Ce mécanisme détecte l'altération mais ne promet pas à lui seul une valeur probatoire réglementaire.

## ADR-007 — PostgreSQL comme seule dépendance de données obligatoire

**Statut :** accepté  
**Décision :** données métier, sessions BFF et file de travaux persistante utilisent PostgreSQL. Aucun Redis, moteur de recherche ou courtier n'est obligatoire. Keycloak utilise une base PostgreSQL séparée.  
**Conséquences :** les travaux asynchrones utilisent une table et `FOR UPDATE SKIP LOCKED`. La recherche du MVP repose sur PostgreSQL.

## ADR-008 — Texte brut et absence de pièces jointes

**Statut :** accepté  
**Décision :** les transmissions utilisent du texte brut UTF-8 avec retours à la ligne. Les pièces jointes et le rendu HTML sont hors MVP.  
**Conséquences :** le frontend MUST rendre le texte comme texte, jamais avec une primitive HTML non sûre.

## ADR-009 — Caddy comme point d'entrée

**Statut :** accepté  
**Décision :** Caddy est le reverse proxy de référence et le seul service exposé publiquement.  
**Conséquences :** l'API, les bases et l'administration Keycloak restent sur des réseaux internes. Un remplacement reste possible si le contrat d'en-têtes et de routage est respecté.

## ADR-010 — Pas de mode hors ligne ni de bris de glace

**Statut :** accepté  
**Décision :** aucune donnée métier n'est rendue persistante pour un usage hors ligne et aucun contournement d'habilitation d'urgence n'est fourni.  
**Conséquences :** une panne réseau bloque l'usage ; l'application MUST afficher cet état sans faire croire qu'une écriture est enregistrée.

## ADR-011 — API HTTP versionnée

**Statut :** accepté  
**Décision :** l'API métier est JSON sur HTTPS, préfixée `/api/v1`. OpenAPI est la description contractuelle. Les ruptures utilisent une nouvelle version majeure d'API.  
**Conséquences :** les schémas d'erreur, pagination, concurrence et idempotence sont communs à toutes les routes.
