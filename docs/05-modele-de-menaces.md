# Modèle de menaces

## 1. Méthode et portée

Ce modèle initial utilise STRIDE, complété par les risques de confidentialité propres aux données sociales et médico-sociales. Il couvre le navigateur, le reverse proxy, l'API, Keycloak, PostgreSQL, les traitements différés, les sauvegardes, les exports, la chaîne de livraison et l'administration.

Il devra être mis à jour après les choix d'authentification, d'hébergement, de pièces jointes, de notifications et d'immutabilité de l'audit.

Échelle qualitative :

- impact : faible, significatif, élevé, critique ;
- vraisemblance : faible, moyenne, élevée ;
- priorité : combinaison nécessitant traitement immédiat, avant pilote ou ultérieur.

## 2. Actifs à protéger

- Identité, coordonnées minimales et rattachements des personnes accompagnées.
- Contenu des transmissions, tâches, relèves et accusés de lecture.
- Comptes, rôles, habilitations et sessions des professionnels.
- Journal d'audit et preuves d'intégrité.
- Sauvegardes, exports, secrets OIDC, clés TLS et clés de signature/hachage.
- Disponibilité du service lors des prises de poste et relèves.
- Code source, images de conteneurs, dépendances et chaîne de mise à jour.
- Réputation et obligations réglementaires de l'organisme.

## 3. Frontières de confiance

1. Appareil et navigateur de l'utilisateur ↔ reverse proxy.
2. Reverse proxy ↔ frontend/API/Keycloak.
3. API/worker ↔ PostgreSQL.
4. Keycloak ↔ sa base et éventuel annuaire fédéré.
5. Plateforme de production ↔ cible de sauvegarde ou d'export.
6. Chaîne de développement et registre d'images ↔ environnement de production.
7. Administrateurs d'infrastructure ↔ données et secrets.

## 4. Adversaires et erreurs envisagés

- Utilisateur externe non authentifié.
- Utilisateur authentifié curieux ou malveillant.
- Professionnel dont les droits viennent d'être retirés.
- Administrateur applicatif abusant de ses pouvoirs.
- Exploitant ou compte d'infrastructure compromis.
- Logiciel malveillant ou navigateur compromis sur un terminal.
- Attaquant réseau ou service exposé par erreur.
- Dépendance, image ou mise à jour compromise.
- Erreur humaine : mauvais destinataire, mauvais périmètre, export excessif, sauvegarde non restaurable.
- Attaquant disposant d'une sauvegarde, d'un export ou d'un ancien volume.

## 5. Scénarios de menace et mesures

| ID | Scénario | STRIDE | Risque initial | Mesures principales | Risque résiduel / vérification |
|---|---|---|---|---|---|
| M-01 | Vol de session ou de jeton par XSS | S/I/D | Critique, vraisemblance moyenne | BFF recommandé, cookie `HttpOnly`, CSP stricte, encodage, contenu riche limité, dépendances maîtrisées | Une compromission du navigateur reste possible ; tests XSS et revue CSP avant pilote |
| M-02 | Jeton OIDC forgé, destiné à un autre client ou ancien | S/E | Critique, moyenne | Validation signature, issuer, audience, expiration, nonce/PKCE ; compte local actif ; rotation des clés | Tester mauvaises audiences, algorithmes et retrait d'accès |
| M-03 | Accès horizontal par modification d'un UUID (IDOR) | E/I | Critique, élevée | Autorisation backend par ressource et périmètre, requêtes filtrées, refus par défaut, tests négatifs | Risque majeur de régression ; matrice automatisée obligatoire |
| M-04 | Élévation de privilège via rôle ou route d'administration | E | Critique, moyenne | Permissions séparées, périmètres datés, séparation admin/métier, audit, contrôles de masse | Revue à quatre yeux pour rôles sensibles à évaluer |
| M-05 | Recherche, compteur ou message d'erreur révélant l'existence d'une personne | I | Élevé, moyenne | Filtrage avant agrégation, réponses indistinguables, minimisation des résultats, quotas | Tests de canaux latéraux applicatifs |
| M-06 | Injection SQL ou contournement des filtres | T/I/E | Critique, moyenne | ORM/requêtes paramétrées, validation, aucun SQL dynamique non contrôlé, compte DB minimal | Analyse statique et tests d'injection |
| M-07 | Contenu de transmission injectant HTML/script | T/I/S | Critique, moyenne | Texte brut recommandé ; sinon liste blanche stricte côté serveur et rendu sûr | Valider le besoin de texte riche avant d'élargir |
| M-08 | CSRF sur action sensible | T/E | Élevé, moyenne | `SameSite`, jeton CSRF si cookie, vérification Origin, méthodes HTTP correctes | Tests selon modèle d'authentification retenu |
| M-09 | Modification ou suppression discrète d'une transmission | T/R | Élevé, moyenne | Versions append-only, motifs, transactions, privilèges DB, audit chaîné | DBA compromis peut agir ; ancrage externe à décider |
| M-10 | Falsification ou troncature du journal d'audit | T/R | Critique, moyenne | Compte d'écriture limité, chaîne de hachage authentifiée, vérification et export/ancrage | La chaîne détecte mais n'empêche pas la suppression de fin ; stockage séparé recommandé |
| M-11 | Désaveu d'une lecture ou d'une action | R | Significatif, moyenne | Identité individuelle, horodatage serveur, version accusée, audit et synchronisation horaire | Un accusé ne prouve pas la compréhension ; formulation juridique prudente |
| M-12 | Exposition de données dans les journaux techniques | I | Élevé, élevée | Liste blanche de champs, filtrage central, aucun corps ni jeton, accès et rétention limités | Tests automatisés et revue d'exemples de logs |
| M-13 | Export massif ou laissé accessible | I | Critique, moyenne | Permission dédiée, motif, quotas, chiffrement, expiration, audit des téléchargements | Le fichier téléchargé échappe ensuite au contrôle ; procédure organisationnelle requise |
| M-14 | Sauvegarde volée ou mal configurée | I/T | Critique, moyenne | Chiffrement avant transfert, clés séparées, contrôle d'accès, checksums, rétention | Tester restauration et rotation ; risque lié aux copies oubliées |
| M-15 | Sauvegardes inutilisables lors d'un incident | D/T | Critique, moyenne | Tests réguliers isolés, manifestes de versions, supervision locale, procédure documentée | RPO/RTO et fréquence à valider |
| M-16 | Rançongiciel détruisant production et sauvegardes accessibles | D/T | Critique, moyenne | Copie hors ligne/immuable, séparation d'identités, rétention multi-générations | Architecture de sauvegarde dépend du déployeur |
| M-17 | Déni de service par requêtes, recherche ou exports coûteux | D | Élevé, moyenne | Limites proxy/API, pagination, délais, quotas, travaux asynchrones bornés, index | Tests de charge selon capacité cible |
| M-18 | Course ou double soumission produisant des états incohérents | T | Élevé, moyenne | Transactions, contraintes DB, verrouillage optimiste, idempotence | Tests concurrents sur publication, accusé et clôture |
| M-19 | Droits retirés mais session encore utilisable | E/I | Critique, moyenne | Vérification du compte et rattachement à chaque requête, jetons courts, invalidation de session | Délai maximal à définir et tester |
| M-20 | Mauvaise attribution organisationnelle d'une personne ou transmission | I/T | Critique, moyenne | Contraintes d'organisation, choix contextualisés, confirmation, audit, interdiction des références croisées | L'erreur métier reste possible ; ergonomie et procédure importantes |
| M-21 | Compromission de Keycloak ou de son compte administrateur | S/E/I | Critique, moyenne | Interface admin restreinte, MFA admin, réseau séparé, correctifs, sauvegarde, moindre privilège | Keycloak est un composant critique à durcir et superviser |
| M-22 | Compromission de PostgreSQL ou secret DB | I/T/E | Critique, moyenne | Réseau interne, secrets montés, comptes distincts, moindre privilège, chiffrement hôte, rotation | Un DBA reste très puissant ; séparation des responsabilités |
| M-23 | Image ou dépendance compromise | T/E/I | Critique, moyenne | Versions/digests verrouillés, SBOM, scans, signatures, builds reproductibles, revue de mise à jour | Processus de réponse aux vulnérabilités requis |
| M-24 | Secret ou donnée réelle commis dans Git/CI | I | Critique, moyenne | Données synthétiques, scan de secrets, revue, règles de contribution, CI sans dump | Prévoir procédure de révocation et purge d'historique |
| M-25 | Service tiers contacté involontairement par le frontend | I | Élevé, moyenne | Aucun CDN/télémétrie, CSP `connect-src` restrictive, ressources embarquées, tests sans Internet | Vérifier dépendances et pages d'erreur |
| M-26 | Terminal perdu, partagé ou laissé ouvert | I/S | Élevé, élevée | Sessions courtes, verrouillage, bouton déconnexion, MFA, absence de stockage local sensible | Politique de terminaux relève de l'organisme |
| M-27 | Accès d'urgence contournant les droits | E/I/R | Critique, moyenne si présent | Hors MVP par défaut ; sinon motif, durée, notification, audit renforcé et revue a posteriori | Décision explicite indispensable |
| M-28 | Purge détruisant une preuve ou conservation excessive | T/I/R | Élevé, moyenne | Politiques validées, legal hold, simulation, double validation, audit, sauvegarde | Validation juridique et AIPD nécessaires |
| M-29 | Pièce jointe malveillante ou surdimensionnée | E/D/I | Critique, moyenne | Hors MVP ; si ajout : types autorisés, quotas, stockage isolé, antivirus local, téléchargement forcé | Ne pas activer sans conception dédiée |
| M-30 | Worker exécutant deux fois une tâche ou hors périmètre | T/I | Élevé, moyenne | File transactionnelle, idempotence, comptes limités, revalidation des droits ou contexte système explicite | Tests de reprises après panne |

## 6. Mesures prioritaires avant le pilote

1. Valider le modèle BFF/OIDC et réaliser une revue de flux complète.
2. Formaliser la matrice des rôles, permissions et périmètres, puis automatiser ses tests négatifs.
3. Implémenter l'audit append-only avec contrôle d'intégrité et procédure de vérification.
4. Définir les données minimales, durées de conservation et règles d'archive avec le responsable de traitement.
5. Durcir Docker Compose, Keycloak, proxy, PostgreSQL et la gestion des secrets.
6. Tester les sauvegardes et restaurations contre les objectifs RPO/RTO validés.
7. Mettre en place scans de secrets, dépendances, images et SBOM dans la chaîne de livraison.
8. Réaliser tests d'intrusion ciblés sur IDOR, élévation, XSS, CSRF, exports et isolation multi-établissements.

## 7. Hypothèses et risques acceptés provisoirement

- Un déploiement Docker Compose sur un hôte unique n'offre pas de haute disponibilité.
- Un administrateur racine de l'hôte peut, techniquement, accéder aux processus, volumes et secrets ; la séparation des responsabilités et le chiffrement de disque réduisent mais n'annulent pas ce risque.
- L'audit chaîné dans la même base détecte certaines altérations mais n'est pas équivalent à un stockage légalement probant ou WORM.
- Le MVP n'offre pas de mode hors ligne ; une perte réseau interrompt le service.
- Le produit fournit des mécanismes techniques, mais l'organisme reste responsable des habilitations, terminaux, sauvegardes, conservation, information et gestion d'incident.

## 8. Validation du modèle

À chaque décision structurante, organiser un atelier court associant métier, sécurité, protection des données et exploitation. Pour chaque menace : confirmer l'actif, le scénario, la mesure, le propriétaire, l'échéance et la preuve de vérification. Le registre doit être revu avant chaque version majeure et après tout incident significatif.
