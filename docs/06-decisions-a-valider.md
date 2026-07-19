# Décisions validées

**Statut global : validé le 18 juillet 2026 par le porteur du projet.**

Toutes les recommandations ci-dessous sont adoptées comme orientations de référence du MVP. Les formulations « recommandation » sont conservées pour documenter l'option qui a été choisie.

Certaines décisions portent sur une méthode de détermination plutôt que sur une valeur immédiatement disponible. Pour celles-ci, le principe est validé mais le paramètre reste à renseigner avec l'établissement pilote, le DPO, le conseil juridique, la sécurité ou l'exploitation. Cela concerne en particulier DEC-004, DEC-005, DEC-011, DEC-014 à DEC-018, DEC-024, DEC-025, DEC-027 et DEC-029.

## 1. Orientations structurantes validées

### DEC-001 — Périmètre de mutualisation

**Question :** une installation héberge-t-elle une seule organisation juridique avec plusieurs établissements, ou plusieurs organisations totalement isolées ?

**Recommandation :** une organisation par installation pour le MVP, tout en conservant `organization_id` dans le modèle. Une mutualisation multi-organisations augmente fortement les enjeux d'isolation.

### DEC-002 — Hiérarchie organisationnelle

**Question :** la structure établissement → service → unité couvre-t-elle tous les cas, et une unité peut-elle appartenir à plusieurs services ?

**Recommandation :** hiérarchie stricte pour le MVP, avec rattachements datés.

### DEC-003 — Rattachement des personnes

**Question :** une personne accompagnée peut-elle relever simultanément de plusieurs unités ou établissements, et qui conserve l'accès après son transfert ?

**Recommandation :** plusieurs affectations datées possibles, accès courant par affectation active et accès historique via permission explicite.

### DEC-004 — Données minimales d'identification

**Question :** quels champs sont indispensables pour identifier sans ambiguïté une personne et gérer les homonymes ?

**Recommandation :** définir ce jeu avec les métiers et le DPO avant de figer le schéma ; éviter tout identifiant national par défaut.

### DEC-005 — Taxonomie des transmissions

**Question :** quelles catégories initiales, quels niveaux d'importance et quelles règles obligatoires par catégorie ?

**Recommandation :** référentiel administrable avec codes stables et désactivation sans suppression ; démarrer avec peu de valeurs validées en atelier.

### DEC-006 — Correction d'une transmission

**Question :** autorise-t-on une nouvelle version, uniquement un addendum, ou les deux ? Qui peut corriger et pendant combien de temps ?

**Recommandation :** nouvelle version motivée, original conservé, historique visible ; aucune suppression ordinaire.

### DEC-007 — Signification de l'accusé de lecture

**Question :** l'accusé est-il explicite ou automatique, porte-t-il sur une version et une nouvelle version impose-t-elle une nouvelle lecture ?

**Recommandation :** action explicite, liée à la version ; nouvelle version substantielle à accuser de nouveau.

### DEC-008 — Destinataires attendus

**Question :** une transmission cible-t-elle tous les professionnels habilités du périmètre, ou des utilisateurs, rôles ou équipes précis ?

**Recommandation :** périmètre d'unité par défaut et destinataires ciblés uniquement si les métiers ont besoin d'un suivi nominatif.

### DEC-009 — Modèle des tâches

**Question :** les tâches peuvent-elles être assignées à un utilisateur, une fonction, une unité ou plusieurs acteurs ? Quelles règles de réattribution et de clôture ?

**Recommandation :** une responsabilité active à la fois, utilisateur ou unité, avec historique complet.

### DEC-010 — Contenu exact d'une relève

**Question :** quelles règles sélectionnent automatiquement les éléments, qui peut les modifier et que signifie « clôturer » ?

**Recommandation :** références aux éléments importants, non lus, en retard ou choisis ; clôture figée et réouverture habilitée.

### DEC-011 — Matrice des rôles et séparation des responsabilités

**Question :** quels rôles réels existent, sur quels périmètres, et quelles combinaisons sont interdites ?

**Recommandation :** valider une matrice métier avant le développement ; séparer administration de structure, accès métier, audit et exploitation.

### DEC-012 — Accès exceptionnel (« bris de glace »)

**Question :** faut-il permettre un accès d'urgence hors habilitation normale ?

**Recommandation :** hors MVP. S'il est obligatoire : motif, durée courte, périmètre borné, alerte, audit renforcé et revue systématique.

### DEC-013 — Architecture d'authentification web

**Question :** backend-for-frontend avec cookie de session ou SPA détenant les jetons OIDC ?

**Recommandation :** BFF avec Authorization Code + PKCE et cookie `HttpOnly`, compte tenu de la sensibilité des données.

### DEC-014 — Niveau d'immutabilité de l'audit

**Question :** suffit-il de détecter l'altération dans PostgreSQL, ou faut-il résister à un administrateur de l'hôte avec ancrage séparé/WORM ?

**Recommandation :** append-only et chaîne cryptographique dans le MVP, plus export/ancrage local séparé configurable. Faire valider la valeur probatoire attendue.

### DEC-015 — Conservation, archivage et suppression

**Question :** quelles durées s'appliquent aux personnes, transmissions, tâches, relèves, audits, exports et sauvegardes ? Quelles suspensions de purge ?

**Recommandation :** aucune purge automatique avant validation juridique, AIPD et procédure testée ; politiques distinctes par type de données.

### DEC-016 — Objectifs de continuité

**Question :** quels RPO, RTO, niveau de disponibilité et durée maximale d'indisponibilité pendant une mise à jour ?

**Recommandation :** les fixer avec un établissement pilote ; ils déterminent la stratégie PostgreSQL, de sauvegarde et d'exploitation.

### DEC-017 — Volumétrie de référence

**Question :** combien d'établissements, utilisateurs simultanés, personnes actives, transmissions quotidiennes et années d'historique ?

**Recommandation :** définir petit, nominal et pic afin de dimensionner les index, tests et ressources Compose.

### DEC-018 — Cadre réglementaire et hébergement

**Question :** les données traitées seront-elles qualifiées de données de santé et quelles obligations d'hébergement, certification, journalisation ou localisation en découlent dans les contextes visés ?

**Recommandation :** analyse juridique et sécurité formelle avant pilote ; ne pas présenter l'auto-hébergement comme suffisant en soi.

## 2. Orientations complémentaires validées

### DEC-019 — Pièces jointes

**Question :** sont-elles nécessaires au MVP ?

**Recommandation :** non. Leur ajout impose stockage, quotas, antivirus local, formats autorisés, prévisualisation sûre et conservation.

### DEC-020 — Texte riche

**Question :** le contenu doit-il supporter mise en forme, mentions ou liens ?

**Recommandation :** texte brut enrichi de retours à la ligne pour le MVP afin de réduire le risque XSS et les ambiguïtés d'archivage.

### DEC-021 — Notifications

**Question :** uniquement dans l'application, ou aussi par courriel/SMS/outil institutionnel ?

**Recommandation :** centre de notifications interne pour le MVP ; intégrations facultatives, locales et sans contenu sensible.

### DEC-022 — PostgreSQL Row-Level Security

**Question :** faut-il activer RLS dès le MVP comme défense en profondeur ?

**Recommandation :** réaliser un prototype sur les tables critiques, puis l'activer seulement avec rôles DB séparés et tests systématiques.

### DEC-023 — Reverse proxy de référence

**Question :** quel proxy documenter et inclure dans Compose ?

**Recommandation :** choisir un seul proxy de référence simple à durcir, tout en documentant le contrat HTTP pour permettre un remplacement.

### DEC-024 — Stratégie de sauvegarde de référence

**Question :** dumps chiffrés périodiques ou sauvegarde physique et archivage WAL ? Vers quelle cible locale ?

**Recommandation :** décision après RPO/RTO et volumétrie ; fournir au minimum une cible filesystem et une interface vers stockage auto-hébergé.

### DEC-025 — Exports métier

**Question :** quels formats, finalités, approbations et limites sont nécessaires ?

**Recommandation :** aucun export de masse générique ; exports précisément finalisés, temporaires, marqués et audités.

### DEC-026 — Internationalisation et fuseaux horaires

**Question :** français uniquement au MVP ? Des établissements peuvent-ils utiliser des fuseaux différents ?

**Recommandation :** interface française avec chaînes externalisées ; stockage UTC et fuseau par établissement.

### DEC-027 — Navigateurs et appareils pris en charge

**Question :** versions minimales, tablettes institutionnelles, Safari/iOS et contraintes de terminaux ?

**Recommandation :** deux dernières versions majeures des navigateurs courants, à confirmer avec le parc réel du pilote.

### DEC-028 — Mode déconnecté

**Question :** un fonctionnement sans réseau est-il nécessaire ?

**Recommandation :** hors MVP à cause des risques de données locales, conflits et révocation des droits.

### DEC-029 — Supervision locale

**Question :** quelles métriques et alertes, avec quel outil déjà présent chez les déployeurs ?

**Recommandation :** endpoints et journaux standards, profil Compose optionnel, aucun envoi externe.

### DEC-030 — Licence et gouvernance open source

**Question :** AGPL-3.0 est-elle confirmée ? Qui détient les droits, accepte les contributions et gère les vulnérabilités ?

**Recommandation :** revue juridique des dépendances, confirmation AGPL-3.0, politique de contribution, DCO ou CLA selon gouvernance, `SECURITY.md` et procédure d'embargo.

## 3. Travaux d'application des décisions

1. Atelier métier : préciser et appliquer DEC-002 à DEC-011 et DEC-017.
2. Atelier protection des données/juridique : renseigner les paramètres de DEC-004, DEC-014, DEC-015, DEC-018 et DEC-025, puis appliquer DEC-030.
3. Atelier sécurité/architecture : traduire DEC-001, DEC-012 à DEC-016, DEC-019 à DEC-024 et DEC-028 en spécifications techniques et critères d'acceptation.
4. Atelier exploitation et pilote : chiffrer DEC-016, DEC-017, DEC-024, DEC-027 et DEC-029, puis appliquer le choix de référence de DEC-023.

Les décisions structurantes devront être converties en ADR datés indiquant contexte, option retenue, conséquences et responsables au moment de la conception détaillée. Un changement ultérieur devra passer par un nouvel ADR et ne devra pas réécrire silencieusement cette validation.
