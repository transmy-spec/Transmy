# Utilisateurs et parcours

## 1. Acteurs

### Professionnel de terrain

Éducateur, accompagnant, aide-soignant, infirmier ou autre intervenant autorisé. Il consulte les informations nécessaires à sa prise de poste, rédige des transmissions, accuse leur lecture et gère des tâches dans le périmètre de ses unités.

### Responsable d'équipe ou de service

Dispose des fonctions du professionnel et organise le travail : relève, suivi des transmissions importantes, attribution des tâches, contrôle des échéances et supervision de son périmètre.

### Administrateur d'établissement

Gère la structure locale, les rattachements, les rôles et les habilitations de son établissement. Il ne reçoit pas automatiquement le droit de lire le contenu métier sensible.

### Administrateur de l'organisation

Configure les établissements et les paramètres communs, délègue l'administration et supervise l'exploitation. Ses pouvoirs techniques et ses droits métier doivent rester séparés.

### Auditeur ou référent conformité

Consulte, dans un périmètre explicitement autorisé, les événements d'audit, les exports de contrôle et l'état des politiques de conservation. Il n'accède au contenu métier que si cela est indispensable et autorisé.

### Exploitant technique

Déploie, met à jour, sauvegarde, restaure et surveille les composants. Son accès à l'infrastructure ne doit pas lui conférer un accès applicatif ordinaire aux dossiers.

### Personne accompagnée ou représentant

Acteur externe indirect au MVP. Une demande d'accès, de rectification ou d'information est instruite par l'organisme ; aucun portail dédié n'est prévu dans le MVP.

### Administrateur d'identité

Administre Keycloak : comptes, authentification, politiques de mot de passe, second facteur et éventuellement fédération d'annuaire. Ce rôle est distinct des habilitations métier de l'application.

## 2. Parcours principaux

### 2.1 Prendre son poste et effectuer la relève

1. Le professionnel ouvre l'application sur ordinateur, tablette ou téléphone.
2. Il s'authentifie auprès de Keycloak avec OpenID Connect.
3. Le backend associe l'identité authentifiée au compte applicatif actif et recalcule son périmètre effectif.
4. Le professionnel choisit, si nécessaire, son établissement, son service ou son unité de travail.
5. Il ouvre la relève correspondant à son périmètre et à une période donnée.
6. Il voit les transmissions non lues, importantes ou urgentes, les tâches échues ou proches de l'échéance et les éléments sélectionnés pour la relève.
7. Il ouvre les éléments utiles ; les accusés de lecture sont enregistrés de manière explicite selon la règle retenue.
8. Il peut ajouter une note de relève ou signaler un point restant à traiter, selon ses droits.

Résultat attendu : le professionnel identifie rapidement les informations et actions prioritaires sans accéder à un périmètre non autorisé.

### 2.2 Retrouver une personne accompagnée

1. Le professionnel recherche une personne uniquement dans son périmètre autorisé.
2. La recherche retourne le minimum d'informations permettant d'éviter les homonymies.
3. Il ouvre la fiche et consulte les transmissions actives, tâches et éléments de contexte accessibles.
4. Toute consultation sensible pertinente est auditée.

Cas particuliers : homonymie, personne archivée, changement d'unité, rattachement simultané à plusieurs services, accès temporaire ou exceptionnel.

### 2.3 Rédiger et publier une transmission

1. Depuis une personne accompagnée, le professionnel crée un brouillon.
2. Il choisit une catégorie et un niveau d'importance, puis rédige un contenu factuel.
3. Il indique éventuellement une échéance, crée une tâche liée ou sélectionne l'élément pour la relève.
4. Le frontend vérifie les champs ; le backend valide les données, le périmètre et chaque permission.
5. À la publication, l'auteur et l'horodatage sont figés et un événement d'audit est ajouté.
6. Une correction ultérieure crée une nouvelle version ou un addendum traçable ; l'original demeure conservé selon la politique retenue.

### 2.4 Lire et accuser réception

1. Le professionnel ouvre une transmission autorisée.
2. Il déclenche explicitement « Marquer comme lue » ; l'ouverture seule ne vaut pas accusé de lecture.
3. Le système conserve l'identité, la date, la version lue et le contexte utile.
4. L'auteur ou le responsable peut consulter la couverture de lecture sans exposer de données hors de son périmètre.
5. Une nouvelle version substantielle peut invalider l'accusé précédent selon la règle choisie.

### 2.5 Créer et suivre une tâche

1. Un professionnel autorisé crée une tâche autonome ou liée à une transmission et à une personne.
2. Il définit une échéance et l'assigne à un utilisateur, un rôle ou une unité selon les options retenues.
3. Le destinataire la prend en charge, la termine ou la réattribue si son habilitation le permet.
4. Les retards et échéances proches apparaissent dans la relève.
5. Chaque changement d'état, d'échéance et d'attribution est historisé.

### 2.6 Préparer et conduire une relève d'équipe

1. Un responsable crée une relève pour un périmètre et une plage temporelle.
2. Le système propose les éléments importants, non lus, en retard ou explicitement sélectionnés.
3. Le responsable ajoute ou retire des éléments selon ses droits, sans copier leur contenu.
4. Pendant la relève, l'équipe passe les éléments en revue et documente les suites utiles.
5. La relève est clôturée ; sa composition et sa clôture sont auditables.

Une relève référence les transmissions et tâches : elle ne duplique pas les contenus, afin d'éviter des divergences.

### 2.7 Administrer une structure et les habilitations

1. L'administrateur crée ou désactive établissements, services et unités dans son périmètre.
2. L'identité est provisionnée dans Keycloak, puis liée à un compte applicatif.
3. L'administrateur attribue des rattachements datés et des rôles applicatifs limités à des périmètres.
4. Le backend refuse les combinaisons incompatibles et journalise les changements.
5. À un départ, le compte ou ses rattachements sont désactivés sans supprimer l'historique.

### 2.8 Archiver une personne accompagnée

1. Un utilisateur habilité demande l'archivage avec un motif.
2. Le backend vérifie les tâches ouvertes et les règles de conservation.
3. La personne disparaît des vues courantes, mais ses données ne sont pas supprimées.
4. La consultation d'une archive nécessite une habilitation dédiée et est auditée.
5. La restitution ou la suppression à échéance suit une procédure contrôlée restant à préciser.

### 2.9 Auditer un événement

1. L'auditeur sélectionne une période, un type d'événement et un périmètre autorisé.
2. Il consulte les métadonnées d'audit et, seulement si autorisé, les références métier nécessaires.
3. Il exporte éventuellement un relevé signé ou vérifiable.
4. La consultation et l'export du journal sont eux-mêmes journalisés.

### 2.10 Sauvegarder et restaurer

1. L'exploitant déclenche ou contrôle une sauvegarde chiffrée de PostgreSQL et des éléments de configuration nécessaires.
2. La sauvegarde est copiée vers une cible administrée par l'organisme, sans dépendance cloud obligatoire.
3. Une restauration est testée régulièrement dans un environnement isolé.
4. Le test vérifie l'intégrité, la version applicative compatible, les secrets requis et les objectifs RPO/RTO.
5. Les résultats sont consignés sans données sensibles dans les journaux d'exploitation.

## 3. Parcours transversaux et situations dégradées

- Session expirée : retour vers Keycloak, sans perdre un brouillon local au-delà de la politique de sécurité retenue.
- Panne réseau : message explicite ; aucune promesse de mode hors ligne dans le MVP.
- Conflit de modification : contrôle de version optimiste et proposition de rechargement.
- Accès retiré pendant une session : vérification backend à chaque requête et refus immédiat dès prise en compte.
- Urgence : aucun mécanisme « bris de glace » n'est inclus dans le MVP.
- Erreur sur une transmission publiée : addendum ou nouvelle version, jamais écrasement opaque.
- Homonymie : affichage de discriminants limités et non ambigus définis par l'organisme.
- Changement d'affectation : droits datés, sans réécriture de l'historique.

## 4. Hors périmètre présumé du MVP

- Dossier usager informatisé complet ou dossier médical.
- Prescription, circuit du médicament et facturation.
- Messagerie instantanée générale, visioconférence ou notifications par service tiers.
- Portail autonome pour les personnes accompagnées.
- Application mobile native et fonctionnement hors ligne.
- Interopérabilité sectorielle avancée tant que les formats cibles ne sont pas validés.
