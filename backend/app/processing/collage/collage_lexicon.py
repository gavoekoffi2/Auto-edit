"""ANCRAGE LEXICAL — ce qui est DIT décide de ce qui est DESSINÉ.

Le défaut le plus visible du collage n'était pas la qualité des découpes, c'était
leur **pertinence**: quelqu'un parle de sa voiture, la scène montre un flacon et
une feuille. Trois causes, toutes traitées ici:

1. **Vocabulaire trop étroit.** La bibliothèque de découpes couvrait le discours
   e-commerce (colis, prix, avis). « Voiture », « maison », « ordinateur »,
   « rendez-vous » n'existaient pas — donc rien ne pouvait correspondre.
2. **Repli arbitraire.** Un mot inconnu retombait sur ``sha1(mot) % N``: une
   forme STABLE, mais sans aucun rapport. Stable et faux est pire qu'absent,
   parce que ça se voit à chaque rendu.
3. **Aucune remontée du texte source.** Les objets venaient d'une bibliothèque
   d'intentions (prix → étiquette, pièces…), jamais des noms réellement
   prononcés. Le collage illustrait la CATÉGORIE du propos, pas son SUJET.

Ce module est la source de vérité du lien « mot prononcé → découpe ». Il expose:

    resolve("voiture")                 -> "car"        (strict, None si inconnu)
    ground("j'ai vendu ma voiture")    -> [Entity(car), Entity(handshake)…]

`collage_shapes` s'appuie dessus pour la résolution, et le planner s'en sert
pour ANCRER chaque concept sur les objets réellement nommés dans la phrase.

Règle d'écriture des motifs: tout mot court est ancré sur des limites de mot.
Le français piège en permanence — « car » (conjonction) n'est pas une voiture,
« montrer » n'est pas une montre, « livrer » n'est pas un livre. Chaque piège
connu a son test dans `tests/test_collage_grounding.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

__all__ = [
    "Entity", "LEXICON", "NOUNS", "ground", "resolve", "noun_for",
    "vocabulary_hint",
]


@dataclass(frozen=True)
class Entity:
    """Une chose nommée dans le discours, et la découpe qui la représente."""

    term: str          # le mot réellement prononcé ("voiture")
    pictogram: str     # la découpe ("car")
    noun: str          # le nom canonique anglais pour les prompts ("car")
    position: int      # index du mot dans la phrase (ordre de narration)


# --------------------------------------------------------------------------- #
# Nom canonique (anglais) de chaque découpe.
#
# Sert à deux choses: nommer un objet de concept quand on l'ancre depuis le
# texte, et décrire le vocabulaire dessinable au planner LLM. Les prompts du
# moteur sont en anglais: ces noms y entrent tels quels.
# --------------------------------------------------------------------------- #
NOUNS: dict[str, str] = {
    "arrow_up": "rising arrow", "bag": "paper bag", "ball": "ball",
    "banknote": "banknote", "battery": "battery", "book": "open book",
    "bottle": "bottle", "box": "cardboard box", "brain": "brain",
    "brick": "brick wall", "bridge": "bridge", "briefcase": "briefcase",
    "building": "building",
    "bulb": "light bulb", "calendar": "calendar", "camera": "camera",
    "car": "car", "card": "bank card", "cart": "shopping basket",
    "chain": "chain links", "chart": "bar chart", "chat": "speech bubble",
    "check": "check mark", "clock": "clock", "cloud": "cloud",
    "coins": "stack of coins", "cross": "cross mark", "crown": "crown",
    "cup": "coffee cup", "document": "sheet of paper", "door": "open door",
    "drop": "droplet", "dumbbell": "dumbbell", "envelope": "envelope",
    "eye": "eye", "flag": "flag", "flame": "flame", "folder": "folder",
    "gear": "gear", "gift": "gift box", "glasses": "glasses",
    "globe": "globe", "graduation": "graduation cap", "hand": "open hand",
    "handshake": "handshake", "heart": "heart", "hourglass": "hourglass",
    "house": "house", "jar": "cream jar", "key": "key", "ladder": "ladder",
    "laptop": "laptop", "leaf": "leaf", "lightning": "lightning bolt",
    "lock": "padlock", "magnifier": "magnifying glass",
    "megaphone": "megaphone", "mirror": "before and after panels",
    "mountain": "mountain", "music": "music note", "pen": "pen",
    "person": "person", "phone": "phone", "pill": "capsule",
    "pin": "location pin", "plane": "paper plane", "plate": "plate of food",
    "road": "road", "rocket": "rocket", "ring": "ring", "scale": "balance scale",
    "scissors": "scissors", "shield": "shield", "shirt": "shirt",
    "shoe": "shoe", "sparkle": "sparkle", "sprout": "sprout",
    "stairs": "staircase", "star": "star", "sun": "sun", "tag": "price tag",
    "target": "target", "thumb_up": "thumbs up", "tools": "hammer",
    "tree": "tree", "trophy": "trophy", "truck": "delivery truck",
    "tube": "tube", "umbrella": "umbrella", "wallet": "wallet",
    "watch": "wrist watch", "wifi": "signal waves",
}


# --------------------------------------------------------------------------- #
# LE LEXIQUE — français parlé et anglais, du plus spécifique au plus générique.
#
# L'ordre est signifiant: en cas de chevauchement, la règle listée d'abord
# gagne. C'est ainsi qu'on désamorce « je te livre le colis » (livraison) avant
# « j'ai lu un livre » (bouquin).
# --------------------------------------------------------------------------- #
LEXICON: list[tuple[str, str]] = [
    # ---- pièges à désamorcer en premier ---------------------------------- #
    # « je te livre le colis » ne doit pas donner un LIVRE: la forme verbale
    # « livre » n'est une livraison que suivie d'un complément.
    ("truck", r"livraison|livrais|livrée?s?\b|livrer|livreur|expédi|expedi|"
              r"transporteur|shipping|delivery|courier|\bcamions?\b|"
              r"\bvans?\b|\btrucks?\b|"
              r"\blivre\b(?=\s+(?:le|la|les|ton|ta|tes|votre|vos|en|à|a|chez|"
              r"demain|partout|gratuitement))"),
    ("chat", r"\bavis\b|témoignage|temoignage|commentaire|\breviews?\b|"
             r"\bmessages?\b|\bdiscussion|\bsms\b|réponse|reponse"),

    # ---- transport & déplacement ----------------------------------------- #
    # « car » (conjonction) est bien trop fréquent en français pour servir
    # d'ancrage: seule la forme anglaise suivie d'un verbe est retenue.
    ("car", r"voiture|bagnole|automobile|véhicule|vehicule|\bautos?\b(?!-)|"
            r"\bcarburant\b|\bessence\b|\bvolant\b|\bpermis\b|\bgarage\b|"
            r"\bparking\b|conduire|\bcars?\b(?=\s+(?:is|was|are|park|drive))"),
    ("plane", r"\bavions?\b|\bvols?\b(?!\w)|aéroport|aeroport|\bvisas?\b|"
              r"voyage|voyager|à l'étranger|a l'etranger|\bplane\b|flight|"
              r"\btravel\b|décoller|decoller"),
    ("road", r"\broutes?\b|\bchemins?\b|parcours|\btrajets?\b|kilomètre|"
             r"kilometre|\bautoroute\b|\bvirage\b|\broad\b|\bjourney\b"),
    ("bridge", r"\bponts?\b|passerelle|\brelier\b|faire le lien|\bbridge\b|"
               r"\btraverser\b"),
    ("pin", r"\badresse\b|localisation|\bquartier\b|\bvilles?\b|\bendroit\b|"
            r"sur place|\blieu\b|\bzone\b|\blocation\b|\bmaps?\b"),
    ("globe", r"\bmondes?\b|international|mondial|\bplanète|\bplanete|"
              r"\bpays\b|\bafrique\b|\beurope\b|partout dans|\bglobal|"
              r"\bglobe\b|worldwide"),

    # ---- lieux de vie & de travail --------------------------------------- #
    ("house", r"\bmaisons?\b|appartement|\bapparts?\b|\bloyer\b|immobilier|"
              r"chez (moi|toi|lui|elle|nous|vous)|\bfoyer\b|\bhouse\b|"
              r"\bhome\b|\brent\b|logement"),
    ("building", r"\bimmeubles?\b|bâtiment|batiment|\bboutiques?\b|"
                 r"\bmagasins?\b|\blocal\b|\bbureaux?\b|\bentreprise\b|"
                 r"\bsociété\b|\bsociete\b|\bstore\b|\boffice\b|\busine\b"),
    ("briefcase", r"\bboulot\b|\btravail\b|\btaf\b|\bjobs?\b|\bmétier\b|"
                  r"\bmetier\b|carrière|carriere|\bemplois?\b|professionnel|"
                  r"\bbusiness\b|\bfreelance\b|\bmallette\b|\bwork\b"),
    ("door", r"\bportes?\b|opportunité|opportunite|\bseuil\b|\bentrée\b|"
             r"\bentree\b|\bouvrir la\b|\bdoor\b"),

    # ---- objets du quotidien --------------------------------------------- #
    ("laptop", r"ordinateur|\bpc\b|\blaptop\b|macbook|\bclavier\b|"
               r"site (web|internet)|\blogiciels?\b|\bapplications?\b|"
               r"\bappli\b|\bplateforme\b|\bcomputer\b|\bwebsite\b"),
    ("phone", r"téléphone|telephone|smartphone|\bmobile\b|\bportable\b|"
              r"\bwhatsapp\b|\bdm\b|\binsta|\btiktok\b|\bécran\b|\becran\b|"
              r"\bphone\b|\bappels?\b|\bappeler\b"),
    ("wifi", r"\bwifi\b|\binternet\b|connexion|\bréseau\b|\breseau\b|\b4g\b|"
             r"\b5g\b|\bdébit\b|\bdebit\b|\bconnecté|\bconnecte|\bsignal\b"),
    ("camera", r"\bcaméra\b|\bcamera\b|\bphotos?\b|\bvidéos?\b|\bvideos?\b|"
               r"\bfilmer\b|\btournage\b|\btourner une\b|\bobjectif photo\b|"
               r"\bcontenu\b|\bshoot\b"),
    # « son » est un possessif avant d'être un bruit: seule la forme
    # déterminée compte.
    ("music", r"\bmusiques?\b|\bchansons?\b|\ble son\b|\bdu son\b|\baudio\b|"
              r"\bmélodie\b|\bmelodie\b|\bplaylist\b|\bmusic\b|\bbeat\b"),
    ("cup", r"\btasse\b|\bcafés?\b|\bcafes?\b|\bthé\b|\bboissons?\b|"
            r"\bpause\b|\bcoffee\b|\bmug\b"),
    ("plate", r"\bassiettes?\b|\brepas\b|\bmanger\b|\bnourriture\b|"
              r"\bcuisine\b|\brestaurants?\b|\bresto\b|\bplats?\b|\bmenu\b|"
              r"\bfood\b|\bmeal\b|\brecette\b"),
    ("glasses", r"\blunettes?\b|\bglasses\b|\bmyopie\b|\bvue\b"),
    ("watch", r"\bmontres?\b|\bpoignet\b|\bwatch\b|\bchrono\b"),
    ("ring", r"\bbagues?\b|\bbijoux?\b|\bmariage\b|\bfiançailles\b|"
             r"\bfiancailles\b|\balliance\b|\bring\b|\bdiamant\b"),
    ("shoe", r"\bchaussures?\b|\bbaskets?\b|\bsneakers?\b|\bsemelle\b|"
             r"\bpieds?\b|\bshoes?\b|\btalons?\b"),
    ("shirt", r"\bvêtements?\b|\bvetements?\b|\brobes?\b|\bt-?shirts?\b|"
              r"\bpull\b|\bvestes?\b|\btenue\b|\btaille\b|"
              r"\bclothes\b|\bshirt\b"),
    ("umbrella", r"\bparapluie\b|\bpluie\b|\bimprévu\b|\bimprevu\b|"
                 r"\bassurance\b|\bumbrella\b|\bà l'abri\b"),
    ("scissors", r"\bciseaux\b|\bcouper\b|\bcoupes?\b|\bmontage\b|"
                 r"\bdécoupe\b|\bdecoupe\b|\bscissors\b|\btrim\b"),
    ("tools", r"\bmarteau\b|\boutils?\b|\bréparer\b|\breparer\b|\btravaux\b|"
              r"\bbricolage\b|\bchantier\b|\bconstruire\b|\btools?\b|"
              r"\bhammer\b|\bfix\b"),
    ("pen", r"\bstylos?\b|\bsigner\b|\bsignature\b|\bécrire\b|\becrire\b|"
            r"\bnoter\b|\bpen\b|\bsign\b"),
    ("battery", r"\bbatteries?\b|\bautonomie\b|\brecharge\b|\bénergie\b|"
                r"\benergie\b|\bbattery\b"),
    ("bulb", r"\bampoules?\b|\bidées?\b|\bidees?\b|\binspiration\b|"
             r"\bélectricité\b|\belectricite\b|\bdéclic\b|\bdeclic\b|"
             r"\bidea\b|\bbulb\b|\bcourant\b"),

    # ---- corps, santé, apparence ----------------------------------------- #
    ("pill", r"\bgélules?\b|\bgelules?\b|\bcomprimés?\b|\bcomprimes?\b|"
             r"\bmédicaments?\b|\bmedicaments?\b|\bpilules?\b|\bcures?\b|"
             r"\btraitement\b|\bpills?\b|\bcapsules?\b|\bcomplément\b|"
             r"\bcomplement\b"),
    ("brain", r"\bcerveau\b|\bmental\b|\bmémoire\b|\bmemoire\b|\bapprendre\b|"
              r"\bcomprendre\b|\bréfléch|\brefléch|\breflech|\bmindset\b|"
              r"\bbrain\b|\bpsycho"),
    ("eye", r"\bœil\b|\boeil\b|\byeux\b|\bregard\b|\bvisibilité\b|"
            r"\bvisibilite\b|\bremarqué|\bremarque\b|\battention\b|\beyes?\b|"
            r"\bvoir\b|\bvues\b"),
    ("dumbbell", r"\bmuscu\b|\bsalle de sport\b|\bfitness\b|\bhaltères?\b|"
                 r"\bhalteres?\b|\bentraînement\b|\bentrainement\b|"
                 r"\bmuscles?\b|\bgym\b|\bworkout\b"),
    ("ball", r"\bballons?\b|\bfoot\b|\bmatchs?\b|\béquipe\b|\bequipe\b|"
             r"\bsport collectif\b|\bball\b|\bsoccer\b"),

    # ---- nature & temps --------------------------------------------------- #
    ("tree", r"\barbres?\b|\bforêt\b|\bforet\b|\bplantes?\b|\bjardin\b|"
             r"\bplanter\b|\btrees?\b|\bracines?\b"),
    ("sprout", r"\bgraines?\b|\bpousses?\b|\bgermer\b|\bdébut\b|\bdebut\b|"
               r"\bdémarr|\bdemarr|\bcommencement\b|\bpremiers pas\b|"
               r"\bseed\b|\bsprout\b|\bstart from\b"),
    ("sun", r"\bsoleil\b|\bjournée\b|\bjournee\b|\bété\b|\bsummer\b|"
            r"\bsun\b|\blumière du jour\b"),
    ("cloud", r"\bnuages?\b|\bcloud\b|\bstockage\b|\bmétéo\b|\bmeteo\b|"
              r"\bsauvegarde\b|\bbackup\b"),
    ("mountain", r"\bmontagnes?\b|\bsommet\b|\bobstacles?\b|\bfalaise\b|"
                 r"\bgrimper\b|\bmountain\b|\bpeak\b"),
    ("hourglass", r"\bsabliers?\b|compte à rebours|compte a rebours|"
                  r"\bplus que quelques\b|\btemps qui passe\b|\bdeadline\b|"
                  r"\bhourglass\b|\bil reste peu\b"),
    ("calendar", r"\bcalendriers?\b|\bdates?\b|\bsemaines?\b|\bmois\b|"
                 r"\bplanning\b|\brendez-vous\b|\brdv\b|\bagenda\b|"
                 r"\broutine\b|\bcalendar\b|\bschedule\b"),
    ("clock", r"\bhorloges?\b|\bheures?\b|\bminutes?\b|\btemps\b|\bdurée\b|"
              r"\bduree\b|\brapide(?:ment)?\b|\bclock\b|\btime\b|\bvite\b"),

    # ---- argent ----------------------------------------------------------- #
    ("tag", r"\bétiquettes?\b|\betiquettes?\b|\bprix\b|\btarifs?\b|\bpromo|"
            r"\bréduction\b|\breduction\b|\bsoldes?\b|\bdiscount\b|"
            r"\bprice tag\b|pas cher|moins cher"),
    ("banknote", r"\bbillets?\b|\bargent\b|\bcash\b|\bsalaires?\b|\brevenus?\b|"
                 r"\bcash-?flow\b|\bchiffre d'affaires?\b|\bbanknote\b|"
                 r"\bmoney\b|\bfrancs?\b|\beuros?\b|\bcfa\b|\bdollars?\b"),
    ("coins", r"\bpièces?\b|\bpieces?\b|\bmonnaie\b|\béconomies?\b|"
              r"\beconomies?\b|\bépargne\b|\bepargne\b|\bcoins?\b|"
              r"\bcentimes?\b|\bbudget\b"),
    ("card", r"carte bancaire|\bvisa card\b|\bmastercard\b|paiement par carte|"
             r"\bcarte de crédit\b|\bcarte de credit\b|\bcredit card\b|"
             r"\babonnement\b|\bprélèvement\b|\bprelevement\b"),
    ("wallet", r"\bportefeuilles?\b|\bporte-monnaie\b|\bpoche\b|\bwallet\b|"
               r"\bpouvoir d'achat\b"),
    ("cart", r"\bpaniers?\b|\bcaddie\b|\bcommandes?\b|\bcommander\b|"
             r"\bacheter\b|\bachats?\b|\bcheckout\b|\bcart\b|\bboutique en\b"),
    ("gift", r"\bcadeaux?\b|\bbonus\b|\boffert\b|\bgratuit\b|\bsurprises?\b|"
             r"\bgifts?\b|\bfree\b|\bruban\b"),

    # ---- produit & preuve -------------------------------------------------- #
    ("box", r"\bcartons?\b|\bboîtes?\b|\bboites?\b|\bemballage\b|\bcolis\b|"
            r"\bpackaging\b|\bcoffrets?\b|\bparcels?\b|\bbox\b|\bunboxing\b"),
    ("bottle", r"\bflacons?\b|\bbouteilles?\b|\bsprays?\b|\bvaporisateur\b|"
               r"\bparfums?\b|\bshampo\b|\bsérums?\b|\bserums?\b|\bbottle\b"),
    ("jar", r"\bpots?\b|\bcrèmes?\b|\bcremes?\b|\bbaumes?\b|\bmasques?\b|"
            r"\bbeurre\b|\bjar\b|\bcream\b"),
    ("tube", r"\btubes?\b|\bdentifrice\b|\bgels?\b|\blotions?\b|\bmascara\b|"
             r"\brouge à lèvres\b|\brouge a levres\b"),
    ("bag", r"\bsacs?\b|\bsachets?\b|\bpochettes?\b|\bpouch\b"),
    ("leaf", r"\bfeuilles?\b|\bnaturel(?:le)?s?\b|(?<!en )\bbio\b|"
             r"\bingrédients?\b|\bingredients?\b|\bcomposition\b|"
             r"\bvégétal|\bvegetal|\bplant-based\b|\bleaf\b"),
    ("drop", r"\bgouttes?\b|\beau\b|\bhydrat|\bliquides?\b|\bhuiles?\b|"
             r"\btextures?\b|\bdrops?\b|\bwater\b|\boil\b|\bsérum liquide\b"),
    ("star", r"\bétoiles?\b|\betoiles?\b|\bnotes?\b|\bnotation\b|\bratings?\b|"
             r"\bstars?\b|\b5 sur 5\b|\bnoté\b|\bnote\b"),
    ("thumb_up", r"\bpouce\b|\blike[sr]?\b|\bapprouv|\brecommand|\bthumbs?\b|"
                 r"\bvalidé\b|\bvalide\b"),
    ("heart", r"\bcœurs?\b|\bcoeurs?\b|\badore\b|\bamour\b|\bfavoris?\b|"
              r"\bpréfér|\bprefer|\bkiff|\bhearts?\b|\blove\b"),
    ("chart", r"\bgraphiques?\b|\bcourbes?\b|\bstatistiques?\b|\bstats?\b|"
              r"\bchiffres?\b|\bperformances?\b|\bventes?\b|\bcharts?\b|"
              r"\bbarres?\b"),
    ("arrow_up", r"\bflèches?\b|\bfleches?\b|\bmonter\b|\baugment|\bprogress|"
                 r"\bcroissance\b|\baméliorer\b|\bameliorer\b|\bgrowth\b|"
                 r"\bmieux\b"),
    ("magnifier", r"\bloupes?\b|\bzoom\b|\bdétails?\b|\bdetails?\b|"
                  r"\banalyse\b|\binspect|\bexaminer\b|\bde près\b|"
                  r"\bmagnif"),
    ("scale", r"\bbalances?\b|\bcomparer\b|\bcomparaison\b|\béquilibre\b|"
              r"\bequilibre\b|\bpeser\b|\bversus\b|\bvs\b|\bd'un côté\b|"
              r"\bd'un cote\b|\bscale\b"),
    ("mirror", r"\bmiroirs?\b|\bavant.{0,10}après\b|\bavant.{0,10}apres\b|"
               r"\bbefore.{0,10}after\b|\btransformation\b|\bmétamorphose\b"),

    # ---- réussite, sécurité, obstacles ------------------------------------ #
    ("trophy", r"\btrophées?\b|\btrophees?\b|\bcoupes? du\b|\bmédailles?\b|"
               r"\bmedailles?\b|\bchampions?\b|\bgagné\b|\bgagne[rz]?\b|"
               r"\bvictoire\b|\bnuméro un\b|\bnumero un\b|\btrophy\b|"
               r"\bwinner\b"),
    ("crown", r"\bcouronnes?\b|\bpremium\b|\bluxe\b|haut de gamme|\broi\b|"
              r"\breine\b|\bvip\b|\bcrown\b|\bélite\b|\belite\b"),
    ("target", r"\bcibles?\b|\bobjectifs?\b|\bbuts?\b|\bviser\b|"
               r"\bdans le mille\b|\btargets?\b|\bgoals?\b"),
    ("flag", r"\bdrapeaux?\b|\bétape franchie\b|\bjalon\b|\bmilestone\b|"
             r"\bflags?\b"),
    ("stairs", r"\bescaliers?\b|\bétapes?\b|\betapes?\b|\bpaliers?\b|"
               r"\bniveaux?\b|\bstairs?\b|\bsteps?\b|\bprogressivement\b"),
    ("ladder", r"\béchelles?\b|\bechelles?\b|\bgrimper\b|\bmonter d'un\b|"
               r"\bladder\b|\bbarreau\b"),
    ("brick", r"\bbriques?\b|\bmurs?\b|\bbâtir\b|\bbatir\b|\bfondations?\b|"
              r"\bbricks?\b|\bwall\b|pierre par pierre"),
    ("gear", r"\bengrenages?\b|\bsystèmes?\b|\bsystemes?\b|\bmécanisme\b|"
             r"\bmecanisme\b|\bfonctionnement\b|\bréglages?\b|\breglages?\b|"
             r"\bparamètres?\b|\bparametres?\b|\bgears?\b|\bprocessus\b"),
    # « lien en bio » est un appel à l'achat, pas une chaîne.
    ("chain", r"\bchaînes?\b|\bchaines?\b|\bmaillons?\b|\bliens?\b(?! en bio)|"
              r"\bchain\b|\bconnecté(?:es?|s)? entre\b"),
    ("rocket", r"\bfusées?\b|\bfusees?\b|\bdécollage\b|\bdecollage\b|"
               r"\blancement\b|\blancer\b|\bexplose\b|\brockets?\b|"
               r"\blaunch\b|\bboost\b"),
    ("lightning", r"\béclairs?\b|\beclairs?\b|\bfoudre\b|\binstantané\b|"
                  r"\binstantane\b|\ben un clin\b|\bflash\b|\bchoc\b|"
                  r"\blightning\b"),
    ("shield", r"\bboucliers?\b|\bgarantie\b|\bsécuri|\bsecuri|\bprotég|"
               r"\bproteg|\bprotect|\bsans risque\b|\bshield\b|\bcertifi"),
    ("lock", r"\bcadenas\b|\bverrous?\b|\bsecrets?\b|\bexclusi|\baccès\b|"
             r"\bacces\b|\bprivé\b|\bprive\b|\block\b|\bpassword\b|"
             r"\bmot de passe\b"),
    ("key", r"\bclés?\b|\bclefs?\b|\bdébloqu|\bdebloqu|\bdéverrouill|"
            r"\bdeverrouill|\bsolutions?\b|\bkeys?\b|\bunlock\b"),
    ("cross", r"\bcroix\b|\berreurs?\b|\bproblèmes?\b|\bproblemes?\b|"
              r"\béviter\b|\beviter\b|\barnaques?\b|\bfaux\b|\bratés?\b|"
              r"\brates?\b|\bmistakes?\b|\bfail\b|\bne marche pas\b"),
    ("check", r"\bcoches?\b|\bvalider\b|\binclus\b|\brésolu\b|\bresolu\b|"
              r"\bréglé\b|\bc'est bon\b|\bcheck\b|\bdone\b|\bok\b"),
    ("flame", r"\bflammes?\b|\bfeu\b|\btendance\b|\bviral\b|\bcartonne\b|"
              r"\bexplos|\bchaud\b|\bhype\b|\bfire\b|\bhot\b"),
    ("sparkle", r"\béclat\b|\beclat\b|\bbrill|\bglow\b|\brésultats?\b|"
                r"\bresultats?\b|\beffets?\b|\bwaouh\b|\bwow\b|\bmagie\b|"
                r"\bsparkle\b"),

    # ---- gens, papiers, communication -------------------------------------- #
    ("graduation", r"\bécoles?\b|\becoles?\b|\bétudiants?\b|\betudiants?\b|"
                   r"\bdiplômes?\b|\bdiplomes?\b|\bformations?\b|"
                   r"(?<!au )\bcours\b|\buniversité\b|\buniversite\b|"
                   r"\bapprentissage\b|\bgraduation\b|\btraining\b"),
    ("book", r"\blivres?\b|\bbouquins?\b|\blecture\b|\bchapitres?\b|"
             r"\bebooks?\b|\bguides?\b|\bbooks?\b|\bmanuel\b"),
    ("document", r"\bdocuments?\b|\bfactures?\b|\bcontrats?\b|\bpapiers?\b|"
                 r"\badministrat|\bdevis\b|\battestation\b|\bformulaire\b|"
                 r"\bpaperwork\b"),
    ("folder", r"\bdossiers?\b|\bfichiers?\b|\bclasser\b|\barchives?\b|"
               r"\bfolder\b|\bfiles?\b"),
    ("envelope", r"\benveloppes?\b|\bcourriers?\b|\bmails?\b|\be-?mails?\b|"
                 r"\blettres?\b|\bnewsletter\b|\benvelope\b"),
    ("megaphone", r"\bmégaphone\b|\bmegaphone\b|\bannonces?\b|\bpublicité\b|"
                  r"\bpublicite\b|\bpubs?\b|\bmarketing\b|\bcommuniquer\b|"
                  r"\bpartager\b|\bmegaphone\b|\bshout\b"),
    # « d'accord » est un tic de langage: seul l'accord CONCLU compte.
    ("handshake", r"\bpoignée de main\b|\bpoignee de main\b|\bpartenariat\b|"
                  r"\bpartenaires?\b|\bdeals?\b|\bs'entendre\b|"
                  r"\bhandshake\b|\bnégoci|\bnegoci|\baccord (?:commercial|"
                  r"signé|conclu|gagnant)\b"),
    ("person", r"\bpersonnes?\b|\bclients?\b|\bgens\b|\butilisateurs?\b|"
               r"\bfemmes?\b|\bhommes?\b|\bvisages?\b|\bcustomers?\b|"
               r"\busers?\b|\bsilhouette\b|\bpublic\b|\bcommunauté\b|"
               r"\bcommunaute\b"),
    ("hand", r"\bmains?\b|\bpaume\b|\bgestes?\b|\btenir\b|\bdoigts?\b|"
             r"\bhands?\b|\bholding\b"),

    # ---- vocabulaire des bibliothèques de métaphores ----------------------- #
    # Les profils décrivent leurs objets en anglais générique (« rising bar »,
    # « speech bubble », « padlock »). Ces termes sont écrits par le produit,
    # pas prononcés par les gens: ils arrivent EN DERNIER pour ne jamais
    # préempter une règle française sur du transcript réel.
    ("arrow_up", r"\barrows?\b|\brising (?:bar|line)\b|\bupward\b|\bincoming\b"),
    ("chart", r"\bscattered dots\b|\baxis\b|\brow of squares\b|\bbars?\b"),
    ("chat", r"\b(?:speech|second) bubble\b|\bbubbles?\b"),
    ("lock", r"\bpadlocks?\b"),
    ("card", r"\bbank cards?\b"),
    ("stairs", r"\bstaircase\b|\bpedestal\b"),
    ("wifi", r"\bsound waves\b|\bwaves\b"),
    ("cross", r"\bwarning triangle\b"),
    ("box", r"\bshelf\b"),
    ("document", r"\bsigned sheet\b|\bseal\b|\bsheet\b"),
    ("target", r"\bcircle\b|\bbow\b|\brings?\b"),
    ("person", r"\bears?\b|\bcrowd\b"),
    ("sun", r"\blight beam\b|\bbeam\b"),
    ("cloud", r"\bsmoke plume\b|\bplume\b|\bsmoke\b"),
    ("chain", r"\bthreads?\b|\bnetwork nodes?\b|\bnodes?\b|\boverlap shape\b"),
    ("road", r"\bopen path\b|\bpaths?\b"),
    ("plate", r"\bcracked plate\b"),
    ("door", r"\bshutters?\b"),
    ("gear", r"\bbelts?\b|\blevers?\b"),
    ("hourglass", r"\bfalling sand\b|\bsand\b"),
    ("flame", r"\bmatch\b|\bspark\b"),
    ("drop", r"\bfalling piece\b"),
]

_COMPILED: list[tuple[str, re.Pattern[str]]] = [
    (pictogram, re.compile(pattern, re.I | re.UNICODE))
    for pictogram, pattern in LEXICON
]

#: Un mot d'ancrage doit être un vrai nom, pas un fragment. En dessous de cette
#: longueur, on refuse de fonder une scène entière sur la correspondance.
_MIN_TERM_LEN = 2


# --------------------------------------------------------------------------- #
def resolve(name: Optional[str]) -> Optional[str]:
    """Découpe correspondant à *name*, ou **None** si rien ne correspond.

    Volontairement STRICT: renvoyer None est une information exploitable
    (« je ne sais pas dessiner ça »), alors qu'une forme au hasard est un
    mensonge visuel. Les appelants décident quoi faire du None — le planner
    remplace l'objet, le rendu prend une forme neutre.
    """
    text = (name or "").strip()
    if not text:
        return None
    key = text.lower().replace(" ", "_").replace("-", "_")
    if key in NOUNS:
        return key
    for pictogram, pattern in _COMPILED:
        if pattern.search(text):
            return pictogram
    return None


def noun_for(pictogram: str) -> str:
    """Nom anglais canonique d'une découpe (pour les prompts et les objets)."""
    return NOUNS.get(pictogram, pictogram.replace("_", " "))


# --------------------------------------------------------------------------- #
def ground(text: str, *, limit: int = 6,
           exclude: Iterable[str] = ()) -> list[Entity]:
    """Les choses CONCRÈTES réellement nommées dans *text*, dans l'ordre dit.

    C'est le cœur de la précision d'illustration: la scène est construite à
    partir de ce que la personne prononce, pas d'une catégorie devinée. Deux
    mots qui pointent la même découpe ne comptent qu'une fois (une scène avec
    deux voitures n'illustre rien de plus qu'une scène avec une voiture).

    Les chevauchements sont arbitrés par l'ordre du LEXIQUE: « je te livre le
    colis » donne le camion, pas le livre.
    """
    if not text:
        return []
    banned = {str(x) for x in exclude}
    # 1) tous les emplacements où une découpe est nommée
    hits: list[tuple[int, int, int, str, str]] = []   # (start, -len, rank, picto, term)
    for rank, (pictogram, pattern) in enumerate(_COMPILED):
        if pictogram in banned:
            continue
        for match in pattern.finditer(text):
            term = match.group(0).strip()
            if len(term) < _MIN_TERM_LEN:
                continue
            hits.append((match.start(), -len(term), rank, pictogram, term))
    if not hits:
        return []

    # 2) arbitrage des chevauchements: à position égale, le terme le plus long
    #    puis la règle la plus spécifique (rang le plus faible) l'emportent.
    hits.sort()
    taken: list[tuple[int, int]] = []
    entities: list[Entity] = []
    seen: set[str] = set()
    for start, neg_len, _rank, pictogram, term in hits:
        end = start - neg_len
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue
        taken.append((start, end))
        if pictogram in seen:
            continue
        seen.add(pictogram)
        entities.append(Entity(term=term, pictogram=pictogram,
                               noun=noun_for(pictogram), position=start))
    return entities[:limit]


# --------------------------------------------------------------------------- #
def vocabulary_hint(max_terms: int = 44) -> str:
    """Liste des découpes disponibles, à donner au planner LLM.

    Un modèle qui ignore le vocabulaire dessinable propose « steering wheel »
    ou « supply chain »: rien de tout ça n'existe en découpe, et l'objet finit
    remplacé. Lui donner la liste supprime le problème à la source.
    """
    nouns = sorted({noun for noun in NOUNS.values()})
    return ", ".join(nouns[:max_terms])
