# Documentation de cadrage du MVP

Ce dossier décrit le cadrage fonctionnel, technique et de sécurité d'une application open source de transmissions destinée aux professionnels du secteur social et médico-social.

## Documents

- [Preparation du pilote](07-preparation-pilote.md)
- [Phase 2](08-phase-2.md)
- [Installation simplifiee sur Debian 13](11-installation-debian.md)

1. [Utilisateurs et parcours](01-utilisateurs-et-parcours.md)
2. [Exigences fonctionnelles et non fonctionnelles](02-exigences.md)
3. [Modèle de données](03-modele-de-donnees.md)
4. [Architecture proposée](04-architecture.md)
5. [Modèle de menaces](05-modele-de-menaces.md)
6. [Décisions validées](06-decisions-a-valider.md)
7. [Conception détaillée du MVP](conception/README.md)

## Principes de cadrage

- Le MVP est multi-établissements et multi-services, mais auto-hébergé par une organisation.
- Les données concernant les personnes accompagnées et les transmissions sont considérées comme hautement sensibles.
- Toute autorisation est vérifiée côté backend, indépendamment de l'affichage du frontend.
- Le produit ne contient aucune télémétrie et ne requiert aucun service cloud.
- Le dépôt, les exemples, les démonstrations et les tests ne contiennent que des données entièrement fictives.
- Une transmission validée n'est pas modifiée silencieusement : toute correction est traçable.
- L'audit applicatif est append-only et protégé par une chaîne cryptographique ; un export ou ancrage local séparé est configurable.

## Portée

Ces documents cadrent le MVP. Ils ne constituent ni une analyse d'impact relative à la protection des données (AIPD), ni une homologation de sécurité, ni un avis juridique. Ces travaux devront être conduits par chaque organisme déployeur selon son contexte.

## État des décisions

Le 18 juillet 2026, le porteur du projet a validé l'ensemble des recommandations du [registre de décisions](06-decisions-a-valider.md). Elles constituent désormais les orientations de référence du MVP.

Cette validation adopte aussi la démarche recommandée pour les décisions dépendant du contexte d'un déploiement. Elle ne fixe pas arbitrairement les valeurs qui exigent une étude ou des données du pilote, notamment la volumétrie, les objectifs RPO/RTO, les durées de conservation et la qualification réglementaire de l'hébergement.
