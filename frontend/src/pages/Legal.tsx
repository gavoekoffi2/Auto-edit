import type { ReactNode } from 'react'
import Footer from '../components/layout/Footer'
import { BRAND } from '../brand'

function LegalPage({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <div>
      <article className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1 className="text-3xl font-bold">{title}</h1>
        <p className="mt-2 text-sm text-dark-500">Dernière mise à jour : {updated}</p>
        <div className="mt-10 space-y-8 text-dark-300 leading-relaxed [&_h2]:mb-3 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-white [&_li]:ml-5 [&_li]:list-disc [&_ul]:space-y-1.5">
          {children}
        </div>
      </article>
      <Footer />
    </div>
  )
}

const mail = <a className="text-primary-400 underline" href={`mailto:${BRAND.supportEmail}`}>{BRAND.supportEmail}</a>

/** Politique de confidentialité — reflète ce que la plateforme fait réellement (voir PRIVACY.md). */
export function Privacy() {
  return (
    <LegalPage title="Politique de confidentialité" updated="septembre 2026">
      <section>
        <h2>Données collectées</h2>
        <ul>
          <li>Compte : email, nom (facultatif), mot de passe (stocké uniquement sous forme chiffrée irréversible).</li>
          <li>Contenus : les vidéos que tu envoies ou importes par lien, et les montages produits.</li>
          <li>Paiement : plan choisi, montant et statut. Les données de carte ou de Mobile Money sont traitées par FedaPay, jamais par {BRAND.name}.</li>
          <li>Technique : journaux de fonctionnement (identifiants de requête, erreurs), sans le contenu de tes vidéos.</li>
        </ul>
      </section>
      <section>
        <h2>Utilisation et prestataires</h2>
        <p>Tes données servent uniquement à fournir le service de montage. Selon la configuration du service :</p>
        <ul>
          <li>la piste <strong>audio</strong> peut être envoyée à ElevenLabs pour la transcription (sinon, transcription locale sur nos serveurs) ;</li>
          <li>le <strong>texte</strong> transcrit peut être envoyé à OpenRouter (modèles Google Gemini) pour détecter les moments forts, nettoyer les hésitations et décrire les illustrations à générer ;</li>
          <li>ta <strong>vidéo</strong> elle-même n'est jamais envoyée à un fournisseur d'IA : le rendu est fait sur nos serveurs.</li>
        </ul>
        <p className="mt-3">Ces prestataires appliquent leurs propres conditions. Nous ne vendons pas tes données et ne les utilisons pas à des fins publicitaires.</p>
      </section>
      <section>
        <h2>Durée de conservation</h2>
        <ul>
          <li>Montages terminés : supprimés automatiquement après 14 jours — pense à les télécharger.</li>
          <li>Vidéos importées par lien : supprimées après 7 jours.</li>
          <li>Fichiers des traitements échoués ou annulés : supprimés après 2 jours.</li>
          <li>Tu peux supprimer à tout moment une vidéo ou un montage depuis ton dashboard : les fichiers sont effacés du serveur.</li>
        </ul>
      </section>
      <section>
        <h2>Tes droits</h2>
        <p>
          Tu peux demander l'accès, la rectification ou la suppression de ton compte et de tes données en écrivant à {mail}.
          Nous répondons sous 30 jours.
        </p>
      </section>
      <section>
        <h2>Sécurité</h2>
        <p>Connexions chiffrées (HTTPS), mots de passe hachés, accès aux fichiers limité à leur propriétaire, sessions révoquées lors d'un changement de mot de passe.</p>
      </section>
    </LegalPage>
  )
}

/** Conditions générales d'utilisation. */
export function Terms() {
  return (
    <LegalPage title="Conditions d'utilisation" updated="septembre 2026">
      <section>
        <h2>Le service</h2>
        <p>
          {BRAND.name} monte automatiquement tes vidéos (coupes, sous-titres, motion design, sons). Le résultat est
          produit par des outils automatiques et d'IA : il peut contenir des imperfections, vérifie-le avant publication.
        </p>
      </section>
      <section>
        <h2>Ton compte</h2>
        <ul>
          <li>Tu es responsable de la confidentialité de ton mot de passe et de l'activité de ton compte.</li>
          <li>Un compte par personne ; les informations fournies doivent être exactes.</li>
        </ul>
      </section>
      <section>
        <h2>Tes contenus</h2>
        <ul>
          <li>Tu restes propriétaire de tes vidéos et des montages produits.</li>
          <li>Tu garantis détenir les droits nécessaires sur tout ce que tu envoies ou importes par lien (images, musique, personnes filmées).</li>
          <li>Sont interdits : contenus illégaux, haineux, violents, à caractère sexuel impliquant des mineurs, portant atteinte à la vie privée ou aux droits d'autrui. Nous pouvons suspendre un compte qui ne respecte pas ces règles.</li>
          <li>Les fichiers sont conservés pour une durée limitée (voir la politique de confidentialité) : télécharge tes montages.</li>
        </ul>
      </section>
      <section>
        <h2>Plans et paiement</h2>
        <ul>
          <li>Le plan gratuit inclut un nombre limité de montages par mois ; les montages échoués ou annulés ne sont pas décomptés.</li>
          <li>Les plans payants sont réglés via FedaPay (Mobile Money ou carte). Chaque paiement donne accès au plan pendant 30 jours, <strong>sans renouvellement automatique</strong>.</li>
          <li>Si un paiement est débité sans que ton plan soit activé, contacte {mail} avec la référence affichée : nous régularisons ou remboursons.</li>
        </ul>
      </section>
      <section>
        <h2>Disponibilité et responsabilité</h2>
        <p>
          Nous faisons de notre mieux pour que le service soit disponible et fiable, sans pouvoir le garantir en
          permanence. Notre responsabilité est limitée au montant payé au cours des 30 derniers jours.
        </p>
      </section>
      <section>
        <h2>Contact</h2>
        <p>Une question ? Écris-nous à {mail}.</p>
      </section>
    </LegalPage>
  )
}
