# Preparation du pilote

Mise a jour technique : 18 juillet 2026. Le registre est maintenant disponible dans l'ecran
`Preparation pilote`. Il ne vaut ni audit independant, ni AIPD,
ni acceptation des risques par un organisme.

## Preuves disponibles

| Domaine | Etat | Preuve locale |
|---|---|---|
| Parcours MVP | Satisfait techniquement | 66 tests backend, tests Vue, build TypeScript |
| Autorisations | Satisfait techniquement | tests positifs/negatifs et controle serveur par permission |
| Accessibilite automatique | Satisfait sur l'ecran de connexion | test axe WCAG 2.2 AA dans Vitest |
| Navigation clavier | Corrige, revue manuelle requise | lien d'evitement fonctionnel et `aria-current` |
| Charge de reference | A mesurer a chaque pilote | profil Compose `load-test`, seuil p95 inferieur a 750 ms |
| Securite HTTP | Satisfait techniquement | profil `security-audit`, CSP et acces anonymes controles |
| Sauvegarde/restauration | Satisfait techniquement | archive chiffree et restauration temporaire mesuree |
| Dependances frontend | Satisfait au 18/07/2026 | audit npm : aucune vulnerabilite connue |
| Licence et contribution | Documente | `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md` |

## Suivi des anomalies

Le lot 15 ajoute le registre `Anomalies pilote`, accessible aux administrateurs et chefs de
service. Chaque anomalie peut etre rattachee a un scenario de recette, qualifiee, affectee et
suivie jusqu'a sa resolution ou l'acceptation explicite du risque. Une anomalie critique ouverte
ou en cours bloque automatiquement l'indicateur de preparation du pilote.

## Validations obligatoires de l'organisme

Ces valeurs ne doivent pas recevoir de defaut silencieux en production :

| Decision | Valeur attendue | Responsable | Etat |
|---|---|---|---|
| Volumetrie nominale et pointe | personnes, transmissions/jour, utilisateurs simultanes | Pilote/metier | A renseigner |
| RPO et frequence de sauvegarde | duree chiffree et cible hors machine | Exploitation | A renseigner |
| RTO | duree maximale et procedure d'escalade | Exploitation | A renseigner |
| Conservation | duree et base legale par type de donnee | DPO/juridique | A renseigner |
| AIPD | conclusion, mesures et risques residuels | Responsable de traitement/DPO | A conduire |
| Hebergement | qualification, localisation, sous-traitants | Organisme/securite | A qualifier |
| Navigateurs | versions et appareils institutionnels testes | Support du pilote | A renseigner |
| Supervision | outil local, seuils, astreinte et destinataires | Exploitation | A renseigner |
| Audit independant | accessibilite et intrusion ciblee | Organisme | A planifier |
| Risques residuels | proprietaire, echeance et acceptation signee | Direction du pilote | A accepter |

## Campagne reproductible

```text
docker compose run --rm api pytest
docker compose run --rm frontend npm run test:run
docker compose --profile validation run --rm security-audit
docker compose --profile validation run --rm load-test
docker compose --profile operations run --rm backup
docker compose --profile operations run --rm restore-test
```

Le test de charge fourni est un point de depart a 10 utilisateurs virtuels pendant 30 secondes.
Les variables `LOAD_VUS` et `LOAD_DURATION` doivent etre remplacees par la volumetrie validee.
La campagne finale doit etre executee sur une architecture equivalente au pilote, avec des donnees
strictement synthetiques, et son rapport date doit etre accepte par les responsables ci-dessus.

## Navigateurs et exploitation

La cible provisoire est constituée des deux dernieres versions majeures de Firefox, Chromium,
Edge et Safari. Elle reste provisoire jusqu'a l'inventaire du parc. L'application exige HTTPS,
JavaScript, cookies `Secure`/`HttpOnly` et un navigateur supportant les modules ES modernes.

La supervision de reference reste locale : etats de sante Compose, endpoint
`/api/v1/health/live`, journaux Docker et rapports de restauration. Aucun envoi externe ni aucune
metrique metier ne sont activees.
