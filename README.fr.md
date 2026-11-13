# crowbar-sdk

**Rendez votre runtime PS4RT compatible Crowbar : trophées, profil, téléchargement et mises à jour, sans écrire d'interface.**

[Crowbar](https://github.com/DiamondDogz/crowbar) est un launcher façon XMB pour les runtimes PS4RT, sous Windows et Linux. Ce dépôt contient le format public qu'il lit et de petits outils pour l'adopter. Crowbar reste fermé ; tout ce qui est ici est sous licence MIT.

*[English](README.md)*

## Ce que vos joueurs y gagnent

- **Trophées** : liste, icônes et descriptions dans leur langue, trophées cachés, lus dans leur propre dump. Vous ne fournissez que le déblocage.
- **Une carte et une notification** quand un trophée tombe, en direct pendant la partie. Leurs amis en ligne sont prévenus aussi, et peuvent comparer leurs trophées.
- **Une vraie pause avec le bouton Guide** (facultatif) : le jeu s'arrête pendant que le menu de Crowbar est ouvert, et le Guide refuse poliment quand le jeu ne peut pas s'arrêter (une cinématique, par exemple), comme sur console. Deux appels avec le SDK : `crowbar_poll()` et `crowbar_answer()`.
- **Ce qu'ils font, montré à leurs amis et sur Discord** (facultatif) : « Sakura Wars · Chapitre 3 ». Une partie en ligne n'est jamais mise en pause. Un appel : `crowbar_set_presence()`.
- **Leurs captures et vidéos dans Crowbar** (facultatif) : enregistrez-les dans `PS4RT_CAPTURE_DIR` et le jeu reçoit une galerie Captures. Les **mods** ont leur dossier dans les Contenus du jeu quand vous déclarez `mods`.
- **Un profil** : niveau, totaux, progression par jeu.
- **Téléchargement et mises à jour** depuis le catalogue, chaque fichier vérifié par son SHA-256.
- **DLC et mises à jour du jeu** lus dans leurs `.pkg` ; vous ne recevez que ceux à installer.
- **Sauvegardes** de votre dossier de données, et **rapports de bug utiles** : journal de lancement et infos système, copiés en un clic.

## Ce que vous faites

Quelques minutes de modifications avec un assistant IA (un peu plus à la main), puis une recompilation et un trophée en jeu pour vérifier que tout marche.

1. Appeler `crowbar_unlock(id)` là où votre runtime gère `sceNpTrophyUnlockTrophy`.
2. Livrer un `crowbar.json` à la racine de votre release : nom, CUSA, commande de lancement.
3. Lancer `crowbar-check` jusqu'à ce qu'il ne signale plus rien.
4. Remplir le formulaire **Add a runtime** de [crowbar-catalog](https://github.com/DiamondDogz/crowbar-catalog/issues/new/choose).

## Vous travaillez avec une IA ?

Collez-lui ceci (Claude, Grok, DeepSeek, Gemini, Copilot…) :

> Rends ce runtime compatible Crowbar. Lis https://github.com/DiamondDogz/crowbar-sdk/blob/main/AGENTS.md, lance `crowbar-check . --handout` et suis-le. Arrête-toi quand `crowbar-check . --json` ne renvoie plus d'erreur, puis montre-moi le diff.

[AGENTS.md](AGENTS.md) est écrit pour elles ; `crowbar-check --handout` leur donne un plan pour votre runtime précis, avec fichiers et numéros de ligne. Elles ne publient jamais rien : vous relisez le diff et publiez.

## Tester dans Crowbar

Crowbar a un mode développeur caché. Entrez le code Konami n'importe où dans Crowbar, à la manette ou au clavier : **↑ ↑ ↓ ↓ ← → ← → B A** (au clavier, B et A ou Échap et Entrée). **Paramètres › Développeur** permet alors de pointer votre runtime local, de voir si votre `crowbar.json` est valide, de suivre les lancements et les trophées en direct, de simuler une notification de trophée et de copier une fiche catalogue préremplie. Le même code le cache à nouveau.

La spécification complète, les outils et les exemples sont décrits dans le [README anglais](README.md) et dans [SPEC.md](SPEC.md).

## Licence

MIT. Voir [LICENSE](LICENSE).
