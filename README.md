# Transmissions

Application web open source de transmissions pour les professionnels du secteur social et médico-social.

Les lots 0 à 2 fournissent le socle Docker, une authentification Keycloak avec sessions BFF,
les comptes applicatifs, les rôles, les périmètres, la structure organisationnelle, l'audit et
la gestion des personnes accompagnées dans le périmètre autorisé.

## Prérequis

- Docker Engine avec Docker Compose v2 ;
- ou, pour travailler hors conteneurs, Python 3.13 et Node.js 24 LTS.

## Démarrage local

1. Copier `.env.example` vers `.env`.
2. Remplacer toutes les valeurs `CHANGE_ME` par des secrets locaux aléatoires.
3. Lancer `docker compose config` pour contrôler la configuration.
4. Lancer `docker compose up --build`.
5. Ouvrir `https://localhost` et accepter uniquement en développement le certificat local de Caddy.

Le realm local crée deux comptes synthétiques :

- administrateur : `admin` / `Admin-Local-2026!` ;
- professionnel : `professionnel` / `Pro-Local-2026!`.
- chef de service : `chefservice` / `Chef-Local-2026!`.

Le professionnel consulte et modifie les fiches dans son unité. Seuls le chef de service et
l'administrateur peuvent créer une personne accompagnée. Le lot 3 permet aux rôles métier de
rédiger, publier et accuser la lecture de transmissions versionnées. Le lot 4 ajoute les tâches,
les échéances, leur historique et les relèves préparées automatiquement par le chef de service.

Ces identifiants sont réservés au développement local et doivent être remplacés pour tout autre
environnement.

L'API de santé est accessible via `https://localhost/api/v1/health/live`. Keycloak est publié sous
`https://localhost/oidc/`. La structure et les identités créées localement sont entièrement
synthétiques.

## Vérifications

```text
docker compose run --rm api pytest
docker compose run --rm api ruff check .
docker compose run --rm api mypy app
docker compose run --rm frontend npm run test:run
docker compose run --rm frontend npm run build
```

## Sécurité et données

- Ne jamais placer de donnée réelle, pseudonymisée, de sauvegarde ou de capture de production dans ce dépôt.
- Ne jamais committer `.env`, `.secrets/`, exports, dumps ou journaux d'exécution.
- Le Compose fourni est un environnement de développement. Il ne constitue pas encore la configuration de production durcie décrite dans la [conception détaillée](docs/conception/README.md).
- Aucune télémétrie ni ressource cloud n'est requise.

## Lot 5 : exploitation des donnees

Le lot 5 ajoute les politiques de conservation sans purge active, les exports temporaires
audites et les procedures de sauvegarde chiffree et de restauration controlee.

Definir un secret `BACKUP_ENCRYPTION_PASSWORD` robuste hors developpement, puis executer :

```text
docker compose --profile operations run --rm backup
docker compose --profile operations run --rm restore-test
```

La sauvegarde couvre les bases applicative et Keycloak dans le volume `encrypted_backups`.
L'exercice restaure les archives dans deux bases temporaires, controle leur structure, les
supprime, puis produit un rapport JSON sans donnee metier. Une sauvegarde n'est exploitable
qu'apres un rapport de restauration avec le statut `success`.

Avant une mise a jour, produire et restaurer une sauvegarde, reconstruire avec
`docker compose build`, puis lancer `docker compose up -d --wait`. Les migrations Alembic sont
executees avant le redemarrage de l'API.

## Validation du pilote

Les controles techniques du lot 6 sont decrits dans
[`docs/07-preparation-pilote.md`](docs/07-preparation-pilote.md). Le profil `validation` execute
les controles HTTP de securite et le test de charge local. Les validations AIPD, hebergement,
conservation, RPO/RTO et risques residuels restent a conduire et accepter par l'organisme pilote.

## Production

L'override `compose.production.yaml` active les images durcies et le contrôle d'exploitation.
La procédure complète, les préconditions et la reprise après incident sont décrites dans
[`docs/10-exploitation-production.md`](docs/10-exploitation-production.md). Le Compose local
reste volontairement destiné au développement et ne doit pas accueillir de données réelles.

## Documentation

Le cadrage et la conception sont indexés dans [`docs/`](docs/README.md).
