# Conception détaillée du MVP

**Statut :** base de conception — version 0.1  
**Date :** 18 juillet 2026

Ce dossier traduit le cadrage et les décisions validées en contrats techniques. Il ne contient pas de code applicatif et n'invente aucune donnée réelle.

## Documents

1. [ADR structurants](01-adr-structurants.md)
2. [Authentification et sessions](02-authentification-et-sessions.md)
3. [Matrice des habilitations](03-matrice-habilitations.md)
4. [Contrat d'API](04-contrat-api.md)
5. [Schéma relationnel PostgreSQL](05-schema-postgresql.md)
6. [Audit, archivage et sauvegarde](06-audit-archivage-sauvegarde.md)
7. [Déploiement Docker Compose](07-deploiement-compose.md)
8. [Plan de réalisation](08-plan-realisation.md)

## Conventions

- `MUST`, `SHOULD` et `MAY` expriment respectivement une obligation, une recommandation forte et une option.
- Les identifiants publics sont des UUID opaques ; ils ne constituent jamais une autorisation.
- Les exemples utilisent uniquement des identifiants factices et les domaines réservés `example.test`.
- Une valeur marquée `PILOTE` doit être mesurée ou validée avant une mise en production réelle.
- Les dates métier et techniques sont échangées au format RFC 3339 et conservées en UTC.

## Traçabilité

| Domaine | Décisions principales | Exigences principales | Document |
|---|---|---|---|
| Architecture | DEC-001, 013, 022, 023 | ENF-MAI-001 à 005 | ADR |
| Authentification | DEC-013 | EF-ID-001 à 006, ENF-SEC-001 à 004 | Authentification |
| Autorisation | DEC-002, 003, 011, 012 | EF-AUT-001 à 008 | Matrice |
| API métier | DEC-005 à 010, 019 à 021, 025 | EF-TRN, EF-LEC, EF-TAC, EF-REL | Contrat API |
| Données | DEC-002 à 009, 015, 022 | EF-ORG, EF-PER, ENF-DIS-003 à 006 | Schéma PostgreSQL |
| Audit et conservation | DEC-014 à 016, 024, 025 | EF-AUD, EF-ARC, EF-SAV | Audit et sauvegarde |
| Exploitation | DEC-016, 017, 023, 024, 029 | ENF-DIS, ENF-OPS | Compose |

## Paramètres encore à renseigner

Les orientations sont validées, mais les valeurs suivantes dépendent du pilote : volumétrie nominale et de pointe, RPO, RTO, durées de conservation, fréquence des tests de restauration, contraintes d'hébergement, parc de navigateurs et seuils d'alerte. Leur absence n'autorise pas des valeurs silencieuses en production.
