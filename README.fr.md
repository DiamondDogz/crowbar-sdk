# crowbar-sdk

**Rendez votre runtime PS4RT compatible Crowbar : trophées, profil, téléchargement et mises à jour, sans écrire d'interface.**

[Crowbar](https://github.com/DiamondDogz/crowbar) est un launcher façon XMB pour les runtimes PS4RT, sous Windows et Linux. Ce dépôt contient le format public qu'il lit et de petits outils pour l'adopter. Crowbar reste fermé ; tout ce qui est ici est sous licence MIT.

*[English](README.md)*

## Ce que vos joueurs y gagnent

- **Trophées** : liste, icônes et descriptions dans leur langue, trophées cachés, lus dans leur propre dump. Vous ne fournissez que le déblocage.
- **Une carte et une notification** quand un trophée tombe, en direct pendant la partie.
- **Un profil** : niveau, totaux, progression par jeu.
- **Téléchargement et mises à jour** depuis le catalogue, chaque fichier vérifié par son SHA-256.
- **DLC et mises à jour du jeu** lus dans leurs `.pkg` ; vous ne recevez que ceux à installer.
- **Sauvegardes** de votre dossier de données, et **rapports de bug utiles** : journal de lancement et infos système, copiés en un clic.

## Ce que vous faites (environ une heure)

1. Appeler `crowbar_unlock(id)` là où votre runtime gère `sceNpTrophyUnlockTrophy`.
2. Livrer un `crowbar.json` à la racine de votre release : nom, CUSA, commande de lancement.
3. Lancer `crowbar-check` jusqu'à ce qu'il ne signale plus rien.
4. Remplir le formulaire **Add a runtime** de [crowbar-catalog](https://github.com/DiamondDogz/crowbar-catalog/issues/new/choose).

## Vous travaillez avec une IA ?

Collez-lui ceci (Claude, Grok, DeepSeek, Gemini, Copilot…) :

> Rends ce runtime compatible Crowbar. Lis https://github.com/DiamondDogz/crowbar-sdk/blob/main/AGENTS.md, lance `crowbar-check . --handout` et suis-le. Arrête-toi quand `crowbar-check . --json` ne renvoie plus d'erreur, puis montre-moi le diff.

[AGENTS.md](AGENTS.md) est écrit pour elles ; `crowbar-check --handout` leur donne un plan pour votre runtime précis, avec fichiers et numéros de ligne. Elles ne publient jamais rien : vous relisez le diff et publiez.

La spécification complète, les outils et les exemples sont décrits dans le [README anglais](README.md) et dans [SPEC.md](SPEC.md).

## Licence

MIT. Voir [LICENSE](LICENSE).
