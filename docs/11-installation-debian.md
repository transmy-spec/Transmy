# Installation simplifiée sur Debian 13

Le lot 24 fournit un paquet Debian et la commande d'administration `transmy`. Cette première
version vise une VM Debian 13 dédiée, un domaine public et un certificat HTTPS obtenu par Caddy.
Elle est destinée à l'évaluation avec des données fictives tant que les validations
organisationnelles et réglementaires ne sont pas achevées.

## Construction du paquet

Depuis la racine du dépôt, sur Debian 13 :

```text
chmod +x packaging/debian/*.sh packaging/debian/transmy
packaging/debian/build-package.sh 0.24.0
packaging/debian/test-package.sh dist/transmy_0.24.0_all.deb
```

Le paquet est produit dans `dist/`. Il embarque les sources et construit localement les images
de production afin de rester utilisable avant la publication d'images signées dans un registre.
Le workflow GitHub `Debian package` répète cette construction et publie le `.deb` comme artefact
à chaque modification de l'installateur et pour chaque tag de version.

## Installation

```text
sudo apt install ./dist/transmy_0.24.0_all.deb
sudo transmy setup
```

L'assistant demande le mode public ou local, l'adresse ou le domaine et la langue initiale. Il :

- génère des secrets différents avec OpenSSL ;
- écrit `/etc/transmy/transmy.env` en mode `0600` ;
- crée un realm Keycloak lié au domaine ;
- remplace les mots de passe connus par des valeurs aléatoires temporaires ;
- construit et démarre les images de production ;
- active le service et la sauvegarde quotidienne.

En mode local, saisir l'adresse IPv4 privée stable de la VM. Caddy génère une autorité de
certification locale. Son certificat racine peut être exporté après le démarrage :

```text
sudo transmy certificate
```

Le fichier `/var/lib/transmy/transmy-local-ca.crt` doit être transféré et installé uniquement
sur les postes autorisés à accéder au banc de test. Ne jamais diffuser cette autorité ni sa clé.

Les identifiants initiaux sont écrits dans
`/var/lib/transmy/initial-credentials.txt`, accessible uniquement à `root` :

```text
sudo cat /var/lib/transmy/initial-credentials.txt
```

Utiliser les comptes `admin`, `chefservice` ou `professionnel` avec les mots de passe temporaires
affichés dans ce fichier. Les mots de passe fixes documentés pour Docker Compose sont réservés au
développement et ne fonctionnent pas avec le paquet Debian. Après la première connexion, changer
les mots de passe, les conserver dans le gestionnaire de secrets retenu par l'organisme, puis
supprimer le fichier avec la commande indiquée dans son contenu.

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
  transmy setup
```

## Administration

```text
sudo transmy status
sudo transmy doctor
sudo transmy logs
sudo transmy backup
sudo transmy restore-test
sudo transmy upgrade
```

`transmy upgrade` crée une sauvegarde, exécute un exercice de restauration, reconstruit les
images, applique les migrations et contrôle le point de santé public.

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
git tag -s v0.24.0 -m "Transmy 0.24.0"
git push origin v0.24.0
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
