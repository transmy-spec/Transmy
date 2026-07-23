#!/bin/sh
set -eu

PACKAGE=${1:?usage: build-apt-repository.sh PACKAGE.deb OUTPUT_DIR}
OUTPUT_DIR=${2:?usage: build-apt-repository.sh PACKAGE.deb OUTPUT_DIR}
SIGNING_KEY=${APT_SIGNING_KEY:?Set APT_SIGNING_KEY to the signing key fingerprint}
PASSPHRASE=${APT_SIGNING_KEY_PASSPHRASE:-}

command -v apt-ftparchive >/dev/null 2>&1 || {
  printf '%s\n' "apt-ftparchive is required" >&2
  exit 1
}
command -v gpg >/dev/null 2>&1 || {
  printf '%s\n' "gpg is required" >&2
  exit 1
}
test -f "$PACKAGE"

mkdir -p \
  "$OUTPUT_DIR/pool/main/t/transmy" \
  "$OUTPUT_DIR/dists/trixie/main/binary-amd64"
install -m 0644 "$PACKAGE" "$OUTPUT_DIR/pool/main/t/transmy/"

(
  cd "$OUTPUT_DIR"
  apt-ftparchive packages pool/main >dists/trixie/main/binary-amd64/Packages
  gzip -9 -c dists/trixie/main/binary-amd64/Packages \
    >dists/trixie/main/binary-amd64/Packages.gz

  apt-ftparchive \
    -o APT::FTPArchive::Release::Origin="Transmy" \
    -o APT::FTPArchive::Release::Label="Transmy" \
    -o APT::FTPArchive::Release::Suite="trixie" \
    -o APT::FTPArchive::Release::Codename="trixie" \
    -o APT::FTPArchive::Release::Architectures="amd64" \
    -o APT::FTPArchive::Release::Components="main" \
    -o APT::FTPArchive::Release::Description="Transmy packages for Debian 13" \
    release dists/trixie >dists/trixie/Release

  rm -f dists/trixie/InRelease dists/trixie/Release.gpg
  gpg --batch --yes --pinentry-mode loopback --passphrase "$PASSPHRASE" \
    --local-user "$SIGNING_KEY" --digest-algo SHA512 \
    --clearsign --output dists/trixie/InRelease dists/trixie/Release
  gpg --batch --yes --pinentry-mode loopback --passphrase "$PASSPHRASE" \
    --local-user "$SIGNING_KEY" --digest-algo SHA512 \
    --armor --detach-sign --output dists/trixie/Release.gpg dists/trixie/Release
  gpg --batch --export "$SIGNING_KEY" >transmy-archive-keyring.gpg
  gpg --batch --with-colons --show-keys transmy-archive-keyring.gpg |
    awk -F: '$1 == "fpr" { print $10; exit }' >transmy-archive-keyring.fingerprint
)

fingerprint=$(cat "$OUTPUT_DIR/transmy-archive-keyring.fingerprint")
sed "s/@FINGERPRINT@/$fingerprint/g" \
  "$(dirname "$0")/install-apt-repository.sh.in" \
  >"$OUTPUT_DIR/install.sh"
chmod 0755 "$OUTPUT_DIR/install.sh"

cat >"$OUTPUT_DIR/index.html" <<EOF
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Transmy Debian repository</title>
<h1>Transmy for Debian 13</h1>
<p>Signing key fingerprint: <code>$fingerprint</code></p>
<pre>curl -fsSLO https://transmy-spec.github.io/transmy/debian/install.sh
less install.sh
sudo sh install.sh
sudo apt install transmy
sudo transmy setup</pre>
</html>
EOF
