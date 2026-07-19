# Exigences fonctionnelles et non fonctionnelles

Les identifiants sont stables et destinés à alimenter les futurs critères d'acceptation. « Doit » indique une exigence du MVP ; « devrait » une cible recommandée à confirmer.

## 1. Exigences fonctionnelles

### Identité et comptes

- **EF-ID-001** — Le système doit authentifier les utilisateurs via OpenID Connect avec Keycloak.
- **EF-ID-002** — Chaque action humaine doit être rattachée à un compte individuel ; les comptes partagés sont interdits.
- **EF-ID-003** — Le compte applicatif doit être lié de façon unique et stable à l'émetteur et au sujet OIDC, sans utiliser l'adresse électronique comme identifiant durable.
- **EF-ID-004** — Le système doit refuser un compte applicatif désactivé même si le jeton OIDC est encore valide.
- **EF-ID-005** — La création, l'activation, la désactivation et les changements d'habilitation doivent être audités.
- **EF-ID-006** — Le système doit gérer les rattachements datés d'un utilisateur à un ou plusieurs périmètres organisationnels.

### Organisation multi-établissements

- **EF-ORG-001** — Le système doit gérer une organisation contenant plusieurs établissements.
- **EF-ORG-002** — Un établissement doit contenir des services et les services des unités, avec possibilité d'adapter cette hiérarchie après validation.
- **EF-ORG-003** — Chaque objet métier doit être rattaché à un périmètre organisationnel explicite.
- **EF-ORG-004** — La désactivation d'une structure doit préserver l'historique et empêcher les nouvelles saisies dans cette structure.
- **EF-ORG-005** — Toute requête de lecture ou d'écriture doit être limitée au périmètre effectif de l'utilisateur côté backend.

### Personnes accompagnées

- **EF-PER-001** — Le système doit créer, consulter, modifier de façon tracée et archiver une personne accompagnée.
- **EF-PER-002** — Une personne doit pouvoir être rattachée de manière datée à une ou plusieurs unités, sous réserve de validation métier.
- **EF-PER-003** — La recherche doit être limitée au périmètre autorisé et retourner un jeu minimal de données.
- **EF-PER-004** — Le système doit fournir des moyens de distinguer les homonymes sans exposer plus de données que nécessaire.
- **EF-PER-005** — Une personne archivée doit être exclue par défaut des vues courantes.
- **EF-PER-006** — La consultation d'une personne archivée doit nécessiter une permission dédiée et être auditée.
- **EF-PER-007** — La fusion de doublons n'est pas incluse sans règles explicites de traçabilité et de réversibilité.

### Transmissions

- **EF-TRN-001** — Un utilisateur autorisé doit pouvoir créer un brouillon puis publier une transmission concernant une personne accompagnée.
- **EF-TRN-002** — Une transmission doit comporter au minimum un auteur, un périmètre, une personne, une catégorie, un niveau d'importance, un contenu, un statut et des horodatages serveur.
- **EF-TRN-003** — Catégories et niveaux d'importance doivent être administrables ou définis par une configuration versionnée, selon la décision retenue.
- **EF-TRN-004** — Les catégories désactivées doivent rester visibles sur l'historique mais ne plus être sélectionnables.
- **EF-TRN-005** — Une transmission publiée ne doit pas être supprimée ou écrasée silencieusement.
- **EF-TRN-006** — Toute correction doit conserver l'auteur, la date, le motif et le lien avec la version antérieure.
- **EF-TRN-007** — Le backend doit vérifier l'autorisation sur la personne, le périmètre et l'action lors de chaque lecture et écriture.
- **EF-TRN-008** — La liste doit pouvoir être filtrée au minimum par période, personne, catégorie, importance, statut de lecture et périmètre.
- **EF-TRN-009** — Le système doit permettre d'indiquer qu'une transmission doit apparaître dans une relève.
- **EF-TRN-010** — Les pièces jointes sont hors périmètre par défaut jusqu'à validation de leurs risques, quotas et règles antivirus.

### Accusés de lecture

- **EF-LEC-001** — Le système doit enregistrer, par utilisateur et par version, un accusé de lecture horodaté par le serveur.
- **EF-LEC-002** — Un accusé ne doit pouvoir être créé que si l'utilisateur est autorisé à lire l'objet.
- **EF-LEC-003** — Le système doit distinguer « non lu » de « non concerné » lorsque les destinataires attendus sont définis.
- **EF-LEC-004** — Les utilisateurs habilités doivent pouvoir consulter l'état agrégé ou nominatif des accusés selon leur permission.
- **EF-LEC-005** — Un accusé existant ne doit pas être supprimable par un utilisateur ordinaire.

### Tâches et échéances

- **EF-TAC-001** — Un utilisateur autorisé doit pouvoir créer une tâche liée ou non à une transmission et, si nécessaire, à une personne.
- **EF-TAC-002** — Une tâche doit avoir un titre, un état, un créateur, un périmètre et éventuellement une échéance et un responsable.
- **EF-TAC-003** — Les états minimaux sont à faire, en cours, terminée et annulée.
- **EF-TAC-004** — Le changement d'état, d'échéance ou d'attribution doit être historisé.
- **EF-TAC-005** — Les vues doivent faire ressortir les tâches échues et à échéance proche.
- **EF-TAC-006** — Le backend doit empêcher une attribution à un acteur hors périmètre ou non habilité.
- **EF-TAC-007** — Le mécanisme de rappel ne doit dépendre d'aucun service cloud ; les notifications externes sont optionnelles et désactivées par défaut.

### Relève d'équipe

- **EF-REL-001** — Un utilisateur habilité doit pouvoir créer une relève associée à un périmètre et une plage temporelle.
- **EF-REL-002** — Une relève doit référencer des transmissions et tâches existantes sans dupliquer leur contenu.
- **EF-REL-003** — Le système doit proposer les éléments importants, non lus, sélectionnés ou en retard selon des règles explicites.
- **EF-REL-004** — La clôture doit enregistrer l'auteur, l'heure et la composition de la relève.
- **EF-REL-005** — Une relève clôturée ne doit pas être modifiée sans trace ; la réouverture éventuelle requiert une permission dédiée.

### Rôles et habilitations

- **EF-AUT-001** — Les autorisations doivent combiner rôle, action, type de ressource et périmètre organisationnel.
- **EF-AUT-002** — Le refus doit être la valeur par défaut en l'absence de règle autorisante explicite.
- **EF-AUT-003** — Les contrôles doivent être centralisés dans le backend et appliqués à chaque route et service métier.
- **EF-AUT-004** — Le frontend peut masquer les actions interdites, mais ne doit jamais constituer un contrôle de sécurité.
- **EF-AUT-005** — L'administration technique ne doit pas accorder implicitement l'accès aux données métier.
- **EF-AUT-006** — Les habilitations doivent être datées, désactivables et auditables.
- **EF-AUT-007** — Les exports, archives, audits et administrations d'habilitations doivent posséder des permissions distinctes.
- **EF-AUT-008** — Les tests doivent démontrer l'absence d'accès horizontal entre périmètres et vertical entre rôles.

### Audit

- **EF-AUD-001** — Le système doit journaliser les authentifications applicatives pertinentes, refus d'accès, consultations sensibles, créations, corrections, archivages, exports et changements d'habilitation.
- **EF-AUD-002** — Chaque événement doit contenir un identifiant, un horodatage serveur, l'acteur, l'action, le type et l'identifiant de cible, le périmètre, le résultat et un identifiant de corrélation.
- **EF-AUD-003** — Le journal doit éviter de contenir le corps des transmissions, jetons, secrets et données non nécessaires.
- **EF-AUD-004** — L'API applicative ne doit offrir aucune mise à jour ni suppression d'événement d'audit.
- **EF-AUD-005** — L'intégrité et l'ordre des événements doivent être vérifiables par une chaîne de hachage ou un mécanisme équivalent.
- **EF-AUD-006** — Les accès au journal et ses exports doivent eux-mêmes être audités.
- **EF-AUD-007** — Les événements doivent pouvoir être exportés dans un format ouvert avec éléments de vérification d'intégrité.

### Archivage, conservation et sauvegarde

- **EF-ARC-001** — L'archivage doit être distinct de la suppression et réversible uniquement selon une procédure habilitée.
- **EF-ARC-002** — Les politiques de conservation doivent être configurables par catégorie de données et contexte réglementaire après validation.
- **EF-ARC-003** — Les purges doivent respecter les liens, obligations de conservation, suspensions de suppression et exigences d'audit.
- **EF-SAV-001** — Une procédure documentée doit sauvegarder PostgreSQL, les configurations nécessaires et les éléments cryptographiques requis.
- **EF-SAV-002** — Les sauvegardes doivent être chiffrées, vérifiables et stockables sur une infrastructure contrôlée par l'organisme.
- **EF-SAV-003** — La restauration doit être testable et documentée, avec preuve de tests périodiques.
- **EF-SAV-004** — Aucun fournisseur cloud ne doit être obligatoire pour sauvegarder ou restaurer.

### Administration et exports

- **EF-ADM-001** — Les écrans d'administration doivent appliquer les mêmes contraintes de périmètre que les API.
- **EF-ADM-002** — Les opérations de masse doivent présenter un récapitulatif et être auditées.
- **EF-EXP-001** — Les exports métier ne sont disponibles qu'avec une permission dédiée, un motif et une limite de périmètre.
- **EF-EXP-002** — Les fichiers exportés doivent comporter un marquage de sensibilité et être générés avec une durée de disponibilité limitée.

## 2. Exigences non fonctionnelles

### Sécurité et confidentialité

- **ENF-SEC-001** — Les communications doivent être protégées par TLS en production ; le déploiement doit documenter la terminaison TLS.
- **ENF-SEC-002** — Le backend doit valider signature, émetteur, audience, expiration et propriétés requises des jetons OIDC.
- **ENF-SEC-003** — Les secrets ne doivent pas être intégrés aux images, au dépôt, aux journaux ou au frontend.
- **ENF-SEC-004** — Les cookies éventuels doivent être `Secure`, `HttpOnly` et avec un `SameSite` adapté ; la stratégie CSRF doit être explicite.
- **ENF-SEC-005** — Les entrées doivent être validées par schéma ; les sorties et contenus riches doivent prévenir XSS, injections SQL et injections de journaux.
- **ENF-SEC-006** — Les en-têtes HTTP de sécurité, une politique CSP et des limites de taille doivent être configurés.
- **ENF-SEC-007** — Les images de conteneurs doivent s'exécuter sans privilèges inutiles, avec systèmes de fichiers en lecture seule lorsque possible.
- **ENF-SEC-008** — Les dépendances et images doivent être verrouillées, analysables et accompagnées d'une nomenclature logicielle (SBOM).
- **ENF-SEC-009** — Les sauvegardes doivent être chiffrées hors ligne ou côté client avec rotation des clés documentée.
- **ENF-SEC-010** — Aucune télémétrie, balise distante, police distante ou appel réseau tiers ne doit être activé par défaut.
- **ENF-SEC-011** — Le système doit limiter les tentatives et volumes abusifs sur les routes sensibles, en coordination avec Keycloak et le proxy.
- **ENF-SEC-012** — Les horloges des hôtes doivent être synchronisées pour garantir la cohérence de l'audit et d'OIDC.

### Protection des données

- **ENF-PRI-001** — Les données collectées et affichées doivent être limitées à la finalité opérationnelle.
- **ENF-PRI-002** — Les environnements de développement, démonstration et test ne doivent contenir aucune donnée réelle, pseudonymisée ou issue d'une production.
- **ENF-PRI-003** — Les jeux de données de test doivent être synthétiques, manifestement fictifs et reproductibles.
- **ENF-PRI-004** — Les journaux techniques ne doivent pas contenir le contenu métier, des jetons ou des identifiants excessifs.
- **ENF-PRI-005** — Le déploiement doit permettre à l'organisme de définir information, conservation, droits des personnes et procédure d'incident.

### Disponibilité, intégrité et reprise

- **ENF-DIS-001** — Tous les services nécessaires au fonctionnement doivent pouvoir être déployés par Docker Compose sur une infrastructure sans accès Internet permanent.
- **ENF-DIS-002** — Les composants doivent exposer des contrôles de santé et démarrer selon leurs dépendances réelles.
- **ENF-DIS-003** — Les écritures métier et d'audit associées doivent être transactionnelles autant que possible.
- **ENF-DIS-004** — Les mises à jour concurrentes doivent utiliser un verrouillage optimiste ou une protection équivalente.
- **ENF-DIS-005** — Les objectifs RPO, RTO, disponibilité et fréquence des tests de restauration doivent être validés avant production.
- **ENF-DIS-006** — Les migrations de schéma doivent être versionnées, sauvegardables et accompagnées d'une procédure de retour ou de restauration.

### Performance et capacité

- **ENF-PERF-001** — Les cibles de charge doivent être définies en nombre d'utilisateurs simultanés, personnes actives, transmissions quotidiennes et durée de conservation.
- **ENF-PERF-002** — À charge nominale validée, 95 % des lectures courantes devraient répondre en moins d'une seconde côté API, hors réseau et authentification.
- **ENF-PERF-003** — Les listes doivent être paginées côté serveur et les recherches indexées.
- **ENF-PERF-004** — Les exports et traitements lourds doivent être bornés et exécutés hors du cycle de requête s'ils dépassent un seuil à définir.

### Accessibilité et ergonomie

- **ENF-ACC-001** — L'interface doit viser la conformité WCAG 2.2 niveau AA et RGAA applicable.
- **ENF-ACC-002** — Toutes les fonctions essentielles doivent être utilisables au clavier et avec un lecteur d'écran.
- **ENF-ACC-003** — L'importance ne doit jamais être transmise par la couleur seule.
- **ENF-ACC-004** — L'interface doit être responsive de 320 px de large aux écrans de bureau courants, sans perte de fonction essentielle.
- **ENF-ACC-005** — Les cibles tactiles, messages d'erreur, confirmations et états de chargement doivent être explicites.
- **ENF-ACC-006** — Le français est la langue initiale ; les textes devraient être externalisés pour permettre l'internationalisation.

### Maintenabilité et qualité

- **ENF-MAI-001** — Le backend doit utiliser FastAPI et PostgreSQL ; le frontend Vue 3.
- **ENF-MAI-002** — L'API doit publier une spécification OpenAPI versionnée et ne pas exposer les routes d'administration sans contrôle.
- **ENF-MAI-003** — Les couches présentation, métier, autorisation et persistance doivent être séparées.
- **ENF-MAI-004** — Les tests doivent couvrir règles métier, contrôles d'accès, migrations et principaux parcours de bout en bout.
- **ENF-MAI-005** — Les tests de sécurité doivent inclure matrices d'autorisation, IDOR, injections, XSS, CSRF selon l'architecture et isolation des périmètres.
- **ENF-MAI-006** — Les versions prises en charge, procédures de mise à niveau et politique de divulgation de vulnérabilités doivent être documentées.
- **ENF-MAI-007** — Le code source devrait être publié sous AGPL-3.0 après validation juridique des dépendances et contenus.

### Exploitabilité et portabilité

- **ENF-OPS-001** — Docker Compose doit fournir un déploiement reproductible de l'application, PostgreSQL et Keycloak ; le proxy TLS peut être inclus ou documenté.
- **ENF-OPS-002** — Les images doivent être configurables par variables ou secrets montés, sans reconstruction.
- **ENF-OPS-003** — Les journaux doivent être structurés, horodatés et exploitables localement sans service externe.
- **ENF-OPS-004** — Les métriques techniques locales éventuelles doivent être désactivables et ne contenir aucune donnée métier ; elles ne sont jamais envoyées à l'extérieur.
- **ENF-OPS-005** — Le système doit documenter installation, sauvegarde, restauration, rotation des secrets, mise à jour et diagnostic.
- **ENF-OPS-006** — Le déploiement doit fonctionner sur une architecture de référence à préciser et déclarer les plateformes d'images prises en charge.

## 3. Critères de sortie du MVP

Le MVP peut être déclaré prêt pour un pilote lorsque :

- tous les parcours principaux disposent de critères d'acceptation automatisés ou documentés ;
- la matrice d'autorisation est validée et testée positivement et négativement ;
- le modèle de menaces a été revu et les risques critiques traités ;
- une installation propre, une mise à niveau, une sauvegarde et une restauration ont été répétées ;
- un audit d'accessibilité et un audit de sécurité indépendants ont été planifiés ou réalisés selon le niveau de mise en production ;
- les orientations validées du registre ont été traduites en critères d'acceptation et les paramètres propres au pilote ont été renseignés ;
- l'AIPD, les durées de conservation et les responsabilités du déploiement ont été examinées par l'organisme pilote.
