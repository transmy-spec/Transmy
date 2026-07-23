import { ref } from 'vue'

export type Locale = 'fr' | 'en'

const STORAGE_KEY = 'transmissions.locale'
const configuredLocale = import.meta.env.VITE_DEFAULT_LOCALE === 'en' ? 'en' : 'fr'

export const locale = ref<Locale>(
  globalThis.localStorage?.getItem(STORAGE_KEY) === 'en'
    ? 'en'
    : globalThis.localStorage?.getItem(STORAGE_KEY) === 'fr'
      ? 'fr'
      : configuredLocale,
)

const messages = {
  fr: {
    loading: 'Ouverture de Transmissions...',
    welcome: 'Bienvenue',
    loginIntro: 'Connectez-vous pour accéder à votre espace de travail et à votre périmètre autorisé.',
    login: 'Se connecter avec Keycloak',
    demoAccounts: 'Comptes de démonstration locale',
    secureEnvironment: 'Environnement local sécurisé',
    loginPromise: 'Une information utile, au bon professionnel.',
    loginScope: 'Les accès sont limités par rôle, établissement, service et unité.',
    navigation: 'Navigation principale',
    dashboard: 'Tableau de bord',
    people: 'Personnes accompagnées',
    plans: 'Projets personnalisés',
    transmissions: 'Transmissions',
    work: 'Tâches et relèves',
    schedule: 'Planning',
    pilotage: 'Pilotage',
    notifications: 'Notifications',
    operations: 'Conservation et exports',
    integrations: 'Intégrations locales',
    readiness: 'Préparation pilote',
    acceptance: 'Recette métier',
    issues: 'Anomalies pilote',
    team: 'Équipe et accès',
    structure: 'Structure',
    audit: 'Journal d’audit',
    access: 'Mon accès',
    logout: 'Se déconnecter',
    openMenu: 'Ouvrir le menu',
    workContext: 'Contexte de travail',
    organizationAdmin: 'Administration de l’organisation',
    activeSession: 'Session active',
    workspace: 'Espace de travail',
    hello: 'Bonjour',
    security: 'Sécurité',
    account: 'Compte',
    activeRole: 'Rôle actif',
    scope: 'Périmètre',
    wholeOrganization: 'Organisation entière',
    session: 'Session',
    keycloakSession: 'Authentifiée par Keycloak',
    language: 'Langue de l’interface',
    languageHelp: 'Ce choix est appliqué immédiatement sur cet appareil.',
    french: 'Français',
    english: 'English',
  },
  en: {
    loading: 'Opening Transmissions...',
    welcome: 'Welcome',
    loginIntro: 'Sign in to access your workspace and authorized scope.',
    login: 'Sign in with Keycloak',
    demoAccounts: 'Local demonstration accounts',
    secureEnvironment: 'Secure local environment',
    loginPromise: 'Useful information, shared with the right professional.',
    loginScope: 'Access is restricted by role, facility, service and unit.',
    navigation: 'Main navigation',
    dashboard: 'Dashboard',
    people: 'Supported people',
    plans: 'Personalized plans',
    transmissions: 'Transmissions',
    work: 'Tasks and handovers',
    schedule: 'Schedule',
    pilotage: 'Oversight',
    notifications: 'Notifications',
    operations: 'Retention and exports',
    integrations: 'Local integrations',
    readiness: 'Pilot readiness',
    acceptance: 'Acceptance testing',
    issues: 'Pilot issues',
    team: 'Team and access',
    structure: 'Organization',
    audit: 'Audit log',
    access: 'My access',
    logout: 'Sign out',
    openMenu: 'Open menu',
    workContext: 'Work context',
    organizationAdmin: 'Organization administration',
    activeSession: 'Active session',
    workspace: 'Workspace',
    hello: 'Hello',
    security: 'Security',
    account: 'Account',
    activeRole: 'Active role',
    scope: 'Scope',
    wholeOrganization: 'Entire organization',
    session: 'Session',
    keycloakSession: 'Authenticated by Keycloak',
    language: 'Interface language',
    languageHelp: 'This choice is applied immediately on this device.',
    french: 'Français',
    english: 'English',
  },
} as const

export type MessageKey = keyof typeof messages.fr

export function t(key: MessageKey): string {
  return messages[locale.value][key]
}

export function setLocale(nextLocale: Locale): void {
  locale.value = nextLocale
  globalThis.localStorage?.setItem(STORAGE_KEY, nextLocale)
  document.documentElement.lang = nextLocale
}

document.documentElement.lang = locale.value
