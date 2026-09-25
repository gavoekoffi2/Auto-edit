import { Link } from 'react-router-dom'
import Footer from '../components/layout/Footer'
import { BRAND } from '../brand'

/*
 * Pages légales minimales, alignées sur ce que la plateforme fait RÉELLEMENT
 * (voir PRIVACY.md à la racine du dépôt). À faire relire par un juriste et à
 * compléter avec l'identité de l'éditeur avant une ouverture à grande échelle.
 */

function Terms() {
  return (
    <>
      <h1 className="text-3xl font-bold">Conditions générales d&apos;utilisation</h1>
      <p className="text-dark-400">Dernière mise à jour : septembre 2026</p>

      <h2>1. Le service</h2>
      <p>
        {BRAND.name} est un service en ligne de montage vidéo automatique. Tu importes une vidéo,
        {' '}{BRAND.name} produit un montage (coupes, sous-titres, illustrations, sons) que tu peux télécharger.
      </p>

      <h2>2. Compte</h2>
      <p>
        Tu es responsable de la confidentialité de ton mot de passe et de l&apos;usage de ton compte.
        Un compte peut être suspendu en cas d&apos;abus (contenus illicites, tentative de contournement
        des limites, usage frauduleux des moyens de paiement).
      </p>

      <h2>3. Tes contenus</h2>
      <p>
        Tu restes propriétaire des vidéos que tu importes et des montages produits. Tu garantis
        disposer des droits nécessaires sur ces contenus (image des personnes filmées, musique, marques)
        et qu&apos;ils ne sont ni illégaux, ni haineux, ni diffamatoires. Tu nous autorises uniquement à les
        traiter pour fournir le service.
      </p>

      <h2>4. Offres et paiement</h2>
      <p>
        Le plan Free est gratuit dans la limite de ses quotas. Les plans payants (Pro, Enterprise)
        sont réglés via FedaPay (Mobile Money ou carte) et donnent accès au plan choisi pendant la
        durée indiquée au moment du paiement, sans reconduction automatique. Chaque paiement prolonge
        l&apos;abonnement en cours.
      </p>

      <h2>5. Conservation des fichiers</h2>
      <p>
        Les fichiers ne sont pas archivés indéfiniment : les montages terminés et les vidéos sources
        sont supprimés automatiquement après un délai limité (voir la politique de confidentialité).
        Pense à télécharger tes montages.
      </p>

      <h2>6. Disponibilité et responsabilité</h2>
      <p>
        Le service est fourni « en l&apos;état ». Nous faisons le maximum pour qu&apos;il soit disponible et
        que les montages soient réussis, sans pouvoir le garantir en toutes circonstances. Les éléments
        générés automatiquement (sous-titres, illustrations) peuvent contenir des erreurs : vérifie
        ton montage avant publication.
      </p>

      <h2>7. Contact</h2>
      <p>
        Pour toute question : <a href={`mailto:${BRAND.supportEmail}`}>{BRAND.supportEmail}</a>.
      </p>
    </>
  )
}

function Privacy() {
  return (
    <>
      <h1 className="text-3xl font-bold">Politique de confidentialité</h1>
      <p className="text-dark-400">Dernière mise à jour : septembre 2026</p>

      <h2>Données collectées</h2>
      <p>
        Ton email, ton nom (facultatif), un mot de passe chiffré (jamais stocké en clair), les vidéos
        que tu importes, les montages produits et l&apos;historique de tes paiements (montant, plan,
        statut — aucune donnée de carte ou de Mobile Money n&apos;est stockée chez nous).
      </p>

      <h2>Ce qui est partagé avec des prestataires</h2>
      <ul>
        <li>
          <strong>Transcription</strong> : la piste audio peut être envoyée à ElevenLabs pour être
          transcrite. Sans ce prestataire, la transcription est faite sur nos serveurs.
        </li>
        <li>
          <strong>Analyse et illustrations</strong> : le texte transcrit (pas la vidéo) peut être envoyé
          à un modèle d&apos;IA via OpenRouter pour repérer les moments forts et générer des illustrations.
        </li>
        <li><strong>Paiement</strong> : FedaPay traite les paiements.</li>
      </ul>
      <p>La vidéo elle-même n&apos;est jamais envoyée à un prestataire d&apos;IA : le rendu est fait sur nos serveurs.</p>

      <h2>Durée de conservation</h2>
      <ul>
        <li>Montages terminés : supprimés automatiquement après 14 jours.</li>
        <li>Vidéos sources : supprimées automatiquement après 30 jours.</li>
        <li>Fichiers des traitements échoués : 2 jours.</li>
        <li>Compte et historique de paiements : tant que le compte existe.</li>
      </ul>
      <p>
        Tu peux supprimer à tout moment une vidéo et ses montages depuis ton tableau de bord.
        Pour supprimer ton compte ou exercer tes droits d&apos;accès et de rectification, écris à{' '}
        <a href={`mailto:${BRAND.supportEmail}`}>{BRAND.supportEmail}</a>.
      </p>
    </>
  )
}

export default function Legal({ page }: { page: 'terms' | 'privacy' }) {
  return (
    <div>
      <article className="legal mx-auto max-w-3xl space-y-4 px-4 py-12 text-dark-300 sm:px-6 [&_a]:text-primary-400 [&_a]:underline [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-white [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6">
        {page === 'terms' ? <Terms /> : <Privacy />}
        <p className="pt-6 text-sm">
          <Link to={page === 'terms' ? '/privacy' : '/terms'}>
            {page === 'terms' ? 'Politique de confidentialité' : "Conditions générales d'utilisation"}
          </Link>
        </p>
      </article>
      <Footer />
    </div>
  )
}
