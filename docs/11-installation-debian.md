# Installation simplifiée sur Debian 13

Transmy fournit un paquet Debian et la commande d'administration `transmy`. Cette première
version vise une VM Debian 13 dédiée, une adresse locale ou un domaine public et un certificat HTTPS obtenu par Caddy.
Elle est destinée à l'évaluation avec des données fictives tant que les validations
organisationnelles et réglementaires ne sont pas achevées.

## Construction du paquet

Depuis la racine du dépôt, sur Debian 13 :

```text
chmod +x packaging/debian/*.sh packaging/debian/transmy
packaging/debian/build-package.sh '0.27.0~rc1'
packaging/debian/test-package.sh 'dist/transmy_0.27.0~rc1_all.deb'
```

Le paquet est produit dans `dist/`. Il embarque les sources et construit localement les images
de production afin de rester utilisable avant la publication d'images signées dans un registre.
Le workflow GitHub `Debian package` répète cette construction et publie le `.deb` comme artefact
à chaque modification de l'installateur et pour chaque tag de version.

## Installation

```text
curl --proto '=https' --tlsv1.2 -fsSL \
  https://raw.githubusercontent.com/transmy-spec/Transmy/newest/packaging/debian/install-from-github.sh \
  -o /tmp/transmy-install.sh && sudo sh /tmp/transmy-install.sh
```

Après quinze secondes sans réponse, l'assistant sélectionne le mode local et détecte
automatiquement l'adresse IPv4 privée de la VM. Le mode public reste sélectionnable et demande
alors le domaine et l'adresse ACME. L'assistant demande ensuite la langue initiale et le profil
d'installation :

- `production`, recommandé et sélectionné par défaut, demande le nom de l'association, de
  l'établissement, du service et de l'unité initiale ;
- `evaluation` conserve une structure et des personnages entièrement fictifs pour les essais.

En production, les noms de l'organisation, de l'établissement, du service et de l'unité initiale
sont renseignés après activation du compte administrateur, depuis l'écran **Structure**. Ils ne
bloquent donc plus l'installation technique.

Il :

- génère des secrets différents avec OpenSSL ;
- écrit `/etc/transmy/transmy.env` en mode `0600` ;
- crée un realm Keycloak lié au domaine ;
- ne conserve que le compte administrateur à activer en profil `production` ;
- remplace les mots de passe des personnages fictifs par des valeurs aléatoires temporaires en
  profil `evaluation` ;
- construit et démarre les images de production ;
- active le service et la sauvegarde quotidienne.

En mode local, saisir l'adresse IPv4 privée stable de la VM. Caddy génère une autorité de
certification locale. Son certificat racine peut être exporté après le démarrage :

```text
sudo transmy certificate
```

Le fichier `/var/lib/transmy/transmy-local-ca.crt` doit être transféré et installé uniquement
sur les postes autorisés à accéder au banc de test. Ne jamais diffuser cette autorité ni sa clé.

En profil `production`, aucun compte métier générique et aucun fichier d'identifiants ne sont
créés. L'administrateur reçoit uniquement le lien local d'activation décrit ci-dessous.

En profil `evaluation` seulement, les identifiants fictifs sont écrits dans
`/var/lib/transmy/initial-credentials.txt`, accessible uniquement à `root` :

```text
sudo cat /var/lib/transmy/initial-credentials.txt
```

Les comptes `chefservice` et `professionnel` ainsi créés ne doivent recevoir que des données
fictives. Les mots de passe fixes de Docker Compose sont réservés au développement et ne
fonctionnent pas avec le paquet Debian. Supprimer le fichier après les essais avec la commande
indiquée dans son contenu.

### Activation de l'administrateur

Une installation neuve n'utilise pas de mot de passe administrateur connu. À la fin de
`transmy setup`, la console affiche un lien local d'activation valable deux heures. Le jeton est
placé dans le fragment de l'URL afin de ne pas apparaître dans les journaux HTTP ; seul son
condensat authentifié est conservé en base. L'administrateur ouvre ce lien depuis le réseau de
l'association et choisit directement son mot de passe dans Keycloak.

En cas de perte d'accès, une personne disposant des droits `root` sur le serveur peut révoquer les
liens précédents et produire un nouveau lien à usage unique :

```text
sudo transmy admin-reset
```

Cette opération ferme les sessions administrateur existantes et est inscrite dans l'audit. Le
lien doit être remis en main propre, imprimé ou transmis par un canal interne approuvé. Il ne
doit pas être envoyé avec d'autres éléments d'authentification dans un même message.

Le compte technique `transmy-bootstrap` appartient au realm maître Keycloak et n'est pas un
compte Transmy. Son secret reste dans `/etc/transmy/transmy.env`, lisible uniquement par `root`,
et l'interface d'administration Keycloak n'est pas publiée par le reverse proxy. L'API utilise
un client de service distinct, limité à la gestion des utilisateurs du realm Transmy.

### Invitation des professionnels

Un administrateur crée un professionnel depuis **Équipe et accès**, puis choisit son rôle et son
unité principale. Transmy crée la même identité dans Keycloak et dans sa base applicative. Si une
écriture échoue, l'identité Keycloak créée est supprimée afin d'éviter un compte orphelin.

Le lien d'activation :

- est affiché une seule fois à l'administrateur ;
- est valable 48 heures et utilisable une seule fois ;
- place le jeton dans le fragment de l'URL pour ne pas l'inscrire dans les journaux HTTP ;
- n'est conservé en base que sous forme de condensat authentifié ;
- peut être imprimé et remis en main propre sur le réseau local ;
- peut être révoqué ou renouvelé depuis la fiche du professionnel.

À l'ouverture du lien, le professionnel choisit directement son mot de passe dans Keycloak. Le
compte applicatif reste dans l'état `invited` et ne peut ouvrir aucune session avant la
consommation du jeton. Les créations, renouvellements, révocations et activations sont audités.

L'installation non interactive est disponible pour l'automatisation :

```text
sudo TRANSMY_DOMAIN=transmissions.example.org \
  TRANSMY_MODE=public \
  TRANSMY_ACME_EMAIL=admin@example.org \
  TRANSMY_LANGUAGE=fr \
  transmy setup
```

Exemple local :

```text
sudo TRANSMY_MODE=local \
  TRANSMY_DOMAIN=192.168.1.51 \
  TRANSMY_LANGUAGE=fr \
  TRANSMY_PROFILE=production \
  TRANSMY_ORGANIZATION_NAME="Mon association" \
  TRANSMY_ESTABLISHMENT_NAME="Etablissement principal" \
  TRANSMY_SERVICE_NAME="Accompagnement" \
  TRANSMY_UNIT_NAME="Unite principale" \
  transmy setup
```

Pour un banc d'essai explicitement fictif, remplacer uniquement
`TRANSMY_PROFILE=production` par `TRANSMY_PROFILE=evaluation` et omettre les quatre noms.

## Administration

```text
sudo transmy status
sudo transmy doctor
sudo transmy admin-reset
sudo transmy logs
sudo transmy backup
sudo transmy restore-test
sudo transmy upgrade
```

`transmy upgrade` crée une sauvegarde, exécute un exercice de restauration, reconstruit les
images, applique les migrations et contrôle le point de santé public.

Depuis le lot 26, `transmy start` et `transmy upgrade` réconcilient aussi le client technique
Keycloak utilisé pour les invitations. Une installation existante reçoit automatiquement son
secret local manquant et les permissions minimales `manage-users` et `view-users`. Aucun compte
ni mot de passe utilisateur existant n'est réinitialisé.

## Services systemd

- `transmy.service` réconcilie l'application au démarrage de la VM ;
- `transmy-backup.timer` programme une sauvegarde quotidienne vers 02 h 15 avec un délai
  aléatoire maximal de 30 minutes ;
- `transmy-backup.service` exécute la sauvegarde chiffrée avec une priorité réduite.

Vérification :

```text
systemctl status transmy.service
systemctl list-timers transmy-backup.timer
journalctl -u transmy.service
```

## Désinstallation

```text
sudo apt remove transmy
```

Cette commande arrête le service mais conserve les secrets, les fichiers d'état et les volumes
Docker. Même `apt purge transmy` ne détruit pas les données automatiquement. Leur suppression
doit faire l'objet d'une opération séparée, documentée et précédée d'une sauvegarde restaurée.

## Publication du dépôt APT

Le workflow `Publish signed APT repository` transforme un tag Git `vX.Y.Z` en dépôt APT Debian
13 `amd64`, signe ses métadonnées et le publie avec GitHub Pages.

### Créer la clé de signature

La clé doit être générée hors ligne sur un poste d'administration protégé :

```text
gpg --quick-generate-key "Transmy APT Repository <packages@transmy.fr>" rsa4096 sign 2y
gpg --list-secret-keys --with-subkey-fingerprint
gpg --armor --export-secret-keys IDENTIFIANT_DE_LA_CLE > transmy-apt-private.asc
gpg --armor --export IDENTIFIANT_DE_LA_CLE > transmy-apt-public.asc
```

Conserver la clé privée et sa phrase de passe dans le gestionnaire de secrets retenu. Ajouter
dans les secrets GitHub du dépôt :

- `APT_SIGNING_PRIVATE_KEY` : contenu complet de `transmy-apt-private.asc` ;
- `APT_SIGNING_KEY_PASSPHRASE` : phrase de passe de la clé.

Dans les paramètres GitHub, activer Pages avec la source **GitHub Actions**. La clé publique est
exportée automatiquement avec le dépôt ; son empreinte est publiée sur la page d'index et
intégrée au script d'installation.

### Publier une version

```text
git tag -s v0.27.0 -m "Transmy 0.27.0"
git push origin v0.27.0
```

Le workflow :

1. construit et inspecte le paquet ;
2. génère `Packages`, `Packages.gz` et `Release` ;
3. produit les signatures `InRelease` et `Release.gpg` en SHA-512 ;
4. vérifie les deux signatures ;
5. déploie le dépôt sur GitHub Pages.

### Installation par un utilisateur

Télécharger et examiner le script avant de l'exécuter :

```text
curl -fsSLO https://transmy-spec.github.io/transmy/debian/install.sh
less install.sh
sudo sh install.sh
sudo apt install transmy
sudo transmy setup
```

Le script refuse les systèmes autres que Debian 13, télécharge la clé via HTTPS, vérifie son
empreinte intégrée, installe une source Deb822 avec `Signed-By`, puis actualise APT. Il n'utilise
ni `apt-key`, ni `trusted=yes`.

La publication future d'images versionnées et signées dans un registre permettra de remplacer
la construction locale par un téléchargement vérifiable et plus rapide.
