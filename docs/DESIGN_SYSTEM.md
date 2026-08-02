# CutForge — Système de design du parcours connecté

> Une seule main sur tout ce que l'utilisateur voit après connexion : mêmes
> surfaces, même courbe d'animation, une seule couleur d'action décisive.

---

## 1. Ce qui n'allait pas

Le parcours connecté n'avait pas de structure : il vivait sous la barre du
**site vitrine** (une rangée de liens texte), sans repère de section, et sans
rien du tout sur mobile hormis des liens tassés dans un coin. Les écrans
composaient chacun leurs propres `bg-white/[0.03] border-white/10` : au bout de
quelques ajouts, aucune carte n'avait tout à fait le même gris que sa voisine.
Rien ne distinguait une action décisive d'une action secondaire, les champs de
formulaire flottaient au lieu d'être creusés, et l'attente d'un rendu de
plusieurs minutes n'affichait qu'un pourcentage nu.

## 2. Les partis pris

| Décision | Pourquoi |
|---|---|
| **Profondeur par empilement de valeurs**, pas par ombres | Sur du quasi-noir, une ombre portée ne se voit pas. Ce qui crée le relief, c'est une échelle de surfaces très proches (`surface.canvas → base → raised → overlay`), chacune soulignée d'un **filet clair intérieur en haut** (`shadow-e1..e4`) qui simule une lumière zénithale. |
| **Une seule courbe** (`--ease-premium`, `cubic-bezier(.22,1,.36,1)`) | Départ franc, arrivée posée. Dix animations aux courbes différentes donnent dix produits différents. |
| **Mouvements minuscules** | Les cartes s'élèvent de 3 px, les pages entrent de 10 px, les boutons s'enfoncent à 0.985. Une carte qui saute de 10 px fait « template gratuit ». |
| **Le dégradé de marque est rare** | Réservé à l'action décisive d'un écran (`btn-accent`) et aux indicateurs d'état actif. Partout, il ne veut plus rien dire. |
| **Les champs sont creusés** | Ombre intérieure + fond plus sombre que la surface. C'est le détail qui sépare un formulaire premium d'un formulaire de démo. |
| **L'attente est nommée** | Le backend renvoie un pourcentage ; l'interface le traduit en étape (« Choix des illustrations et du collage… »). Un pourcentage seul pendant quatre minutes se lit comme un blocage. |

## 3. La coquille (`components/layout/AppShell.tsx`)

```
┌─ rail 248px ─┬──────── en-tête collante (64px) ────────┐
│  logo        │  fil d'ariane            plan · compte  │
│  navigation  ├─────────────────────────────────────────┤
│  ·  ·  ·     │                                         │
│              │              contenu                    │
│  plan / CTA  │                                         │
└──────────────┴─────────────────────────────────────────┘
        mobile : rail masqué, onglets bas à portée de pouce
```

* La section active est signalée par un indicateur qui **glisse** d'un item à
  l'autre (`layoutId` de framer-motion) : on suit des yeux où l'on vient
  d'aller, au lieu de voir un fond clignoter ailleurs.
* `/pricing` bascule d'une coquille à l'autre selon la session — on ne « sort »
  plus du produit pour aller payer.
* Le menu de compte se ferme au clic extérieur **et** à Échap : sur mobile, un
  menu qui reste ouvert masque le contenu et fait croire à un blocage.

## 4. Les briques

| Brique | Rôle |
|---|---|
| `Surface` | La seule façon de poser un bloc. `tone` (raised / quiet / glass), `interactive` (halo qui suit le curseur), `flush` (média plein cadre). |
| `Metric` | Tuile de chiffre, avec compte à rebours à la **première** apparition seulement — un chiffre qui rejoue son animation à chaque rafraîchissement devient du bruit. |
| `Toggle` | Vrai `role="switch"` : état annoncé aux lecteurs d'écran, pilotable au clavier, libellé qui passe à la ligne plutôt que d'être tronqué. |
| `PageTransition` | Entrée d'écran discrète (10 px, 320 ms), réduite à un fondu sous `prefers-reduced-motion`. |
| `.ring-progress` | Anneau de progression en `conic-gradient` masqué : aucun nœud DOM supplémentaire, animation gratuite pour le compositeur. |
| `.bar-fill[data-live]` | Liseré qui court sur la barre pendant un rendu — la différence entre « ça travaille » et « c'est figé ». |

## 5. Pièges rencontrés (à ne pas réintroduire)

* **`.overline` est une utilitaire Tailwind** (`text-decoration: overline`), et
  la couche `utilities` passe après `components`. Une classe maison de ce nom
  soulignait chaque intitulé par le haut. Le filet de titre s'appelle
  `.eyebrow`.
* **`border-dashed` se déforme sur les grands rayons** : la zone d'import
  dessine son pointillé en SVG pour qu'il reste régulier dans les angles.
* **Un fond translucide sur les onglets mobiles** laissait le contenu défiler
  visiblement derrière les libellés. L'opacité y est volontairement haute.
* **Deux barres collantes s'empilent** : celle de l'éditeur se colle à
  `top-16`, sous l'en-tête de la coquille.

## 6. Accessibilité

Focus visible sur tous les interactifs, contrastes de texte tenus sur les
surfaces sombres, cibles tactiles ≥ 44 px sur la barre d'onglets, et
`prefers-reduced-motion` qui neutralise halos, balayages, liserés et
translations — sans jamais retirer une information.
