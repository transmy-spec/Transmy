# Préparation de production 0.27.0

Dernière campagne technique : 23 août 2026.

Cette version constitue la première version stable on-premise de Transmy. Son socle technique est
validé par les contrôles automatisés du dépôt. Chaque organisme reste responsable de qualifier
son infrastructure et de valider les critères humains, juridiques et organisationnels ci-dessous
avant d'y introduire des données réelles.

## Résultats techniques

| Contrôle | Résultat | Preuve |
|---|---|---|
| Backend | Conforme | Ruff, mypy, 91 tests, couverture supérieure à 90 % |
| Frontend | Conforme | ESLint sans erreur, 3 tests Vitest, build TypeScript/Vite |
| Dépendances npm | Conforme | `npm audit --audit-level=high` : 0 vulnérabilité |
| Dépendances Python | Conforme | `pip-audit` : 0 vulnérabilité connue |
| Images applicatives | Conforme | Frontend : 0 CVE High/Critical corrigible ; API : `pip-audit` du runtime à 0, deux faux positifs BuildKit absents du runtime vérifiés avec `pip show` |
| Sécurité HTTP | Conforme | CSP/HSTS/en-têtes présents, accès anonymes refusés |
| Charge synthétique | Conforme | 600 requêtes, 0 échec, p95 11,15 ms, 10 VU pendant 30 s |
| Sauvegarde | Conforme | archive chiffrée AES-256-CBC/PBKDF2 et somme SHA-256 |
| Restauration | Conforme | deux bases temporaires restaurées et contrôlées en 5 s |
| Exploitation | Conforme | services publics, sauvegarde et rapport de restauration contrôlés |
| Paquet Debian | Conforme | paquet 0.27.0 de test construit et structure validée |
| Profil production | Conforme | aucun compte métier générique, aucune donnée fictive |

Les mesures de charge décrivent uniquement la machine de développement utilisée pour cette
campagne. Elles ne constituent pas un engagement de capacité pour un établissement.

## Corrections issues de la campagne

- réconciliation Keycloak des installations existantes ;
- utilisation du `subject` Keycloak lors de l'activation administrateur ;
- résolution réelle de l'adresse Caddy dans le contrôle d'exploitation ;
- mise à niveau des paquets Alpine de l'image frontend ;
- verrouillage de `brace-expansion` sur une version corrigée ;
- mise à jour des dépendances transitives frontend signalées depuis la campagne initiale ;
- passage à `cryptography` 50 après publication d'un correctif de sécurité ;
- audit npm ajouté à la CI ;
- construction Debian accélérée en excluant caches et `node_modules`.

## Validations externes obligatoires

Ces cases ne peuvent pas être validées par le projet ou par un test automatisé :

- [ ] recette métier signée par une association pilote ;
- [ ] test de restauration exécuté sur l'infrastructure cible et RTO accepté ;
- [ ] RPO, volumétrie, rétention et cible de sauvegarde hors machine approuvés ;
- [ ] audit de sécurité indépendant et test d'intrusion ciblé réalisés ;
- [ ] audit d'accessibilité manuel réalisé sur le parc de navigateurs cible ;
- [ ] AIPD, registre de traitement et durées de conservation validés par le DPO ;
- [ ] hébergement, accès administrateur et procédure d'incident approuvés ;
- [ ] risques résiduels acceptés par le responsable de traitement.

La publication de `0.27.0` fige le socle logiciel évalué. L'usage de données réelles nécessite
toujours les validations et signatures propres à chaque organisme déployeur.
