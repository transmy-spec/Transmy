# Authentification et sessions

## 1. Acteurs et secrets

- **Navigateur** : possède uniquement un cookie de session opaque et un jeton CSRF lisible par le frontend.
- **BFF FastAPI** : client OIDC confidentiel Keycloak ; conserve les jetons associés à la session côté serveur.
- **Keycloak** : authentifie, applique MFA et gère sa session SSO.
- **PostgreSQL applicatif** : conserve une session chiffrée ou les jetons chiffrés avec expiration.

Le secret du client OIDC, la clé de chiffrement des sessions et les clés CSRF MUST être injectés par fichiers de secrets hors dépôt.

## 2. Connexion

```text
Navigateur        BFF FastAPI                    Keycloak
    | GET /auth/login   |                            |
    |------------------>| génère state, nonce, PKCE |
    | 302               |                            |
    |<------------------|                            |
    | Authorization Request ------------------------>|
    |<---------------- authentification + code ------|
    | GET /auth/callback?code&state                  |
    |------------------>| vérifie state              |
    |                   | échange code + verifier -->|
    |                   |<-- ID/access/refresh tokens|
    |                   | valide issuer/aud/nonce    |
    |                   | lie (issuer, subject)      |
    |<-- session cookie + redirection sûre ----------|
```

Règles :

- `state`, `nonce` et `code_verifier` sont aléatoires, à usage unique et expirent après 5 minutes.
- L'URI de retour est fixe et enregistrée précisément dans Keycloak.
- Le paramètre de destination après connexion est un chemin local validé, jamais une URL libre.
- Le backend valide signature, algorithme attendu, `iss`, `aud`, `exp`, `iat`, `nonce` et le sujet.
- (`issuer`, `subject`) identifie le compte ; ni l'email ni le nom affiché ne le remplacent.
- Un compte inconnu n'est pas auto-provisionné par défaut. Un administrateur doit préparer son compte applicatif et ses rattachements.

## 3. Cookie et session

Nom de référence : `__Host-transmissions_session`.

- `Secure`, `HttpOnly`, `Path=/`, sans attribut `Domain`.
- `SameSite=Lax` si les flux OIDC et le déploiement le permettent.
- Identifiant opaque d'au moins 256 bits d'entropie ; aucune donnée métier ou permission dans le cookie.
- Durée d'inactivité recommandée : 15 minutes (`PILOTE`).
- Durée absolue recommandée : 8 heures (`PILOTE`).
- Rotation de l'identifiant après connexion, élévation administrative et renouvellement sensible.
- Une session référence la version des habilitations du compte. Toute différence force leur recalcul ; une désactivation refuse immédiatement la requête.

Les jetons OIDC persistés sont chiffrés au niveau applicatif. La clé active est versionnée ; une rotation conserve temporairement la capacité de déchiffrer les sessions existantes ou les invalide explicitement.

## 4. Protection CSRF

Toutes les routes modifiant l'état MUST :

- refuser les méthodes simples inattendues ;
- vérifier `Origin` contre l'origine publique configurée ;
- exiger un en-tête `X-CSRF-Token` correspondant à un secret lié à la session ;
- refuser les requêtes sans type de contenu attendu ;
- ne jamais accepter de mutation via `GET`.

Le token CSRF peut être obtenu par `GET /api/v1/session` et conservé uniquement en mémoire par le frontend.

## 5. Renouvellement et révocation

- Le BFF renouvelle un access token uniquement côté serveur et avant une requête qui en a besoin.
- Un échec de renouvellement invalide la session locale et renvoie `401 session_expired`.
- Le statut du compte, les rattachements et les rôles sont contrôlés côté application à chaque requête.
- La désactivation d'un compte supprime toutes ses sessions dans la même transaction logique ou via un travail prioritaire idempotent.
- Les access tokens Keycloak SHOULD avoir une durée courte, recommandée à 5 minutes (`PILOTE`).

## 6. Déconnexion

`POST /api/v1/auth/logout` :

1. valide CSRF et origine ;
2. révoque la session locale ;
3. tente la déconnexion Keycloak selon le flux supporté ;
4. expire le cookie ;
5. journalise la fin de session sans jeton ni contenu sensible.

La déconnexion reste réussie côté application même si Keycloak est momentanément indisponible.

## 7. Endpoints d'authentification

| Méthode | Route | Authentification | Usage |
|---|---|---|---|
| GET | `/auth/login` | publique | Démarre OIDC, avec limitation de débit |
| GET | `/auth/callback` | état OIDC | Termine OIDC |
| GET | `/api/v1/session` | session | Profil minimal, périmètres disponibles, token CSRF |
| POST | `/api/v1/auth/logout` | session + CSRF | Termine la session |

`GET /api/v1/session` ne retourne pas la matrice complète si elle peut être déduite pour attaquer le système ; il retourne les capacités nécessaires à l'interface, qui restent indicatives.

## 8. Erreurs et audit

- `401 authentication_required` : aucune session valide.
- `401 session_expired` : session arrivée à expiration.
- `403 account_disabled` : identité valide mais compte désactivé.
- `403 access_denied` : permission absente ; ne révèle pas l'existence d'une ressource.

Sont audités : connexion réussie, échec applicatif significatif, déconnexion, révocation, compte inconnu, compte désactivé et échecs CSRF répétés. Les tentatives de mot de passe restent dans le journal Keycloak.
