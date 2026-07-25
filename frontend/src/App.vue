<script setup lang="ts">
/* global Event, FormData, HTMLInputElement, HTMLSelectElement */
import { Activity, Archive, ArrowLeft, BarChart3, Bell, Building2, CalendarDays, CheckCircle2, CircleAlert, ClipboardCheck, ContactRound, Download, FileClock, Languages, LayoutDashboard, ListChecks, LogOut, Menu, Paperclip, Pencil, Plug, Plus, Printer, Search, Send, ShieldCheck, Target, Trash2, Users, X } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'

import { locale, setLocale, t, type Locale } from './i18n'

type Role = { code: string; label: string; scope_type: string; scope_id: string }
type WorkContext = { id: string; name: string; service_name: string; establishment_name: string }
type Session = { user: { id: string; username: string; display_name: string; email: string | null }; roles: Role[]; permissions: string[]; contexts: WorkContext[]; csrf_token: string }
type StructureRow = { establishment_name: string; service_id: string; service_name: string; unit_id: string | null; unit_name: string | null }
type Person = { id: string; internal_reference: string; family_name: string; given_name: string; preferred_name: string | null; birth_date: string | null; status: 'active' | 'archived'; archive_reason?: string | null; row_version: number; unit_id: string; unit_name: string; service_name: string; establishment_name: string }
type Reference = { id: string; code: string; label: string; color?: string; requires_acknowledgement?: boolean }
type Transmission = { id: string; person_id: string; author_id: string; family_name: string; given_name: string; preferred_name: string | null; status: 'draft' | 'published'; category_label: string; color: string; importance_code: string; importance_label: string; requires_acknowledgement: boolean; content: string; author_name: string; published_at: string | null; created_at: string; version_number: number; row_version: number; acknowledged: boolean }
type Task = { id: string; title: string; description: string; status: 'todo' | 'in_progress' | 'done' | 'cancelled'; due_at: string; priority: string; family_name: string | null; given_name: string | null; assignee_name: string | null; overdue: boolean; row_version: number }
type Handover = { id: string; unit_name: string; period_start: string; period_end: string; status: 'draft' | 'open' | 'closed'; creator_name: string; row_version: number; tasks?: Task[]; transmissions?: Transmission[] }
type RetentionPolicy = { data_type: string; retention_days: number | null; legal_basis: string | null; status: 'pilot_pending' | 'disabled'; purge_enabled: boolean; row_version: number }
type ExportResult = { id: string; status: string; record_count: number; sha256: string }
type Notification = { notification_key: string; kind: 'task' | 'transmission'; title: string; detail: string; occurred_at: string; severity: 'normal' | 'important' | 'urgent'; is_read: boolean }
type Membership = { id: string; unit_id: string; unit_name: string; service_name: string; is_primary: boolean; ends_at: string | null }
type User = { id: string; username: string; display_name: string; email: string | null; status: 'invited' | 'active' | 'disabled'; roles: string; units: string; memberships?: Membership[] }
type ScheduleEntry = { id: string; user_id: string; user_name: string; unit_name: string; entry_type: 'shift' | 'absence' | 'event'; starts_at: string; ends_at: string; label: string; participant_names: string[]; person_names: string[]; person_ids: string[]; approval_status: 'pending' | 'approved' | 'rejected'; invitation_status: 'pending' | 'accepted' | 'declined'; recurrence_group_id: string | null; created_by: string; row_version: number }
type PersonalizedGoal = { id: string; title: string; success_criteria: string; person_feedback: string; status: 'planned' | 'in_progress' | 'achieved' | 'adapted' | 'abandoned'; progress: number; target_date: string | null; row_version: number }
type ScheduleMember = { id: string; display_name: string }
type SchedulePerson = { id: string; display_name: string }
type Pilotage = { period: { days: number; start: string; end: string }; summary: { active_people: number; transmissions: number; urgent_transmissions: number; tasks_created: number; tasks_completed: number; tasks_overdue: number; completion_rate: number }; daily: { date: string; transmissions: number; tasks_completed: number }[]; alerts: { plans_overdue: number; plans_due_30_days: number; goals_overdue: number; goals_without_recent_follow_up: number; cancelled_events: number; events_without_review: number }; workload: { id: string; display_name: string; shift_hours: number; event_hours: number; absence_hours: number }[] }
type Attachment = { id: string; original_name: string; media_type: string; byte_size: number; sha256: string; scan_status: 'clean'; uploaded_by: string; created_at: string }
type Integration = { id: string; label: string; endpoint_url: string; status: 'disabled' | 'enabled'; last_tested_at: string | null; last_test_status: string | null; last_test_message: string | null; row_version: number }
type PilotDecision = { code: string; label: string; responsible: string; status: 'pending' | 'validated' | 'blocked'; evidence: string; row_version: number }
type Readiness = { decisions: PilotDecision[]; technical_checks: { code: string; label: string; passed: boolean }[]; summary: { validated: number; total: number; technical_passed: number; technical_total: number; ready: boolean } }
type AcceptanceScenario = { code: string; title: string; expected_result: string; status: 'pending' | 'passed' | 'failed' | 'blocked'; notes: string; tester_name: string | null; tested_at: string | null; row_version: number }
type PilotIssue = { id: string; acceptance_code: string | null; scenario_title: string | null; title: string; description: string; severity: 'minor' | 'major' | 'critical'; status: 'open' | 'in_progress' | 'resolved' | 'accepted'; creator_name: string; assigned_to: string | null; assignee_name: string | null; created_at: string; row_version: number }
type PersonalizedPlan = { id: string; status: 'draft' | 'active' | 'closed'; review_due_at: string | null; row_version: number; version_number: number; author_name: string; content: { person_expectations: string; strengths: string; assessed_needs: string; goals: string[]; actions: string[]; participation_method: string; consent_status: 'obtained' | 'refused' | 'unable'; consent_details: string; representative_name: string } }

const session = ref<Session | null>(null)
const loading = ref(true)
const notice = ref('')
const activationToken = ref('')
const activationDetails = ref<{ display_name: string; username: string; expires_at: string } | null>(null)
const activationPassword = ref('')
const activationConfirmation = ref('')
const activationComplete = ref(false)
const activeView = ref('dashboard')
const mobileNavOpen = ref(false)
const structure = ref<{ organization: { name: string }; items: StructureRow[] } | null>(null)
const users = ref<User[]>([])
const selectedUser = ref<User | null>(null)
const userReason = ref('')
const membershipUnit = ref('')
const invitationMode = ref(false)
const invitationForm = ref({ username: '', display_name: '', email: '', role_code: 'professional', unit_id: '' })
const invitationResult = ref<{ activation_url: string; expires_at: string } | null>(null)
const schedule = ref<ScheduleEntry[]>([])
const scheduleMembers = ref<ScheduleMember[]>([])
const schedulePeople = ref<SchedulePerson[]>([])
const scheduleWeek = ref(startOfWeek(new Date()))
const calendarMode = ref<'professionals' | 'people'>('professionals')
const printProfessionalId = ref('all')
const printPublicCopy = ref(true)
const scheduleForm = ref({ user_id: '', entry_type: 'shift', starts_at: '', ends_at: '', label: '', participant_ids: [] as string[], person_ids: [] as string[], link_personalized_plans: true, recurrence_weeks: 0 })
const editingEvent = ref<ScheduleEntry | null>(null)
const leaveForm = ref({ starts_at: '', ends_at: '', leave_type: 'paid_leave' })
const leaveMode = ref(false)
const pilotage = ref<Pilotage | null>(null)
const pilotageDays = ref(30)
const auditEvents = ref<Record<string, string>[]>([])
const newUnitName = ref('')
const saving = ref(false)
const people = ref<Person[]>([])
const selectedPerson = ref<Person | null>(null)
const peopleQuery = ref('')
const peopleStatus = ref<'active' | 'archived'>('active')
const personMode = ref<'list' | 'create' | 'detail' | 'edit'>('list')
const personForm = ref({ family_name: '', given_name: '', preferred_name: '', birth_date: '' })
const archiveReason = ref('')
const transmissions = ref<Transmission[]>([])
const selectedTransmission = ref<Transmission | null>(null)
const attachments = ref<Attachment[]>([])
const transmissionStatus = ref<'all' | 'published' | 'draft'>('all')
const transmissionMode = ref<'list' | 'create' | 'detail'>('list')
const transmissionReferences = ref<{ categories: Reference[]; importance_levels: Reference[] }>({ categories: [], importance_levels: [] })
const transmissionForm = ref({ person_id: '', category_id: '', importance_level_id: '', content: '' })
const tasks = ref<Task[]>([])
const taskStatus = ref('active')
const taskMode = ref<'list' | 'create'>('list')
const taskForm = ref({ title: '', description: '', due_at: '', priority: 'normal', person_id: '' })
const handovers = ref<Handover[]>([])
const selectedHandover = ref<Handover | null>(null)
const retentionPolicies = ref<RetentionPolicy[]>([])
const exportForm = ref({ export_type: 'activity_summary', format: 'json', reason: '' })
const latestExport = ref<ExportResult | null>(null)
const integrations = ref<Integration[]>([])
const integrationAllowedHosts = ref<string[]>([])
const integrationForm = ref({ label: '', endpoint_url: 'http://host.docker.internal:8080/events', status: 'disabled' })
const pilotReadiness = ref<Readiness | null>(null)
const acceptance = ref<{ items: AcceptanceScenario[]; summary: { passed: number; total: number; complete: boolean; failed: number } } | null>(null)
const pilotIssues = ref<{ items: PilotIssue[]; summary: { open: number; critical: number } } | null>(null)
const issueForm = ref({ acceptance_code: '', title: '', description: '', severity: 'minor', assigned_to: '' })
const personalizedPlan = ref<PersonalizedPlan | null>(null)
const planVersions = ref<{ version_number: number; created_at: string; author_name: string }[]>([])
const planEvents = ref<{ id: string; label: string; starts_at: string; ends_at: string; status: string }[]>([])
const planGoals = ref<PersonalizedGoal[]>([])
const goalForm = ref({ title: '', success_criteria: '', person_feedback: '', status: 'planned', progress: 0, target_date: '' })
const reviewEntry = ref<ScheduleEntry | null>(null)
const reviewForm = ref({ summary: '', next_steps: '', attendee_ids: [] as string[] })
const planForm = ref({ person_expectations: '', strengths: '', assessed_needs: '', goals: '', actions: '', participation_method: '', consent_status: 'obtained', consent_details: '', representative_name: '', review_due_at: '' })
const notifications = ref<Notification[]>([])
const unreadNotifications = computed(() => notifications.value.filter((item) => !item.is_read).length)
const scheduleDays = computed(() => Array.from({ length: 7 }, (_, index) => new Date(scheduleWeek.value.getTime() + index * 86400000)))
const printScheduleTitle = computed(() => {
  if (calendarMode.value === 'people') return 'Planning des personnes accompagnees'
  if (printProfessionalId.value === 'all') return 'Planning de l equipe'
  return `Planning de ${scheduleMembers.value.find((member) => member.id === printProfessionalId.value)?.display_name ?? ''}`
})
const isAdmin = computed(() => session.value?.permissions.includes('structure.manage') ?? false)
const initials = computed(() => (session.value?.user.display_name ?? '').split(' ').map((part) => part[0]).join('').slice(0, 2))
const currentContext = computed(() => session.value?.contexts[0] ?? null)
const navigation = computed(() => {
  const items = [{ id: 'dashboard', label: t('dashboard'), icon: LayoutDashboard }]
  if (session.value?.permissions.includes('person.search')) items.push({ id: 'people', label: t('people'), icon: ContactRound })
  if (session.value?.permissions.includes('personalized_plan.read')) items.push({ id: 'personalized-plans', label: t('plans'), icon: Target })
  if (session.value?.permissions.includes('transmission.read')) items.push({ id: 'transmissions', label: t('transmissions'), icon: Send })
  if (session.value?.permissions.includes('task.read')) items.push({ id: 'work', label: t('work'), icon: ListChecks })
  if (session.value?.permissions.includes('schedule.read')) items.push({ id: 'schedule', label: t('schedule'), icon: CalendarDays })
  if (session.value?.permissions.includes('pilotage.read')) items.push({ id: 'pilotage', label: t('pilotage'), icon: BarChart3 })
  if (session.value?.permissions.includes('notification.read')) items.push({ id: 'notifications', label: t('notifications'), icon: Bell })
  if (session.value?.permissions.includes('retention.read')) items.push({ id: 'operations', label: t('operations'), icon: Download })
  if (session.value?.permissions.includes('integration.read')) items.push({ id: 'integrations', label: t('integrations'), icon: Plug })
  if (session.value?.permissions.includes('pilot.read')) items.push({ id: 'readiness', label: t('readiness'), icon: ClipboardCheck })
  if (session.value?.permissions.includes('acceptance.read')) items.push({ id: 'acceptance', label: t('acceptance'), icon: CheckCircle2 })
  if (session.value?.permissions.includes('pilot_issue.read')) items.push({ id: 'pilot-issues', label: t('issues'), icon: CircleAlert })
  if (isAdmin.value) items.push({ id: 'users', label: t('team'), icon: Users }, { id: 'structure', label: t('structure'), icon: Building2 }, { id: 'audit', label: t('audit'), icon: FileClock })
  items.push({ id: 'access', label: t('access'), icon: ShieldCheck })
  return items
})

function updateLocale(event: Event) {
  setLocale((event.target as HTMLSelectElement).value as Locale)
}

async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const jsonBody = options.body && !(options.body instanceof FormData)
  const response = await fetch(url, { ...options, headers: { ...(jsonBody ? { 'Content-Type': 'application/json' } : {}), ...(session.value?.csrf_token ? { 'X-CSRF-Token': session.value.csrf_token } : {}), ...options.headers } })
  if (!response.ok) throw new Error(`La requête a échoué (${response.status}).`)
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}
function printPage() { globalThis.print() }
async function loadSession() { loading.value = true; try { session.value = await api<Session>('/api/v1/session') } catch { session.value = null } finally { loading.value = false } }
async function loadActivation() {
  const match = globalThis.location.hash.match(/^#activation=(.+)$/)
  if (!match) return false
  activationToken.value = decodeURIComponent(match[1])
  try {
    activationDetails.value = await api('/api/v1/account-activation/inspect', {
      method: 'POST',
      body: JSON.stringify({ token: activationToken.value }),
    })
  } catch {
    notice.value = 'Ce lien d activation est invalide ou expire.'
  }
  return true
}
async function completeActivation() {
  if (activationPassword.value.length < 12 || activationPassword.value !== activationConfirmation.value) return
  saving.value = true
  try {
    await api('/api/v1/account-activation/complete', {
      method: 'POST',
      body: JSON.stringify({ token: activationToken.value, password: activationPassword.value }),
    })
    activationComplete.value = true
    activationToken.value = ''
    globalThis.history.replaceState(null, '', '/')
  } catch {
    notice.value = 'Activation impossible. Le lien a peut-etre expire.'
  } finally {
    activationPassword.value = ''
    activationConfirmation.value = ''
    saving.value = false
  }
}
async function selectView(view: string) {
  activeView.value = view; mobileNavOpen.value = false; notice.value = ''
  try {
    if (view === 'structure') structure.value = await api('/api/v1/structure')
    if (view === 'users') {
      users.value = (await api<{ items: User[] }>('/api/v1/users')).items
      structure.value = await api('/api/v1/structure')
      selectedUser.value = null
    }
    if (view === 'audit') auditEvents.value = (await api<{ items: Record<string, string>[] }>('/api/v1/audit-events')).items
    if (view === 'people') await loadPeople()
    if (view === 'personalized-plans') await loadPlanPeople()
    if (view === 'transmissions') await loadTransmissions()
    if (view === 'work') await loadWork()
    if (view === 'schedule') await loadSchedule()
    if (view === 'pilotage') await loadPilotage()
    if (view === 'operations') await loadOperations()
    if (view === 'integrations') await loadIntegrations()
    if (view === 'readiness') await loadReadiness()
    if (view === 'acceptance') await loadAcceptance()
    if (view === 'pilot-issues') await loadPilotIssues()
    if (view === 'notifications') await loadNotifications()
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Une erreur est survenue.' }
}
async function loadPilotage() {
  pilotage.value = await api<Pilotage>(`/api/v1/pilotage?days=${pilotageDays.value}`)
}
function indicatorWidth(value: number) {
  if (!pilotage.value) return '0%'
  const maximum = Math.max(1, ...pilotage.value.daily.flatMap((day) => [day.transmissions, day.tasks_completed]))
  return `${Math.max(value ? 6 : 0, Math.round(value * 100 / maximum))}%`
}
function startOfWeek(date: Date) {
  const result = new Date(date); const day = result.getDay() || 7
  result.setDate(result.getDate() - day + 1); result.setHours(0, 0, 0, 0)
  return result
}
async function loadSchedule() {
  const end = new Date(scheduleWeek.value.getTime() + 7 * 86400000)
  const result = await api<{ items: ScheduleEntry[]; members: ScheduleMember[]; people: SchedulePerson[] }>(`/api/v1/schedule?start=${scheduleWeek.value.toISOString()}&end=${end.toISOString()}`)
  schedule.value = result.items; scheduleMembers.value = result.members; schedulePeople.value = result.people
  if (printProfessionalId.value !== 'all' && !scheduleMembers.value.some((member) => member.id === printProfessionalId.value)) printProfessionalId.value = 'all'
  if (session.value?.permissions.includes('schedule.manage')) users.value = (await api<{ items: User[] }>('/api/v1/users')).items.filter((user) => user.status === 'active')
  if (session.value?.permissions.includes('schedule.event.create')) people.value = (await api<{ items: Person[] }>('/api/v1/people?status=active')).items
}
function scheduleEntries(memberId: string, day: Date) {
  return schedule.value.filter((entry) => entry.user_id === memberId && new Date(entry.starts_at).toDateString() === day.toDateString())
}
function personScheduleEntries(personId: string, day: Date) {
  const matches = schedule.value.filter((entry) => entry.entry_type === 'event' && entry.person_ids.includes(personId) && new Date(entry.starts_at).toDateString() === day.toDateString())
  return [...new Map(matches.map((entry) => [entry.id, entry])).values()]
}
function scheduledHours(memberId: string, day: Date) {
  const milliseconds = scheduleEntries(memberId, day).filter((entry) => entry.entry_type === 'shift').reduce((total, entry) => total + new Date(entry.ends_at).getTime() - new Date(entry.starts_at).getTime(), 0)
  return milliseconds ? `${(milliseconds / 3600000).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} h` : ''
}
async function changeScheduleWeek(offset: number) {
  scheduleWeek.value = new Date(scheduleWeek.value.getTime() + offset * 7 * 86400000)
  await loadSchedule()
}
function prepareScheduleEntry() {
  const start = new Date(scheduleWeek.value); start.setHours(9)
  const end = new Date(start); end.setHours(17)
  editingEvent.value = null; leaveMode.value = false
  scheduleForm.value = { user_id: users.value[0]?.id ?? session.value?.user.id ?? '', entry_type: session.value?.permissions.includes('schedule.manage') ? 'shift' : 'event', starts_at: start.toISOString().slice(0, 16), ends_at: end.toISOString().slice(0, 16), label: '', participant_ids: session.value ? [session.value.user.id] : [], person_ids: [], link_personalized_plans: true, recurrence_weeks: 0 }
}
function prepareCalendarEvent(day: Date, memberId?: string) {
  const start = new Date(day); start.setHours(10, 0, 0, 0)
  const end = new Date(start); end.setHours(11)
  const participants = [session.value?.user.id, memberId].filter((value): value is string => Boolean(value))
  editingEvent.value = null; leaveMode.value = false
  scheduleForm.value = { user_id: session.value?.user.id ?? '', entry_type: 'event', starts_at: start.toISOString().slice(0, 16), ends_at: end.toISOString().slice(0, 16), label: '', participant_ids: [...new Set(participants)], person_ids: [], link_personalized_plans: true, recurrence_weeks: 0 }
}
async function createScheduleEntry() {
  if (!currentContext.value) return
  const body = JSON.stringify({ ...scheduleForm.value, unit_id: currentContext.value.id, starts_at: new Date(scheduleForm.value.starts_at).toISOString(), ends_at: new Date(scheduleForm.value.ends_at).toISOString() })
  if (editingEvent.value) await api(`/api/v1/schedule/${editingEvent.value.id}/event`, { method: 'PUT', headers: { 'If-Match': `"${editingEvent.value.row_version}"` }, body })
  else await api('/api/v1/schedule', { method: 'POST', body })
  notice.value = editingEvent.value ? 'L evenement a ete modifie.' : scheduleForm.value.entry_type === 'event' ? 'L evenement et les invitations ont ete ajoutes.' : 'Le planning a ete mis a jour.'; scheduleForm.value.starts_at = ''; editingEvent.value = null; await loadSchedule()
}
function editEvent(entry: ScheduleEntry) {
  editingEvent.value = entry; leaveMode.value = false
  scheduleForm.value = { user_id: entry.user_id, entry_type: 'event', starts_at: new Date(entry.starts_at).toISOString().slice(0, 16), ends_at: new Date(entry.ends_at).toISOString().slice(0, 16), label: entry.label, participant_ids: [], person_ids: [], link_personalized_plans: false, recurrence_weeks: 0 }
}
async function respondInvitation(entry: ScheduleEntry, response: 'accepted' | 'declined') {
  await api(`/api/v1/schedule/${entry.id}/invitation-response`, { method: 'POST', body: JSON.stringify({ response }) }); await loadSchedule()
}
function prepareLeave() {
  const start = new Date(scheduleWeek.value); start.setHours(8); const end = new Date(start); end.setHours(18)
  leaveForm.value = { starts_at: start.toISOString().slice(0, 16), ends_at: end.toISOString().slice(0, 16), leave_type: 'paid_leave' }; leaveMode.value = true; scheduleForm.value.starts_at = ''
}
async function requestLeave() {
  if (!currentContext.value) return
  await api('/api/v1/schedule/leave-requests', { method: 'POST', body: JSON.stringify({ ...leaveForm.value, unit_id: currentContext.value.id, starts_at: new Date(leaveForm.value.starts_at).toISOString(), ends_at: new Date(leaveForm.value.ends_at).toISOString() }) })
  notice.value = 'La demande de conge a ete transmise.'; leaveMode.value = false; await loadSchedule()
}
async function decideLeave(entry: ScheduleEntry, decision: 'approved' | 'rejected') {
  await api(`/api/v1/schedule/${entry.id}/leave-decision`, { method: 'POST', headers: { 'If-Match': `"${entry.row_version}"` }, body: JSON.stringify({ decision }) }); await loadSchedule()
}
async function cancelScheduleEntry(entry: ScheduleEntry) {
  await api(`/api/v1/schedule/${entry.id}/cancel`, { method: 'POST', headers: { 'If-Match': `"${entry.row_version}"` } })
  notice.value = 'Le creneau a ete annule.'; await loadSchedule()
}
async function openUser(user: User) {
  selectedUser.value = await api<User>(`/api/v1/users/${user.id}`)
  userReason.value = ''
  membershipUnit.value = structure.value?.items.find((item) => item.unit_id)?.unit_id ?? ''
}
function openInvitation() {
  invitationMode.value = true
  invitationResult.value = null
  invitationForm.value = {
    username: '',
    display_name: '',
    email: '',
    role_code: 'professional',
    unit_id: structure.value?.items.find((item) => item.unit_id)?.unit_id ?? '',
  }
}
async function createInvitation() {
  saving.value = true
  try {
    invitationResult.value = await api('/api/v1/users/invitations', {
      method: 'POST',
      body: JSON.stringify(invitationForm.value),
    })
    users.value = (await api<{ items: User[] }>('/api/v1/users')).items
  } catch (error) {
    notice.value = error instanceof Error ? error.message : 'Invitation impossible.'
  } finally {
    saving.value = false
  }
}
async function renewInvitation() {
  if (!selectedUser.value) return
  invitationResult.value = await api(`/api/v1/users/${selectedUser.value.id}/invitation`, { method: 'POST' })
}
async function revokeInvitation() {
  if (!selectedUser.value || userReason.value.trim().length < 5) return
  await api(`/api/v1/users/${selectedUser.value.id}/invitation/revoke`, {
    method: 'POST',
    body: JSON.stringify({ reason: userReason.value }),
  })
  notice.value = 'Invitation révoquée.'
}
function printInvitation() {
  globalThis.print()
}
async function changeUserStatus() {
  if (!selectedUser.value || userReason.value.trim().length < 5) return
  const next = selectedUser.value.status === 'active' ? 'disabled' : 'active'
  await api(`/api/v1/users/${selectedUser.value.id}/status`, { method: 'PATCH', body: JSON.stringify({ status: next, reason: userReason.value }) })
  notice.value = next === 'disabled' ? 'Le compte a ete desactive et ses sessions fermees.' : 'Le compte a ete reactive.'
  await selectView('users')
}
async function addUserMembership() {
  if (!selectedUser.value || !membershipUnit.value) return
  await api(`/api/v1/users/${selectedUser.value.id}/memberships`, { method: 'POST', body: JSON.stringify({ unit_id: membershipUnit.value, is_primary: true }) })
  notice.value = 'Le rattachement a ete ajoute. Les anciennes sessions ont ete fermees.'
  await openUser(selectedUser.value)
}
async function revokeUserMembership(membership: Membership) {
  if (!selectedUser.value || userReason.value.trim().length < 5) return
  await api(`/api/v1/users/${selectedUser.value.id}/memberships/${membership.id}/revoke`, { method: 'POST', body: JSON.stringify({ reason: userReason.value }) })
  notice.value = 'Le rattachement a ete retire immediatement.'
  await openUser(selectedUser.value)
}
async function loadNotifications() {
  const result = await api<{ items: Notification[]; unread_count: number }>('/api/v1/notifications')
  notifications.value = result.items
}
async function openNotification(item: Notification) {
  if (!item.is_read) await api('/api/v1/notifications/read', { method: 'POST', body: JSON.stringify({ keys: [item.notification_key] }) })
  await selectView(item.kind === 'task' ? 'work' : 'transmissions')
  await loadNotifications()
}
async function dismissNotification(item: Notification) {
  await api('/api/v1/notifications/dismiss', { method: 'POST', body: JSON.stringify({ keys: [item.notification_key] }) })
  await loadNotifications()
}
async function loadOperations() {
  const response = await fetch('/api/v1/retention-policies')
  if (!response.ok) throw new Error(`La requete a echoue (${response.status}).`)
  retentionPolicies.value = ((await response.json()) as { items: RetentionPolicy[] }).items
}
async function loadIntegrations() {
  const result = await api<{ items: Integration[]; allowed_hosts: string[] }>('/api/v1/integrations')
  integrations.value = result.items; integrationAllowedHosts.value = result.allowed_hosts
}
async function createIntegration() {
  await api('/api/v1/integrations', { method: 'POST', body: JSON.stringify(integrationForm.value) })
  integrationForm.value.label = ''; notice.value = 'Le connecteur local a ete cree desactive.'
  await loadIntegrations()
}
async function testIntegration(item: Integration) {
  const result = await api<{ status: string; message: string }>(`/api/v1/integrations/${item.id}/test`, { method: 'POST' })
  notice.value = result.status === 'success' ? 'Connexion locale validee.' : `Echec du test : ${result.message}`
  await loadIntegrations()
}
async function loadReadiness() { pilotReadiness.value = await api<Readiness>('/api/v1/pilot-readiness') }
async function savePilotDecision(item: PilotDecision) {
  await api(`/api/v1/pilot-readiness/${item.code}`, { method: 'PUT', headers: { 'If-Match': `"${item.row_version}"` }, body: JSON.stringify({ status: item.status, evidence: item.evidence }) })
  notice.value = 'La validation pilote a ete tracee.'; await loadReadiness()
}
async function loadAcceptance() { acceptance.value = await api('/api/v1/acceptance') }
async function saveAcceptance(item: AcceptanceScenario) {
  await api(`/api/v1/acceptance/${item.code}`, { method: 'PUT', headers: { 'If-Match': `"${item.row_version}"` }, body: JSON.stringify({ status: item.status, notes: item.notes }) })
  notice.value = 'Le resultat de recette a ete trace.'; await loadAcceptance()
}
async function loadPilotIssues() {
  const requests: Promise<unknown>[] = [api('/api/v1/pilot-issues')]
  if (!acceptance.value) requests.push(api('/api/v1/acceptance'))
  if (!users.value.length) requests.push(api<{ items: User[] }>('/api/v1/users'))
  const results = await Promise.all(requests)
  pilotIssues.value = results[0] as typeof pilotIssues.value
  let resultIndex = 1
  if (!acceptance.value) acceptance.value = results[resultIndex++] as typeof acceptance.value
  if (!users.value.length) users.value = (results[resultIndex] as { items: User[] }).items.filter((user) => user.status === 'active')
}
async function createPilotIssue() {
  await api('/api/v1/pilot-issues', { method: 'POST', body: JSON.stringify({ ...issueForm.value, acceptance_code: issueForm.value.acceptance_code || null, assigned_to: issueForm.value.assigned_to || null }) })
  issueForm.value = { acceptance_code: '', title: '', description: '', severity: 'minor', assigned_to: '' }
  notice.value = 'L anomalie pilote a ete enregistree.'
  await loadPilotIssues(); await loadReadiness()
}
async function updatePilotIssue(item: PilotIssue) {
  await api(`/api/v1/pilot-issues/${item.id}`, { method: 'PUT', headers: { 'If-Match': `"${item.row_version}"` }, body: JSON.stringify({ status: item.status, assigned_to: item.assigned_to || null }) })
  notice.value = 'Le suivi de l anomalie a ete actualise.'
  await loadPilotIssues(); await loadReadiness()
}
async function saveRetention(policy: RetentionPolicy) {
  saving.value = true
  try {
    await api(`/api/v1/retention-policies/${policy.data_type}`, { method: 'PUT', headers: { 'If-Match': `"${policy.row_version}"` }, body: JSON.stringify({ retention_days: policy.retention_days, legal_basis: policy.legal_basis || null, status: policy.status }) })
    notice.value = 'La politique a ete enregistree. La purge reste desactivee.'
    await loadOperations()
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Enregistrement impossible.' }
  finally { saving.value = false }
}
async function createExport() {
  saving.value = true
  try {
    latestExport.value = await api<ExportResult>('/api/v1/exports', { method: 'POST', body: JSON.stringify(exportForm.value) })
    notice.value = 'L export temporaire est pret pendant 15 minutes.'
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Export impossible.' }
  finally { saving.value = false }
}
async function downloadExport() {
  if (!latestExport.value) return
  const ticket = await api<{ download_url: string }>(`/api/v1/exports/${latestExport.value.id}/download-ticket`, { method: 'POST' })
  globalThis.location.assign(ticket.download_url)
}
async function loadWork() {
  const [taskResult, handoverResult] = await Promise.all([api<{ items: Task[] }>(`/api/v1/tasks?task_status=${taskStatus.value}`), api<{ items: Handover[] }>('/api/v1/handovers')])
  tasks.value = taskResult.items; handovers.value = handoverResult.items; taskMode.value = 'list'; selectedHandover.value = null
}
async function startTask() {
  people.value = (await api<{ items: Person[] }>('/api/v1/people?status=active')).items
  const tomorrow = new Date(Date.now() + 86400000); taskForm.value = { title: '', description: '', due_at: tomorrow.toISOString().slice(0, 16), priority: 'normal', person_id: '' }; taskMode.value = 'create'
}
async function saveTask() {
  saving.value = true
  try { await api('/api/v1/tasks', { method: 'POST', body: JSON.stringify({ ...taskForm.value, person_id: taskForm.value.person_id || null, due_at: new Date(taskForm.value.due_at).toISOString() }) }); notice.value = 'La tache a ete creee.'; await loadWork() }
  catch (error) { notice.value = error instanceof Error ? error.message : 'Creation impossible.' }
  finally { saving.value = false }
}
async function completeTask(task: Task) {
  await api(`/api/v1/tasks/${task.id}/complete`, { method: 'POST', headers: { 'If-Match': `"${task.row_version}"` } }); notice.value = 'La tache est terminee.'; await loadWork()
}
async function createHandover() {
  const start = new Date(); const end = new Date(start.getTime() + 12 * 3600000)
  const created = await api<{ id: string }>('/api/v1/handovers', { method: 'POST', body: JSON.stringify({ period_start: start.toISOString(), period_end: end.toISOString() }) }); notice.value = 'La releve a ete preparee automatiquement.'; await openHandover(created.id)
}
async function openHandover(id: string) { selectedHandover.value = await api<Handover>(`/api/v1/handovers/${id}`) }
async function transitionHandover(action: 'open' | 'close') {
  if (!selectedHandover.value) return
  await api(`/api/v1/handovers/${selectedHandover.value.id}/${action}`, { method: 'POST', headers: { 'If-Match': `"${selectedHandover.value.row_version}"` } }); notice.value = action === 'open' ? 'La releve est ouverte.' : 'La releve est cloturee.'; await openHandover(selectedHandover.value.id)
}
async function loadTransmissions() {
  transmissions.value = (await api<{ items: Transmission[] }>(`/api/v1/transmissions?transmission_status=${transmissionStatus.value}`)).items
  transmissionMode.value = 'list'; selectedTransmission.value = null
}
async function filterTransmissions(value: string) {
  transmissionStatus.value = value as 'all' | 'published' | 'draft'
  await loadTransmissions()
}
async function startTransmission() {
  const [personResult, references] = await Promise.all([api<{ items: Person[] }>('/api/v1/people?status=active'), api<{ categories: Reference[]; importance_levels: Reference[] }>('/api/v1/transmission-references')])
  people.value = personResult.items; transmissionReferences.value = references
  transmissionForm.value = { person_id: people.value[0]?.id ?? '', category_id: references.categories[0]?.id ?? '', importance_level_id: references.importance_levels[0]?.id ?? '', content: '' }
  transmissionMode.value = 'create'
}
async function saveTransmission(publishNow: boolean) {
  saving.value = true
  try {
    const created = await api<{ id: string; row_version: number }>('/api/v1/transmissions', { method: 'POST', body: JSON.stringify(transmissionForm.value) })
    if (publishNow) await api(`/api/v1/transmissions/${created.id}/publish`, { method: 'POST', headers: { 'If-Match': `"${created.row_version}"` } })
    notice.value = publishNow ? 'La transmission a ete publiee.' : 'Le brouillon a ete enregistre.'; await loadTransmissions()
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Enregistrement impossible.' }
  finally { saving.value = false }
}
async function openTransmission(item: Transmission) {
  try {
    selectedTransmission.value = await api<Transmission>(`/api/v1/transmissions/${item.id}`)
    attachments.value = (await api<{ items: Attachment[] }>(`/api/v1/transmissions/${item.id}/attachments`)).items
    transmissionMode.value = 'detail'
  }
  catch (error) { notice.value = error instanceof Error ? error.message : 'Transmission inaccessible.' }
}
async function uploadAttachment(event: Event) {
  if (!selectedTransmission.value) return
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const form = new FormData(); form.append('file', file)
  saving.value = true
  try {
    await api(`/api/v1/transmissions/${selectedTransmission.value.id}/attachments`, { method: 'POST', body: form })
    attachments.value = (await api<{ items: Attachment[] }>(`/api/v1/transmissions/${selectedTransmission.value.id}/attachments`)).items
    notice.value = 'Le fichier a ete analyse et ajoute.'; input.value = ''
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Fichier refuse.' }
  finally { saving.value = false }
}
async function deleteAttachment(item: Attachment) {
  if (!selectedTransmission.value) return
  await api(`/api/v1/transmissions/${selectedTransmission.value.id}/attachments/${item.id}`, { method: 'DELETE' })
  attachments.value = attachments.value.filter((attachment) => attachment.id !== item.id)
  notice.value = 'La piece jointe a ete supprimee du brouillon.'
}
function downloadAttachment(item: Attachment) {
  if (selectedTransmission.value) globalThis.location.assign(`/api/v1/transmissions/${selectedTransmission.value.id}/attachments/${item.id}/content`)
}
async function publishTransmission() {
  if (!selectedTransmission.value) return
  await api(`/api/v1/transmissions/${selectedTransmission.value.id}/publish`, { method: 'POST', headers: { 'If-Match': `"${selectedTransmission.value.row_version}"` } })
  notice.value = 'La transmission a ete publiee.'; await loadTransmissions()
}
async function acknowledgeTransmission() {
  if (!selectedTransmission.value) return
  await api(`/api/v1/transmissions/${selectedTransmission.value.id}/acknowledgements`, { method: 'POST' })
  selectedTransmission.value.acknowledged = true; notice.value = 'Lecture confirmee.'
}
async function loadPeople() {
  let params = `status=${peopleStatus.value}`
  if (peopleQuery.value.trim().length >= 2) params += `&query=${encodeURIComponent(peopleQuery.value.trim())}`
  people.value = (await api<{ items: Person[] }>(`/api/v1/people?${params}`)).items
  personMode.value = 'list'; selectedPerson.value = null
}
async function loadPlanPeople() {
  peopleStatus.value = 'active'; peopleQuery.value = ''
  people.value = (await api<{ items: Person[] }>('/api/v1/people?status=active')).items
}
async function openPersonPlan(person: Person) {
  activeView.value = 'people'
  await openPerson(person)
}
async function openPerson(person: Person) {
  try {
    selectedPerson.value = await api<Person>(`/api/v1/people/${person.id}`); personMode.value = 'detail'
    if (session.value?.permissions.includes('personalized_plan.read')) await loadPersonalizedPlan()
  }
  catch (error) { notice.value = error instanceof Error ? error.message : 'Fiche inaccessible.' }
}
async function loadPersonalizedPlan() {
  if (!selectedPerson.value) return
  const result = await api<{ item: PersonalizedPlan | null; versions?: { version_number: number; created_at: string; author_name: string }[]; linked_events?: { id: string; label: string; starts_at: string; ends_at: string; status: string }[] }>(`/api/v1/people/${selectedPerson.value.id}/personalized-plan`)
  personalizedPlan.value = result.item; planVersions.value = result.versions ?? []; planEvents.value = result.linked_events ?? []
  planGoals.value = (await api<{ items: PersonalizedGoal[] }>(`/api/v1/people/${selectedPerson.value.id}/personalized-goals`)).items
  const content = result.item?.content
  planForm.value = content ? { ...content, goals: content.goals.join('\n'), actions: content.actions.join('\n'), review_due_at: result.item?.review_due_at ?? '' } : { person_expectations: '', strengths: '', assessed_needs: '', goals: '', actions: '', participation_method: '', consent_status: 'obtained', consent_details: '', representative_name: '', review_due_at: '' }
}
async function createGoal() {
  if (!selectedPerson.value) return
  await api(`/api/v1/people/${selectedPerson.value.id}/personalized-goals`, { method: 'POST', body: JSON.stringify({ ...goalForm.value, target_date: goalForm.value.target_date || null }) })
  goalForm.value = { title: '', success_criteria: '', person_feedback: '', status: 'planned', progress: 0, target_date: '' }
  notice.value = 'L objectif a ete ajoute au projet.'; await loadPersonalizedPlan()
}
async function saveGoal(goal: PersonalizedGoal) {
  if (!selectedPerson.value) return
  await api(`/api/v1/people/${selectedPerson.value.id}/personalized-goals/${goal.id}`, { method: 'PUT', headers: { 'If-Match': `"${goal.row_version}"` }, body: JSON.stringify(goal) })
  notice.value = 'L avancement de l objectif a ete trace.'; await loadPersonalizedPlan()
}
function startEventReview(entry: ScheduleEntry) {
  reviewEntry.value = entry; reviewForm.value = { summary: '', next_steps: '', attendee_ids: [...entry.person_ids] }
}
async function saveEventReview() {
  if (!reviewEntry.value) return
  await api(`/api/v1/schedule/${reviewEntry.value.id}/review`, { method: 'POST', body: JSON.stringify(reviewForm.value) })
  notice.value = 'Le bilan chiffre de l evenement a ete enregistre.'; reviewEntry.value = null
}
async function savePersonalizedPlan(publish: boolean) {
  if (!selectedPerson.value) return
  const content = { ...planForm.value, goals: planForm.value.goals.split('\n').map((value) => value.trim()).filter(Boolean), actions: planForm.value.actions.split('\n').map((value) => value.trim()).filter(Boolean) }
  const { review_due_at, ...protectedContent } = content
  const body = JSON.stringify({ content: protectedContent, review_due_at: review_due_at || null, publish })
  if (personalizedPlan.value) await api(`/api/v1/people/${selectedPerson.value.id}/personalized-plan/${personalizedPlan.value.id}`, { method: 'PUT', headers: { 'If-Match': `"${personalizedPlan.value.row_version}"` }, body })
  else await api(`/api/v1/people/${selectedPerson.value.id}/personalized-plan`, { method: 'POST', body })
  notice.value = publish ? 'Le projet personnalise a ete publie.' : 'Le brouillon chiffre a ete enregistre.'
  await loadPersonalizedPlan()
}
function startCreate() { personForm.value = { family_name: '', given_name: '', preferred_name: '', birth_date: '' }; personMode.value = 'create' }
function startEdit() {
  if (!selectedPerson.value) return
  personForm.value = { family_name: selectedPerson.value.family_name, given_name: selectedPerson.value.given_name, preferred_name: selectedPerson.value.preferred_name ?? '', birth_date: selectedPerson.value.birth_date ?? '' }; personMode.value = 'edit'
}
async function savePerson() {
  if (!currentContext.value) return
  saving.value = true; notice.value = ''
  const body = { ...personForm.value, preferred_name: personForm.value.preferred_name || null, birth_date: personForm.value.birth_date || null }
  try {
    if (personMode.value === 'create') {
      await api('/api/v1/people', { method: 'POST', body: JSON.stringify({ ...body, unit_id: currentContext.value.id }) })
      notice.value = 'La personne a ete ajoutee a votre unite.'; await loadPeople()
    } else if (selectedPerson.value) {
      selectedPerson.value = await api<Person>(`/api/v1/people/${selectedPerson.value.id}`, { method: 'PATCH', headers: { 'If-Match': `"${selectedPerson.value.row_version}"` }, body: JSON.stringify(body) })
      personMode.value = 'detail'; notice.value = 'La fiche a ete mise a jour.'
    }
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Enregistrement impossible.' }
  finally { saving.value = false }
}
async function archivePerson() {
  if (!selectedPerson.value || archiveReason.value.trim().length < 5) return
  saving.value = true
  try {
    await api(`/api/v1/people/${selectedPerson.value.id}/archive`, { method: 'POST', headers: { 'If-Match': `"${selectedPerson.value.row_version}"` }, body: JSON.stringify({ reason: archiveReason.value.trim() }) })
    archiveReason.value = ''; notice.value = 'La fiche a ete archivee.'; await loadPeople()
  } catch (error) { notice.value = error instanceof Error ? error.message : 'Archivage impossible.' }
  finally { saving.value = false }
}
async function createUnit() {
  const serviceId = structure.value?.items[0]?.service_id
  if (!serviceId || newUnitName.value.trim().length < 2) return
  saving.value = true
  try { await api(`/api/v1/services/${serviceId}/units`, { method: 'POST', body: JSON.stringify({ name: newUnitName.value.trim() }) }); newUnitName.value = ''; notice.value = 'L’unité a été créée et journalisée.'; structure.value = await api('/api/v1/structure') }
  catch (error) { notice.value = error instanceof Error ? error.message : 'Création impossible.' }
  finally { saving.value = false }
}
async function logout() {
  const result = await api<{ logout_url: string }>('/api/v1/auth/logout', { method: 'POST' })
  session.value = null
  globalThis.location.assign(result.logout_url)
}
onMounted(async () => {
  loading.value = true
  if (await loadActivation()) {
    loading.value = false
    return
  }
  await loadSession()
  if (session.value?.permissions.includes('notification.read')) await loadNotifications()
})
</script>

<template>
  <div
    v-if="loading"
    class="loading-screen"
    role="status"
  >
    <Activity
      :size="24"
      class="spin"
    /><span>{{ t('loading') }}</span>
  </div>
  <main
    v-else-if="activationToken || activationComplete"
    id="main-content"
    class="login-shell"
  >
    <section class="login-panel" aria-labelledby="activation-title">
      <div class="brand-mark"><ShieldCheck :size="26" /></div>
      <p class="product-label">Transmissions</p>
      <template v-if="activationComplete">
        <h1 id="activation-title">Compte administrateur activé</h1>
        <p class="login-intro">Votre mot de passe est enregistré dans Keycloak. Le lien utilisé est désormais révoqué.</p>
        <a class="primary-button login-button" href="/auth/login">Se connecter</a>
      </template>
      <template v-else>
        <h1 id="activation-title">Activer le compte administrateur</h1>
        <p class="login-intro">{{ activationDetails?.display_name }} · {{ activationDetails?.username }}</p>
        <p v-if="notice" class="form-error" role="alert">{{ notice }}</p>
        <form v-if="activationDetails" class="activation-form" @submit.prevent="completeActivation">
          <label>Nouveau mot de passe<input v-model="activationPassword" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label>
          <label>Confirmer le mot de passe<input v-model="activationConfirmation" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label>
          <button class="primary-button" type="submit" :disabled="saving || activationPassword.length < 12 || activationPassword !== activationConfirmation">
            <ShieldCheck :size="18" />Activer mon compte
          </button>
        </form>
      </template>
    </section>
    <aside class="login-context" aria-label="Activation locale">
      <div><span class="status-dot" />Activation locale à usage unique</div>
      <h2>Votre mot de passe ne quitte pas cette installation.</h2>
      <p>Le lien expire automatiquement et ne peut être utilisé qu’une seule fois.</p>
    </aside>
  </main>
  <main
    v-else-if="!session"
    id="main-content"
    class="login-shell"
  >
    <section
      class="login-panel"
      aria-labelledby="login-title"
    >
      <div class="brand-mark">
        <ClipboardCheck :size="26" />
      </div><p class="product-label">
        Transmissions
      </p>
      <h1 id="login-title">
        {{ t('welcome') }}
      </h1><p class="login-intro">
        {{ t('loginIntro') }}
      </p>
      <a
        class="primary-button login-button"
        href="/auth/login"
      ><ShieldCheck :size="18" />{{ t('login') }}</a>
      <label class="language-select login-language">
        <Languages :size="17" /><span>{{ t('language') }}</span>
        <select
          :value="locale"
          @change="updateLocale"
        >
          <option value="fr">{{ t('french') }}</option>
          <option value="en">{{ t('english') }}</option>
        </select>
      </label>
    </section>
    <aside
      class="login-context"
      :aria-label="t('workContext')"
    >
      <div><span class="status-dot" />{{ t('secureEnvironment') }}</div><h2>{{ t('loginPromise') }}</h2><p>{{ t('loginScope') }}</p>
    </aside>
  </main>

  <div
    v-else
    class="app-shell"
  >
    <aside
      class="sidebar"
      :class="{ open: mobileNavOpen }"
    >
      <div class="sidebar-brand">
        <ClipboardCheck :size="22" /><span>Transmissions</span>
      </div>
      <nav :aria-label="t('navigation')">
        <button
          v-for="item in navigation"
          :key="item.id"
          class="nav-item"
          :class="{ active: activeView === item.id }"
          :aria-current="activeView === item.id ? 'page' : undefined"
          @click="selectView(item.id)"
        >
          <component
            :is="item.icon"
            :size="18"
          />{{ item.label }}<span
            v-if="item.id === 'notifications' && unreadNotifications"
            class="nav-count"
          >{{ unreadNotifications }}</span>
        </button>
      </nav>
      <div class="sidebar-footer">
        <div class="avatar">
          {{ initials }}
        </div><div class="identity">
          <strong>{{ session.user.display_name }}</strong><span>{{ session.roles[0]?.label }}</span>
        </div><button
          class="icon-button"
          :title="t('logout')"
          @click="logout"
        >
          <LogOut :size="18" />
        </button>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <button
          class="icon-button menu-button"
          :title="t('openMenu')"
          @click="mobileNavOpen = !mobileNavOpen"
        >
          <X
            v-if="mobileNavOpen"
            :size="20"
          /><Menu
            v-else
            :size="20"
          />
        </button><div
          v-if="currentContext"
          class="context-switcher"
        >
          <span><small>{{ t('workContext') }}</small>{{ currentContext.establishment_name }} · {{ currentContext.name }}</span>
        </div><span
          v-else
          class="admin-context"
        >{{ t('organizationAdmin') }}</span><div class="topbar-status">
          <span class="status-dot" />{{ t('activeSession') }}
        </div>
      </header>
      <main
        id="main-content"
        class="content"
        tabindex="-1"
      >
        <p
          v-if="notice"
          class="notice"
          role="status"
        >
          {{ notice }}
        </p>
        <section
          v-if="activeView === 'dashboard'"
          aria-labelledby="dashboard-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                {{ t('workspace') }}
              </p><h1 id="dashboard-title">
                {{ t('hello') }} {{ session.user.display_name.split(' ')[0] }}
              </h1>
            </div><span class="role-chip">{{ session.roles[0]?.label }}</span>
          </div>
          <template v-if="isAdmin">
            <div class="metric-grid">
              <article><Users :size="20" /><strong>2</strong><span>comptes actifs</span></article><article><Building2 :size="20" /><strong>1</strong><span>unité opérationnelle</span></article><article><ShieldCheck :size="20" /><strong>2</strong><span>rôles attribués</span></article>
            </div><div class="section-band">
              <div><h2>Administration prête</h2><p>La structure, les comptes et les habilitations sont disponibles dans le menu.</p></div><button
                class="secondary-button"
                @click="selectView('users')"
              >
                Voir l’équipe
              </button>
            </div>
          </template>
          <template v-else>
            <div class="empty-workday">
              <ClipboardCheck :size="28" /><div><h2>Votre espace est prêt</h2><p>Votre rattachement à l’Unité A est actif. Les personnes et transmissions sont disponibles dans le menu.</p></div>
            </div><div class="upcoming-grid">
              <div><span>Prochainement</span><h3>Personnes accompagnées</h3><p>Recherche limitée à votre périmètre.</p></div><div><span>Prochainement</span><h3>Transmissions</h3><p>Rédaction, publication et accusés de lecture.</p></div><div><span>Prochainement</span><h3>Tâches et relève</h3><p>Priorités de votre prise de poste.</p></div>
            </div>
          </template>
        </section>
        <section
          v-else-if="activeView === 'personalized-plans'"
          aria-labelledby="plans-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Accompagnement individualisé
              </p><h1 id="plans-title">
                Projets personnalisés
              </h1>
            </div><span class="role-chip">{{ people.length }} personne(s)</span>
          </div>
          <div class="section-band">
            <div><h2>Projets d’accompagnement</h2><p>Sélectionnez une personne pour consulter, rédiger ou réévaluer son projet.</p></div>
          </div>
          <div class="people-list">
            <button
              v-for="person in people"
              :key="person.id"
              class="person-row"
              @click="openPersonPlan(person)"
            >
              <span class="person-avatar">{{ person.given_name[0] }}{{ person.family_name[0] }}</span><span><strong>{{ person.preferred_name || person.given_name }} {{ person.family_name }}</strong><small>{{ person.internal_reference }} · {{ person.unit_name }}</small></span><span class="active-status">Ouvrir le projet</span>
            </button><p
              v-if="!people.length"
              class="empty-row"
            >
              Aucune personne active dans votre périmètre.
            </p>
          </div>
        </section>
        <section
          v-else-if="activeView === 'people'"
          aria-labelledby="people-title"
        >
          <div class="page-heading people-heading">
            <div>
              <p class="eyebrow">
                Suivi quotidien
              </p><h1 id="people-title">
                Personnes accompagnees
              </h1>
            </div><button
              v-if="personMode === 'list' && session.permissions.includes('person.create')"
              class="primary-button"
              @click="startCreate"
            >
              <Plus :size="17" />Ajouter
            </button>
          </div>
          <template v-if="personMode === 'list'">
            <form
              class="people-toolbar"
              @submit.prevent="loadPeople"
            >
              <label class="search-field"><Search :size="17" /><input
                v-model="peopleQuery"
                aria-label="Rechercher une personne"
                minlength="2"
                placeholder="Nom, prenom ou reference"
              ></label>
              <select
                v-model="peopleStatus"
                aria-label="Etat des fiches"
                @change="loadPeople"
              >
                <option value="active">
                  Actives
                </option><option value="archived">
                  Archivees
                </option>
              </select>
              <button class="secondary-button">
                Rechercher
              </button>
            </form>
            <div class="people-list">
              <button
                v-for="person in people"
                :key="person.id"
                class="person-row"
                @click="openPerson(person)"
              >
                <span class="person-avatar">{{ person.given_name[0] }}{{ person.family_name[0] }}</span><span><strong>{{ person.preferred_name || person.given_name }} {{ person.family_name }}</strong><small>{{ person.internal_reference }} · {{ person.unit_name }}</small></span><span :class="person.status === 'active' ? 'active-status' : 'archived-status'">{{ person.status === 'active' ? 'Active' : 'Archivee' }}</span>
              </button>
              <p
                v-if="!people.length"
                class="empty-row"
              >
                Aucune fiche ne correspond a cette recherche.
              </p>
            </div>
          </template>
          <form
            v-else-if="personMode === 'create' || personMode === 'edit'"
            class="person-form"
            @submit.prevent="savePerson"
          >
            <button
              type="button"
              class="back-button"
              @click="personMode = selectedPerson ? 'detail' : 'list'"
            >
              <ArrowLeft :size="17" />Retour
            </button>
            <div class="form-grid">
              <label>Nom<input
                v-model="personForm.family_name"
                required
                minlength="2"
                maxlength="120"
              ></label><label>Prenom<input
                v-model="personForm.given_name"
                required
                minlength="2"
                maxlength="120"
              ></label><label>Nom d'usage<input
                v-model="personForm.preferred_name"
                maxlength="120"
              ></label><label>Date de naissance<input
                v-model="personForm.birth_date"
                type="date"
              ></label>
            </div>
            <div class="form-actions">
              <button
                type="submit"
                class="primary-button"
                :disabled="saving"
              >
                Enregistrer
              </button>
            </div>
          </form>
          <div
            v-else-if="selectedPerson"
            class="person-detail"
          >
            <button
              class="back-button"
              @click="loadPeople"
            >
              <ArrowLeft :size="17" />Retour a la liste
            </button>
            <header>
              <span class="person-avatar large">{{ selectedPerson.given_name[0] }}{{ selectedPerson.family_name[0] }}</span><div><p>{{ selectedPerson.internal_reference }}</p><h2>{{ selectedPerson.preferred_name || selectedPerson.given_name }} {{ selectedPerson.family_name }}</h2><span class="active-status">Active</span></div><button
                v-if="session.permissions.includes('person.update')"
                class="secondary-button"
                @click="startEdit"
              >
                <Pencil :size="16" />Modifier
              </button>
            </header>
            <dl class="person-fields">
              <div><dt>Identite complete</dt><dd>{{ selectedPerson.given_name }} {{ selectedPerson.family_name }}</dd></div><div><dt>Date de naissance</dt><dd>{{ selectedPerson.birth_date ? new Date(selectedPerson.birth_date).toLocaleDateString('fr-FR') : 'Non renseignee' }}</dd></div><div><dt>Unite</dt><dd>{{ selectedPerson.establishment_name }} · {{ selectedPerson.service_name }} · {{ selectedPerson.unit_name }}</dd></div>
            </dl>
            <section
              v-if="session.permissions.includes('personalized_plan.read')"
              class="plan-panel"
              aria-labelledby="plan-title"
            >
              <div class="plan-heading">
                <div>
                  <h3 id="plan-title">
                    Projet personnalisé d’accompagnement
                  </h3><p>Attentes, objectifs et actions co-construits avec la personne.</p>
                </div><button
                  type="button"
                  class="secondary-button"
                  @click="printPage"
                >
                  <Printer :size="16" />Imprimer
                </button><span :class="personalizedPlan?.status === 'active' ? 'active-status' : 'role-chip'">{{ personalizedPlan?.status === 'active' ? 'Actif' : 'Brouillon' }}</span>
              </div>
              <form
                class="plan-form"
                @submit.prevent="savePersonalizedPlan(false)"
              >
                <div class="plan-grid">
                  <label>Parole et attentes de la personne<textarea
                    v-model="planForm.person_expectations"
                    required
                    maxlength="5000"
                    rows="4"
                  /></label><label>Forces, ressources et capacités<textarea
                    v-model="planForm.strengths"
                    maxlength="5000"
                    rows="4"
                  /></label><label>Besoins évalués<textarea
                    v-model="planForm.assessed_needs"
                    maxlength="5000"
                    rows="4"
                  /></label><label>Objectifs, un par ligne<textarea
                    v-model="planForm.goals"
                    required
                    rows="4"
                  /></label><label>Actions prévues, une par ligne<textarea
                    v-model="planForm.actions"
                    rows="4"
                  /></label><label>Modalités de participation<textarea
                    v-model="planForm.participation_method"
                    required
                    maxlength="2000"
                    rows="4"
                  /></label>
                </div>
                <div class="plan-consent">
                  <label>Consentement<select v-model="planForm.consent_status"><option value="obtained">Recueilli</option><option value="refused">Refusé</option><option value="unable">Impossible à recueillir</option></select></label><label>Précisions et expression de la personne<input
                    v-model="planForm.consent_details"
                    maxlength="2000"
                  ></label><label>Représentant légal ou personne associée<input
                    v-model="planForm.representative_name"
                    maxlength="200"
                  ></label>
                </div><label>Date de réévaluation<input
                  v-model="planForm.review_due_at"
                  type="date"
                ></label>
                <div class="plan-history">
                  <span
                    v-for="version in planVersions"
                    :key="version.version_number"
                  >Version {{ version.version_number }} · {{ version.author_name }} · {{ new Date(version.created_at).toLocaleDateString('fr-FR') }}</span>
                </div>
                <section
                  v-if="planEvents.length"
                  class="plan-events"
                >
                  <h4>Sorties et accompagnements liés</h4><article
                    v-for="event in planEvents"
                    :key="event.id"
                  >
                    <CalendarDays :size="17" /><span><strong>{{ event.label }}</strong><small>{{ new Date(event.starts_at).toLocaleString('fr-FR') }} · {{ event.status === 'active' ? 'Planifié' : 'Annulé' }}</small></span>
                  </article>
                </section>
                <section
                  v-if="personalizedPlan"
                  class="goal-section"
                >
                  <h4>Objectifs et progression</h4><article
                    v-for="goal in planGoals"
                    :key="goal.id"
                    class="goal-row"
                  >
                    <div><strong>{{ goal.title }}</strong><small>{{ goal.success_criteria || 'Critère à préciser' }}</small></div><select v-model="goal.status">
                      <option value="planned">
                        Planifié
                      </option><option value="in_progress">
                        En cours
                      </option><option value="achieved">
                        Atteint
                      </option><option value="adapted">
                        Adapté
                      </option><option value="abandoned">
                        Abandonné
                      </option>
                    </select><label>Progression<input
                      v-model.number="goal.progress"
                      type="range"
                      min="0"
                      max="100"
                    ><span>{{ goal.progress }} %</span></label><input
                      v-model="goal.person_feedback"
                      maxlength="2000"
                      placeholder="Retour de la personne"
                    ><button
                      type="button"
                      class="secondary-button"
                      @click="saveGoal(goal)"
                    >
                      Actualiser
                    </button>
                  </article><form
                    class="goal-create"
                    @submit.prevent="createGoal"
                  >
                    <input
                      v-model="goalForm.title"
                      required
                      minlength="3"
                      maxlength="500"
                      placeholder="Nouvel objectif"
                    ><input
                      v-model="goalForm.success_criteria"
                      maxlength="2000"
                      placeholder="Critère de réussite"
                    ><input
                      v-model="goalForm.target_date"
                      type="date"
                    ><button class="secondary-button">
                      <Plus :size="16" />Ajouter
                    </button>
                  </form>
                </section>
                <div
                  v-if="session.permissions.includes('personalized_plan.manage')"
                  class="form-actions"
                >
                  <button class="secondary-button">
                    Enregistrer le brouillon
                  </button><button
                    type="button"
                    class="primary-button"
                    @click="savePersonalizedPlan(true)"
                  >
                    <CheckCircle2 :size="17" />Publier la version
                  </button>
                </div>
              </form>
            </section>
            <form
              v-if="session.permissions.includes('person.archive')"
              class="archive-form"
              @submit.prevent="archivePerson"
            >
              <div><Archive :size="18" /><span><strong>Archiver cette fiche</strong><small>Elle ne figurera plus dans la liste active.</small></span></div><label>Motif<input
                v-model="archiveReason"
                required
                minlength="5"
                maxlength="500"
                placeholder="Motif de l'archivage"
              ></label><button
                class="danger-button"
                :disabled="saving"
              >
                Archiver
              </button>
            </form>
          </div>
        </section>
        <section
          v-else-if="activeView === 'transmissions'"
          aria-labelledby="transmissions-title"
        >
          <div class="page-heading people-heading">
            <div>
              <p class="eyebrow">
                Informations d'equipe
              </p><h1 id="transmissions-title">
                Transmissions
              </h1>
            </div>
            <button
              v-if="transmissionMode === 'list'"
              class="primary-button"
              @click="startTransmission"
            >
              <Plus :size="17" />Nouvelle transmission
            </button>
          </div>
          <template v-if="transmissionMode === 'list'">
            <div class="transmission-filters">
              <button
                v-for="filter in [{ id: 'all', label: 'Toutes' }, { id: 'published', label: 'Publiees' }, { id: 'draft', label: 'Mes brouillons' }]"
                :key="filter.id"
                :class="{ active: transmissionStatus === filter.id }"
                @click="filterTransmissions(filter.id)"
              >
                {{ filter.label }}
              </button>
            </div>
            <div class="transmission-list">
              <button
                v-for="item in transmissions"
                :key="item.id"
                class="transmission-row"
                @click="openTransmission(item)"
              >
                <span
                  class="category-bar"
                  :style="{ background: item.color }"
                /><span class="transmission-main"><span><strong>{{ item.preferred_name || item.given_name }} {{ item.family_name }}</strong><small>{{ item.category_label }} · {{ item.importance_label }}</small></span><p>{{ item.content }}</p><small>{{ item.author_name }} · {{ new Date(item.published_at || item.created_at).toLocaleString('fr-FR') }}</small></span><span :class="item.status === 'draft' ? 'draft-status' : 'active-status'">{{ item.status === 'draft' ? 'Brouillon' : 'Publiee' }}</span>
              </button><p
                v-if="!transmissions.length"
                class="empty-row"
              >
                Aucune transmission dans ce filtre.
              </p>
            </div>
          </template>
          <form
            v-else-if="transmissionMode === 'create'"
            class="transmission-editor"
            @submit.prevent="saveTransmission(false)"
          >
            <button
              type="button"
              class="back-button"
              @click="transmissionMode = 'list'"
            >
              <ArrowLeft :size="17" />Retour
            </button>
            <div class="form-grid">
              <label>Personne<select
                v-model="transmissionForm.person_id"
                required
              ><option
                v-for="person in people"
                :key="person.id"
                :value="person.id"
              >{{ person.given_name }} {{ person.family_name }}</option></select></label><label>Categorie<select
                v-model="transmissionForm.category_id"
                required
              ><option
                v-for="category in transmissionReferences.categories"
                :key="category.id"
                :value="category.id"
              >{{ category.label }}</option></select></label><label>Importance<select
                v-model="transmissionForm.importance_level_id"
                required
              ><option
                v-for="level in transmissionReferences.importance_levels"
                :key="level.id"
                :value="level.id"
              >{{ level.label }}</option></select></label>
            </div>
            <label class="content-field">Contenu<textarea
              v-model="transmissionForm.content"
              required
              minlength="2"
              maxlength="10000"
              rows="9"
              placeholder="Saisir les faits utiles, precis et observes"
            /><small>{{ transmissionForm.content.length }} / 10 000</small></label>
            <div class="editor-actions">
              <button
                class="secondary-button"
                :disabled="saving"
              >
                Enregistrer le brouillon
              </button><button
                type="button"
                class="primary-button"
                :disabled="saving || transmissionForm.content.length < 2"
                @click="saveTransmission(true)"
              >
                <Send :size="16" />Publier
              </button>
            </div>
          </form>
          <article
            v-else-if="selectedTransmission"
            class="transmission-detail"
          >
            <button
              class="back-button"
              @click="loadTransmissions"
            >
              <ArrowLeft :size="17" />Retour aux transmissions
            </button>
            <header>
              <div><span :class="selectedTransmission.status === 'draft' ? 'draft-status' : 'active-status'">{{ selectedTransmission.status === 'draft' ? 'Brouillon' : 'Publiee' }}</span><h2>{{ selectedTransmission.preferred_name || selectedTransmission.given_name }} {{ selectedTransmission.family_name }}</h2><p>{{ selectedTransmission.category_label }} · {{ selectedTransmission.importance_label }} · version {{ selectedTransmission.version_number }}</p></div><button
                v-if="selectedTransmission.status === 'draft'"
                class="primary-button"
                @click="publishTransmission"
              >
                <Send :size="16" />Publier
              </button>
            </header>
            <div class="transmission-content">
              {{ selectedTransmission.content }}
            </div><footer><span>{{ selectedTransmission.author_name }}</span><time>{{ new Date(selectedTransmission.published_at || selectedTransmission.created_at).toLocaleString('fr-FR') }}</time></footer>
            <section
              class="attachment-panel"
              aria-labelledby="attachment-title"
            >
              <div class="band-heading">
                <div>
                  <h3 id="attachment-title">
                    <Paperclip :size="17" />Pieces jointes
                  </h3><p>PDF, JPEG ou PNG · 5 Mo maximum · analyse antivirus obligatoire</p>
                </div><label
                  v-if="selectedTransmission.status === 'draft' && selectedTransmission.author_id === session.user.id"
                  class="secondary-button attachment-picker"
                ><Plus :size="16" />Ajouter<input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  :disabled="saving"
                  @change="uploadAttachment"
                ></label>
              </div>
              <div class="attachment-list">
                <article
                  v-for="item in attachments"
                  :key="item.id"
                >
                  <Paperclip :size="18" /><div><strong>{{ item.original_name }}</strong><small>{{ (item.byte_size / 1024).toFixed(1) }} Ko · Analyse saine</small></div><button
                    class="icon-complete"
                    title="Telecharger"
                    @click="downloadAttachment(item)"
                  >
                    <Download :size="17" />
                  </button><button
                    v-if="selectedTransmission.status === 'draft' && selectedTransmission.author_id === session.user.id"
                    class="icon-delete"
                    title="Supprimer"
                    @click="deleteAttachment(item)"
                  >
                    <Trash2 :size="17" />
                  </button>
                </article><p
                  v-if="!attachments.length"
                  class="empty-row"
                >
                  Aucune piece jointe.
                </p>
              </div>
            </section>
            <button
              v-if="selectedTransmission.status === 'published' && !selectedTransmission.acknowledged"
              class="secondary-button acknowledge-button"
              @click="acknowledgeTransmission"
            >
              <CheckCircle2 :size="17" />Confirmer ma lecture
            </button><p
              v-else-if="selectedTransmission.acknowledged"
              class="acknowledged"
            >
              <CheckCircle2 :size="17" />{{ selectedTransmission.author_id === session.user.id ? 'Transmission publiee par vous' : 'Lecture confirmee pour cette version' }}
            </p>
          </article>
        </section>
        <section
          v-else-if="activeView === 'work'"
          aria-labelledby="work-title"
        >
          <div class="page-heading people-heading">
            <div>
              <p class="eyebrow">
                Prise de poste
              </p><h1 id="work-title">
                Taches et releves
              </h1>
            </div><div class="heading-actions">
              <button
                v-if="session.permissions.includes('handover.create')"
                class="secondary-button"
                @click="createHandover"
              >
                <ClipboardCheck :size="17" />Preparer une releve
              </button><button
                class="primary-button"
                @click="startTask"
              >
                <Plus :size="17" />Nouvelle tache
              </button>
            </div>
          </div>
          <template v-if="!selectedHandover">
            <section class="work-band">
              <div class="band-heading">
                <h2>Taches</h2><select
                  v-model="taskStatus"
                  aria-label="Filtrer les taches"
                  @change="loadWork"
                >
                  <option value="active">
                    A faire
                  </option><option value="done">
                    Terminees
                  </option><option value="cancelled">
                    Annulees
                  </option>
                </select>
              </div>
              <form
                v-if="taskMode === 'create'"
                class="task-editor"
                @submit.prevent="saveTask"
              >
                <div class="form-grid">
                  <label>Titre<input
                    v-model="taskForm.title"
                    required
                    minlength="2"
                    maxlength="200"
                  ></label><label>Echeance<input
                    v-model="taskForm.due_at"
                    type="datetime-local"
                    required
                  ></label><label>Priorite<select v-model="taskForm.priority"><option value="normal">Normale</option><option value="important">Importante</option><option value="urgent">Urgente</option></select></label><label>Personne<select v-model="taskForm.person_id"><option value="">Aucune</option><option
                    v-for="person in people"
                    :key="person.id"
                    :value="person.id"
                  >{{ person.given_name }} {{ person.family_name }}</option></select></label>
                </div><label class="content-field">Description<textarea
                  v-model="taskForm.description"
                  rows="3"
                  maxlength="5000"
                /></label><div class="editor-actions">
                  <button
                    type="button"
                    class="secondary-button"
                    @click="taskMode = 'list'"
                  >
                    Annuler
                  </button><button
                    class="primary-button"
                    :disabled="saving"
                  >
                    Creer
                  </button>
                </div>
              </form>
              <div
                v-else
                class="task-list"
              >
                <article
                  v-for="task in tasks"
                  :key="task.id"
                  :class="{ overdue: task.overdue }"
                >
                  <span :class="`priority priority-${task.priority}`" /><div><strong>{{ task.title }}</strong><p>{{ task.given_name ? `${task.given_name} ${task.family_name} · ` : '' }}{{ task.assignee_name || 'Unite' }}</p></div><time>{{ new Date(task.due_at).toLocaleString('fr-FR') }}</time><button
                    v-if="task.status !== 'done' && task.status !== 'cancelled'"
                    class="icon-complete"
                    title="Terminer la tache"
                    @click="completeTask(task)"
                  >
                    <CheckCircle2 :size="20" />
                  </button>
                </article><p
                  v-if="!tasks.length"
                  class="empty-row"
                >
                  Aucune tache dans ce filtre.
                </p>
              </div>
            </section>
            <section class="work-band">
              <div class="band-heading">
                <h2>Releves recentes</h2>
              </div><div class="handover-list">
                <button
                  v-for="handover in handovers"
                  :key="handover.id"
                  @click="openHandover(handover.id)"
                >
                  <ClipboardCheck :size="19" /><span><strong>{{ handover.unit_name }}</strong><small>{{ new Date(handover.period_start).toLocaleString('fr-FR') }} · {{ handover.creator_name }}</small></span><span :class="handover.status === 'open' ? 'active-status' : 'draft-status'">{{ handover.status }}</span>
                </button><p
                  v-if="!handovers.length"
                  class="empty-row"
                >
                  Aucune releve preparee.
                </p>
              </div>
            </section>
          </template>
          <article
            v-else
            class="handover-detail"
          >
            <button
              class="back-button"
              @click="loadWork"
            >
              <ArrowLeft :size="17" />Retour
            </button><header>
              <div><span :class="selectedHandover.status === 'open' ? 'active-status' : 'draft-status'">{{ selectedHandover.status }}</span><h2>Releve · {{ selectedHandover.unit_name }}</h2><p>{{ new Date(selectedHandover.period_start).toLocaleString('fr-FR') }} au {{ new Date(selectedHandover.period_end).toLocaleString('fr-FR') }}</p></div><button
                v-if="selectedHandover.status === 'draft'"
                class="primary-button"
                @click="transitionHandover('open')"
              >
                Ouvrir
              </button><button
                v-else-if="selectedHandover.status === 'open' && session.permissions.includes('handover.close')"
                class="primary-button"
                @click="transitionHandover('close')"
              >
                Cloturer
              </button>
            </header><section>
              <h3>Taches prioritaires</h3><div class="handover-items">
                <article
                  v-for="task in selectedHandover.tasks"
                  :key="task.id"
                >
                  <ListChecks :size="18" /><div><strong>{{ task.title }}</strong><small>{{ new Date(task.due_at).toLocaleString('fr-FR') }} · {{ task.priority }}</small></div>
                </article><p
                  v-if="!selectedHandover.tasks?.length"
                  class="empty-row"
                >
                  Aucune tache proposee.
                </p>
              </div>
            </section><section>
              <h3>Transmissions importantes</h3><div class="handover-items">
                <article
                  v-for="item in selectedHandover.transmissions"
                  :key="item.id"
                >
                  <Send :size="18" /><div><strong>{{ item.given_name }} {{ item.family_name }} · {{ item.category_label }}</strong><small>{{ item.content }}</small></div>
                </article><p
                  v-if="!selectedHandover.transmissions?.length"
                  class="empty-row"
                >
                  Aucune transmission proposee.
                </p>
              </div>
            </section>
          </article>
        </section>
        <section
          v-else-if="activeView === 'pilotage'"
          aria-labelledby="pilotage-title"
        >
          <div class="page-heading pilotage-heading">
            <div>
              <p class="eyebrow">
                Vue agregee de votre perimetre
              </p><h1 id="pilotage-title">
                Indicateurs de pilotage
              </h1>
            </div><label>Periode<select
              v-model.number="pilotageDays"
              @change="loadPilotage"
            ><option :value="7">7 jours</option><option :value="30">30 jours</option><option :value="90">90 jours</option></select></label>
          </div>
          <template v-if="pilotage">
            <div class="pilotage-metrics">
              <article><span>Personnes actives</span><strong>{{ pilotage.summary.active_people }}</strong><small>dans les unites autorisees</small></article><article><span>Transmissions publiees</span><strong>{{ pilotage.summary.transmissions }}</strong><small>dont {{ pilotage.summary.urgent_transmissions }} urgentes</small></article><article><span>Taches terminees</span><strong>{{ pilotage.summary.tasks_completed }}</strong><small>sur {{ pilotage.summary.tasks_created }} creees</small></article><article :class="{ attention: pilotage.summary.tasks_overdue > 0 }">
                <span>Taches en retard</span><strong>{{ pilotage.summary.tasks_overdue }}</strong><small>a traiter actuellement</small>
              </article>
            </div>
            <section class="management-alerts" aria-labelledby="management-alerts-title">
              <div class="band-heading">
                <div><h2 id="management-alerts-title">Alertes metier</h2><p>Points nécessitant une vérification dans votre périmètre</p></div>
              </div><div class="alert-metrics">
                <article :class="{ critical: pilotage.alerts.plans_overdue > 0 }"><Target :size="19" /><span><strong>{{ pilotage.alerts.plans_overdue }}</strong> projet{{ pilotage.alerts.plans_overdue > 1 ? 's' : '' }} en retard de révision</span></article>
                <article :class="{ warning: pilotage.alerts.plans_due_30_days > 0 }"><FileClock :size="19" /><span><strong>{{ pilotage.alerts.plans_due_30_days }}</strong> projet{{ pilotage.alerts.plans_due_30_days > 1 ? 's' : '' }} à réviser sous 30 jours</span></article>
                <article :class="{ critical: pilotage.alerts.goals_overdue > 0 }"><CircleAlert :size="19" /><span><strong>{{ pilotage.alerts.goals_overdue }}</strong> objectif{{ pilotage.alerts.goals_overdue > 1 ? 's' : '' }} arrivé{{ pilotage.alerts.goals_overdue > 1 ? 's' : '' }} à échéance</span></article>
                <article :class="{ warning: pilotage.alerts.goals_without_recent_follow_up > 0 }"><Activity :size="19" /><span><strong>{{ pilotage.alerts.goals_without_recent_follow_up }}</strong> objectif{{ pilotage.alerts.goals_without_recent_follow_up > 1 ? 's' : '' }} sans suivi depuis 30 jours</span></article>
                <article :class="{ warning: pilotage.alerts.events_without_review > 0 }"><ClipboardCheck :size="19" /><span><strong>{{ pilotage.alerts.events_without_review }}</strong> accompagnement{{ pilotage.alerts.events_without_review > 1 ? 's' : '' }} sans bilan</span></article>
                <article :class="{ warning: pilotage.alerts.cancelled_events > 0 }"><CalendarDays :size="19" /><span><strong>{{ pilotage.alerts.cancelled_events }}</strong> événement{{ pilotage.alerts.cancelled_events > 1 ? 's' : '' }} annulé{{ pilotage.alerts.cancelled_events > 1 ? 's' : '' }} sur la période</span></article>
              </div>
            </section>
            <section class="workload-panel" aria-labelledby="workload-title">
              <div class="band-heading"><div><h2 id="workload-title">Charge prévisionnelle</h2><p>Sept prochains jours · heures planifiées</p></div></div><div class="workload-table" role="table" aria-label="Charge des professionnels">
                <div class="workload-header" role="row"><span role="columnheader">Professionnel</span><span role="columnheader">Présence</span><span role="columnheader">Accompagnements</span><span role="columnheader">Absence</span></div><div
                  v-for="member in pilotage.workload"
                  :key="member.id"
                  class="workload-row"
                  role="row"
                ><strong role="cell">{{ member.display_name }}</strong><span role="cell">{{ member.shift_hours }} h</span><span role="cell">{{ member.event_hours }} h</span><span role="cell">{{ member.absence_hours }} h</span></div><p v-if="!pilotage.workload.length" class="empty-row">Aucun professionnel actif.</p>
              </div>
            </section>
            <div class="pilotage-detail">
              <section aria-labelledby="activity-title">
                <div class="band-heading">
                  <div>
                    <h2 id="activity-title">
                      Activite quotidienne
                    </h2><p>Transmissions publiees et taches terminees</p>
                  </div>
                </div>
                <div class="activity-chart">
                  <div
                    v-for="day in pilotage.daily"
                    :key="day.date"
                    class="activity-row"
                  >
                    <time :datetime="day.date">{{ new Date(`${day.date}T12:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }) }}</time><div class="activity-bars">
                      <span
                        class="transmission-bar"
                        :style="{ width: indicatorWidth(day.transmissions) }"
                      ><b>{{ day.transmissions }}</b></span><span
                        class="task-bar"
                        :style="{ width: indicatorWidth(day.tasks_completed) }"
                      ><b>{{ day.tasks_completed }}</b></span>
                    </div>
                  </div>
                </div><div class="chart-legend">
                  <span><i class="transmission-key" />Transmissions</span><span><i class="task-key" />Taches terminees</span>
                </div>
              </section>
              <aside aria-labelledby="completion-title">
                <span>Taux de realisation</span><strong id="completion-title">{{ pilotage.summary.completion_rate }} %</strong><div
                  class="completion-track"
                  role="progressbar"
                  aria-label="Taux de realisation des taches"
                  :aria-valuenow="pilotage.summary.completion_rate"
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  <span :style="{ width: `${Math.min(100, pilotage.summary.completion_rate)}%` }" />
                </div><p>Rapport entre les taches terminees et creees sur la periode.</p><small>Les indicateurs ne contiennent aucun nom ni contenu metier.</small>
              </aside>
            </div>
          </template>
        </section>
        <section
          v-else-if="activeView === 'schedule'"
          :class="{ 'public-schedule-print': printProfessionalId !== 'all' && printPublicCopy }"
          aria-labelledby="schedule-title"
        >
          <div class="page-heading people-heading">
            <div>
              <p class="eyebrow">
                Organisation de l equipe
              </p><h1 id="schedule-title">
                Planning
              </h1>
            </div>
            <div class="schedule-print-controls">
              <label v-if="calendarMode === 'professionals'">Impression<select v-model="printProfessionalId"><option value="all">Toute l'equipe</option><option
                v-for="member in scheduleMembers"
                :key="member.id"
                :value="member.id"
              >{{ member.display_name }}</option></select></label><label
                v-if="printProfessionalId !== 'all'"
                class="public-copy-toggle"
              ><span>Document usager</span><input v-model="printPublicCopy" type="checkbox"></label><button
                type="button"
                class="secondary-button"
                @click="printPage"
              >
                <Printer :size="17" />Imprimer
              </button>
            </div>
            <button
              v-if="session.permissions.includes('leave.request')"
              type="button"
              class="secondary-button"
              @click="prepareLeave"
            >
              <CalendarDays :size="17" />Demander un congé
            </button>
            <button
              v-if="session.permissions.includes('schedule.manage') || session.permissions.includes('schedule.event.create')"
              class="primary-button"
              @click="prepareScheduleEntry"
            >
              <Plus :size="17" />Ajouter un creneau
            </button>
          </div>
          <div class="calendar-mode-switch" role="group" aria-label="Type de planning">
            <button
              type="button"
              :class="{ active: calendarMode === 'professionals' }"
              :aria-pressed="calendarMode === 'professionals'"
              @click="calendarMode = 'professionals'"
            >
              <Users :size="17" />Professionnels
            </button><button
              type="button"
              :class="{ active: calendarMode === 'people' }"
              :aria-pressed="calendarMode === 'people'"
              @click="calendarMode = 'people'"
            >
              <ContactRound :size="17" />Personnes accompagnees
            </button>
          </div>
          <div class="print-schedule-heading" aria-hidden="true">
            <strong>{{ printScheduleTitle }}</strong><span>{{ currentContext?.establishment_name }} · {{ currentContext?.service_name }} · {{ currentContext?.name }}</span><span>Semaine du {{ scheduleWeek.toLocaleDateString('fr-FR') }}</span>
          </div>
          <form
            v-if="leaveMode"
            class="leave-editor"
            @submit.prevent="requestLeave"
          >
            <label>Type<select v-model="leaveForm.leave_type"><option value="paid_leave">Congé</option><option value="training">Formation</option><option value="sick_leave">Arrêt</option><option value="recovery">Récupération</option><option value="other">Autre absence</option></select></label><label>Début<input
              v-model="leaveForm.starts_at"
              type="datetime-local"
              required
            ></label><label>Fin<input
              v-model="leaveForm.ends_at"
              type="datetime-local"
              required
            ></label><button class="primary-button">
              Envoyer la demande
            </button>
          </form>
          <div class="week-toolbar">
            <button
              class="icon-button"
              title="Semaine precedente"
              @click="changeScheduleWeek(-1)"
            >
              <ArrowLeft :size="18" />
            </button><strong>Semaine du {{ scheduleWeek.toLocaleDateString('fr-FR') }}</strong><button
              class="icon-button next-week"
              title="Semaine suivante"
              @click="changeScheduleWeek(1)"
            >
              <ArrowLeft :size="18" />
            </button>
          </div>
          <form
            v-if="scheduleForm.starts_at"
            class="schedule-editor"
            @submit.prevent="createScheduleEntry"
          >
            <label v-if="scheduleForm.entry_type !== 'event'">Professionnel<select
              v-model="scheduleForm.user_id"
              required
            ><option
              v-for="user in users"
              :key="user.id"
              :value="user.id"
            >{{ user.display_name }}</option></select></label>
            <label>Type<select v-model="scheduleForm.entry_type"><option
              v-if="session.permissions.includes('schedule.manage')"
              value="shift"
            >Présence</option><option
              v-if="session.permissions.includes('schedule.manage')"
              value="absence"
            >Congé / absence</option><option value="event">Événement partagé</option></select></label>
            <label>Debut<input
              v-model="scheduleForm.starts_at"
              type="datetime-local"
              required
            ></label><label>Fin<input
              v-model="scheduleForm.ends_at"
              type="datetime-local"
              required
            ></label>
            <label>Libellé<input
              v-model="scheduleForm.label"
              maxlength="120"
              :required="scheduleForm.entry_type === 'event'"
              placeholder="Réunion, sortie, accompagnement…"
            ></label><label v-if="scheduleForm.entry_type === 'event' && !editingEvent">Répéter<select v-model.number="scheduleForm.recurrence_weeks"><option :value="0">Une seule fois</option><option :value="3">Chaque semaine · 4 fois</option><option :value="7">Chaque semaine · 8 fois</option><option :value="11">Chaque semaine · 12 fois</option></select></label><fieldset
              v-if="scheduleForm.entry_type === 'event' && !editingEvent"
              class="schedule-invites"
            >
              <legend>Professionnels invités</legend><label
                v-for="member in scheduleMembers"
                :key="member.id"
              ><input
                v-model="scheduleForm.participant_ids"
                type="checkbox"
                :value="member.id"
              >{{ member.display_name }}</label>
            </fieldset><fieldset
              v-if="scheduleForm.entry_type === 'event' && !editingEvent"
              class="schedule-invites schedule-people"
            >
              <legend>Personnes accompagnées concernées</legend><label
                v-for="person in people"
                :key="person.id"
              ><input
                v-model="scheduleForm.person_ids"
                type="checkbox"
                :value="person.id"
              >{{ person.preferred_name || person.given_name }} {{ person.family_name }}</label>
              <label class="link-plans"><input
                v-model="scheduleForm.link_personalized_plans"
                type="checkbox"
              >Rattacher aux projets personnalisés existants</label>
            </fieldset><button class="primary-button">
              {{ editingEvent ? 'Enregistrer les modifications' : 'Enregistrer' }}
            </button>
          </form>
          <form
            v-if="reviewEntry"
            class="event-review"
            @submit.prevent="saveEventReview"
          >
            <div>
              <strong>Bilan · {{ reviewEntry.label }}</strong><button
                type="button"
                class="icon-button"
                title="Fermer"
                @click="reviewEntry = null"
              >
                <X :size="16" />
              </button>
            </div><label>Compte rendu<textarea
              v-model="reviewForm.summary"
              required
              minlength="3"
              maxlength="5000"
              rows="3"
            /></label><label>Suites à donner<textarea
              v-model="reviewForm.next_steps"
              maxlength="3000"
              rows="2"
            /></label><fieldset>
              <legend>Présence effective des personnes accompagnées</legend><label
                v-for="(name, index) in reviewEntry.person_names"
                :key="reviewEntry.person_ids[index]"
              ><input
                v-model="reviewForm.attendee_ids"
                type="checkbox"
                :value="reviewEntry.person_ids[index]"
              >{{ name }}</label>
            </fieldset><button class="primary-button">
              Enregistrer le bilan
            </button>
          </form>
          <div
            v-if="calendarMode === 'professionals'"
            class="team-calendar"
            :style="{ '--calendar-columns': `170px repeat(${scheduleDays.length}, minmax(120px, 1fr))` }"
          >
            <div class="calendar-corner">
              Professionnels
            </div><div
              v-for="day in scheduleDays"
              :key="day.toISOString()"
              class="calendar-day"
            >
              <strong>{{ day.toLocaleDateString('fr-FR', { weekday: 'short' }) }}</strong><span>{{ day.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) }}</span>
            </div>
            <template
              v-for="member in scheduleMembers"
              :key="member.id"
            >
              <div :class="['calendar-member', { current: member.id === session.user.id, 'print-excluded': printProfessionalId !== 'all' && printProfessionalId !== member.id }]">
                <span class="person-avatar">{{ member.display_name.split(' ').map((part) => part[0]).join('').slice(0, 2) }}</span><span><strong>{{ member.display_name }}</strong><small>{{ member.id === session.user.id ? 'Mon planning' : 'Même unité' }}</small></span>
              </div><div
                v-for="day in scheduleDays"
                :key="`${member.id}-${day.toISOString()}`"
                :class="['calendar-cell', { 'print-excluded': printProfessionalId !== 'all' && printProfessionalId !== member.id }]"
              >
                <div class="cell-summary">
                  <span>{{ scheduledHours(member.id, day) }}</span><button
                    class="cell-add"
                    title="Créer un événement avec ce professionnel"
                    @click="prepareCalendarEvent(day, member.id)"
                  >
                    <Plus :size="13" />
                  </button>
                </div>
                <article
                  v-for="entry in scheduleEntries(member.id, day)"
                  :key="entry.id"
                  :class="`calendar-entry schedule-${entry.entry_type}`"
                >
                  <strong>{{ new Date(entry.starts_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) }}–{{ new Date(entry.ends_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) }}</strong><small :class="{ 'print-sensitive': entry.entry_type === 'event' }">{{ entry.entry_type === 'shift' ? 'Présence' : entry.entry_type === 'absence' ? 'Congé / absence' : entry.label }}</small><small v-if="entry.entry_type === 'event'" class="print-only-public">Accompagnement / réunion</small><small v-if="entry.entry_type === 'event'" class="print-sensitive">Avec {{ entry.participant_names.join(', ') }}</small><small v-if="entry.entry_type === 'event' && entry.person_names.length" class="print-sensitive">Personnes accompagnées : {{ entry.person_names.join(', ') }}</small><button
                    v-if="session.permissions.includes('schedule.manage') || (entry.entry_type === 'event' && entry.created_by === session.user.id)"
                    class="icon-button"
                    title="Annuler ce créneau"
                    @click="cancelScheduleEntry(entry)"
                  >
                    <X :size="14" />
                  </button><button
                    v-if="entry.entry_type === 'event' && entry.created_by === session.user.id"
                    class="review-button"
                    title="Saisir le bilan"
                    @click="startEventReview(entry)"
                  >
                    <ClipboardCheck :size="14" />
                  </button><button
                    v-if="entry.entry_type === 'event' && entry.created_by === session.user.id"
                    class="edit-event-button"
                    title="Modifier l'événement"
                    @click="editEvent(entry)"
                  >
                    <Pencil :size="14" />
                  </button><div
                    v-if="entry.entry_type === 'event' && entry.user_id === session.user.id && entry.created_by !== session.user.id && entry.invitation_status === 'pending'"
                    class="invitation-actions"
                  >
                    <button
                      title="Accepter"
                      @click="respondInvitation(entry, 'accepted')"
                    >
                      <CheckCircle2 :size="13" />
                    </button><button
                      title="Refuser"
                      @click="respondInvitation(entry, 'declined')"
                    >
                      <X :size="13" />
                    </button>
                  </div><span
                    v-if="entry.entry_type === 'absence' && entry.approval_status === 'pending'"
                    class="pending-leave"
                  >En attente</span><div
                    v-if="entry.entry_type === 'absence' && entry.approval_status === 'pending' && session.permissions.includes('leave.approve')"
                    class="leave-actions"
                  >
                    <button
                      title="Valider"
                      @click="decideLeave(entry, 'approved')"
                    >
                      <CheckCircle2 :size="13" />
                    </button><button
                      title="Refuser"
                      @click="decideLeave(entry, 'rejected')"
                    >
                      <X :size="13" />
                    </button>
                  </div>
                </article>
              </div>
            </template>
            <p
              v-if="!scheduleMembers.length"
              class="empty-row calendar-empty"
            >
              Aucun professionnel actif dans cette unité.
            </p>
          </div>
          <div
            v-else
            class="team-calendar people-calendar"
            :style="{ '--calendar-columns': `170px repeat(${scheduleDays.length}, minmax(120px, 1fr))` }"
          >
            <div class="calendar-corner">
              Personnes accompagnees
            </div><div
              v-for="day in scheduleDays"
              :key="day.toISOString()"
              class="calendar-day"
            >
              <strong>{{ day.toLocaleDateString('fr-FR', { weekday: 'short' }) }}</strong><span>{{ day.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) }}</span>
            </div>
            <template v-for="person in schedulePeople" :key="person.id">
              <div class="calendar-member">
                <span class="person-avatar">{{ person.display_name.split(' ').map((part) => part[0]).join('').slice(0, 2) }}</span><span><strong>{{ person.display_name }}</strong><small>Planning d'accompagnement</small></span>
              </div><div
                v-for="day in scheduleDays"
                :key="`${person.id}-${day.toISOString()}`"
                class="calendar-cell"
              >
                <article
                  v-for="entry in personScheduleEntries(person.id, day)"
                  :key="entry.id"
                  class="calendar-entry schedule-event person-event"
                >
                  <strong>{{ new Date(entry.starts_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) }}-{{ new Date(entry.ends_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) }}</strong><small>{{ entry.label }}</small><small>Professionnels : {{ entry.participant_names.join(', ') }}</small>
                </article><button
                  v-if="session.permissions.includes('schedule.event.create')"
                  class="cell-add person-cell-add"
                  title="Ajouter un accompagnement pour cette personne"
                  @click="prepareCalendarEvent(day); scheduleForm.person_ids = [person.id]"
                >
                  <Plus :size="13" />
                </button>
              </div>
            </template>
            <p v-if="!schedulePeople.length" class="empty-row calendar-empty">
              Aucune personne accompagnee active dans cette unite.
            </p>
          </div>
        </section>
        <section
          v-else-if="activeView === 'notifications'"
          aria-labelledby="notifications-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Prise de poste
              </p>
              <h1 id="notifications-title">
                Notifications
              </h1>
            </div><span class="role-chip">{{ unreadNotifications }} non lue{{ unreadNotifications > 1 ? 's' : '' }}</span>
          </div>
          <div class="notification-list">
            <article
              v-for="item in notifications"
              :key="item.notification_key"
              :class="[`notification-${item.severity}`, { unread: !item.is_read }]"
            >
              <button
                class="notification-main"
                @click="openNotification(item)"
              >
                <Bell :size="19" /><span><strong>{{ item.title }}</strong><small>{{ item.detail }} · {{ new Date(item.occurred_at).toLocaleString('fr-FR') }}</small></span>
              </button><button
                class="icon-button dismiss-notification"
                title="Masquer cette notification"
                @click="dismissNotification(item)"
              >
                <X :size="17" />
              </button>
            </article><p
              v-if="!notifications.length"
              class="empty-row"
            >
              Aucune notification en attente.
            </p>
          </div>
        </section>
        <section
          v-else-if="activeView === 'acceptance'"
          aria-labelledby="acceptance-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Lot 14 · Campagne pilote
              </p><h1 id="acceptance-title">
                Recette métier
              </h1>
            </div><span
              v-if="acceptance"
              :class="acceptance.summary.complete ? 'active-status' : 'role-chip'"
            >{{ acceptance.summary.passed }} / {{ acceptance.summary.total }} réussis</span>
          </div>
          <div
            v-if="acceptance"
            class="acceptance-list"
          >
            <article
              v-for="(item, index) in acceptance.items"
              :key="item.code"
            >
              <span class="scenario-number">{{ index + 1 }}</span><div class="scenario-copy">
                <strong>{{ item.title }}</strong><p>{{ item.expected_result }}</p><small v-if="item.tested_at">Testé par {{ item.tester_name }} le {{ new Date(item.tested_at).toLocaleString('fr-FR') }}</small>
              </div><select
                v-model="item.status"
                :aria-label="`Résultat de ${item.title}`"
              >
                <option value="pending">
                  Non testé
                </option><option value="passed">
                  Réussi
                </option><option value="failed">
                  Échoué
                </option><option value="blocked">
                  Bloqué
                </option>
              </select><input
                v-model="item.notes"
                maxlength="2000"
                :aria-label="`Observations pour ${item.title}`"
                placeholder="Observations et preuve"
              ><button
                class="secondary-button"
                @click="saveAcceptance(item)"
              >
                Enregistrer
              </button>
            </article>
          </div>
        </section>
        <section
          v-else-if="activeView === 'pilot-issues'"
          aria-labelledby="pilot-issues-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Lot 15 · Stabilisation
              </p><h1 id="pilot-issues-title">
                Anomalies pilote
              </h1>
            </div><span
              v-if="pilotIssues"
              :class="pilotIssues.summary.critical ? 'locked-status' : 'active-status'"
            ><CircleAlert :size="15" />{{ pilotIssues.summary.critical ? `${pilotIssues.summary.critical} critique(s)` : 'Aucun blocage critique' }}</span>
          </div>
          <div
            v-if="pilotIssues"
            class="issue-summary"
          >
            <span><strong>{{ pilotIssues.summary.open }}</strong>à traiter</span><span><strong>{{ pilotIssues.items.length }}</strong>au total</span>
          </div>
          <form
            class="issue-form"
            @submit.prevent="createPilotIssue"
          >
            <label>Scénario de recette<select v-model="issueForm.acceptance_code"><option value="">Non lié</option><option
              v-for="scenario in acceptance?.items"
              :key="scenario.code"
              :value="scenario.code"
            >{{ scenario.title }}</option></select></label><label>Titre<input
              v-model="issueForm.title"
              required
              minlength="3"
              maxlength="200"
              placeholder="Résumer le problème"
            ></label><label>Description<textarea
              v-model="issueForm.description"
              maxlength="3000"
              rows="1"
              placeholder="Contexte et étapes"
            /></label><label>Gravité<select v-model="issueForm.severity"><option value="minor">Mineure</option><option value="major">Majeure</option><option value="critical">Critique</option></select></label><button class="primary-button">
              <Plus :size="17" />Déclarer
            </button>
          </form>
          <div
            v-if="pilotIssues"
            class="issue-list"
          >
            <article
              v-for="item in pilotIssues.items"
              :key="item.id"
              class="issue-row"
            >
              <span :class="['issue-severity', `severity-${item.severity}`]">{{ item.severity === 'critical' ? 'Critique' : item.severity === 'major' ? 'Majeure' : 'Mineure' }}</span><div class="issue-copy">
                <strong>{{ item.title }}</strong><p v-if="item.description">
                  {{ item.description }}
                </p><small>{{ item.scenario_title || 'Hors scénario' }} · déclaré par {{ item.creator_name }}</small>
              </div><select
                v-model="item.status"
                :aria-label="`État de ${item.title}`"
              >
                <option value="open">
                  Ouverte
                </option><option value="in_progress">
                  En cours
                </option><option value="resolved">
                  Résolue
                </option><option value="accepted">
                  Risque accepté
                </option>
              </select><select
                v-model="item.assigned_to"
                :aria-label="`Responsable de ${item.title}`"
              >
                <option :value="null">
                  Non affectée
                </option><option
                  v-for="user in users"
                  :key="user.id"
                  :value="user.id"
                >
                  {{ user.display_name }}
                </option>
              </select><button
                class="secondary-button"
                @click="updatePilotIssue(item)"
              >
                Enregistrer
              </button>
            </article><p
              v-if="!pilotIssues.items.length"
              class="empty-row"
            >
              Aucune anomalie déclarée pendant le pilote.
            </p>
          </div>
        </section>
        <section
          v-else-if="activeView === 'readiness'"
          aria-labelledby="readiness-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Lot 13 · Gouvernance
              </p><h1 id="readiness-title">
                Préparation du pilote
              </h1>
            </div><span
              v-if="pilotReadiness"
              :class="pilotReadiness.summary.ready ? 'active-status' : 'locked-status'"
            ><ShieldCheck :size="15" />{{ pilotReadiness.summary.ready ? 'Prêt pour décision' : 'Validations requises' }}</span>
          </div>
          <template v-if="pilotReadiness">
            <div class="readiness-summary">
              <article><strong>{{ pilotReadiness.summary.technical_passed }} / {{ pilotReadiness.summary.technical_total }}</strong><span>contrôles techniques</span></article><article><strong>{{ pilotReadiness.summary.validated }} / {{ pilotReadiness.summary.total }}</strong><span>décisions validées</span></article>
            </div>
            <section class="readiness-band">
              <h2>Contrôles techniques</h2><div class="technical-checks">
                <article
                  v-for="check in pilotReadiness.technical_checks"
                  :key="check.code"
                >
                  <CheckCircle2
                    v-if="check.passed"
                    :size="19"
                  /><X
                    v-else
                    :size="19"
                  /><span>{{ check.label }}</span><strong>{{ check.passed ? 'Satisfait' : 'À traiter' }}</strong>
                </article>
              </div>
            </section>
            <section class="readiness-band">
              <h2>Validations de l’organisme</h2><div class="decision-list">
                <article
                  v-for="item in pilotReadiness.decisions"
                  :key="item.code"
                >
                  <div><strong>{{ item.label }}</strong><small>Responsable : {{ item.responsible }}</small></div><select
                    v-model="item.status"
                    :aria-label="`État de ${item.label}`"
                  >
                    <option value="pending">
                      À valider
                    </option><option value="validated">
                      Validé
                    </option><option value="blocked">
                      Bloqué
                    </option>
                  </select><input
                    v-model="item.evidence"
                    maxlength="1000"
                    :aria-label="`Preuve pour ${item.label}`"
                    placeholder="Référence, date ou preuve"
                  ><button
                    class="secondary-button"
                    @click="savePilotDecision(item)"
                  >
                    Enregistrer
                  </button>
                </article>
              </div>
            </section>
          </template>
        </section>
        <section
          v-else-if="activeView === 'integrations'"
          aria-labelledby="integrations-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Interopérabilité maîtrisée
              </p><h1 id="integrations-title">
                Intégrations locales
              </h1>
            </div><span class="locked-status"><ShieldCheck :size="15" />Flux métier désactivés</span>
          </div>
          <div class="integration-intro">
            <Plug :size="22" /><div><strong>Connecteur HTTP local</strong><p>Le test envoie uniquement la version du schéma et un signal de connectivité. Aucun contenu métier ni identifiant de personne.</p><small>Hôtes autorisés : {{ integrationAllowedHosts.join(', ') }}</small></div>
          </div>
          <form
            class="integration-form"
            @submit.prevent="createIntegration"
          >
            <label>Nom<input
              v-model="integrationForm.label"
              required
              minlength="2"
              maxlength="100"
              placeholder="Logiciel local"
            ></label><label>Adresse locale<input
              v-model="integrationForm.endpoint_url"
              required
              type="url"
              maxlength="500"
            ></label><button class="primary-button">
              <Plus :size="16" />Ajouter désactivé
            </button>
          </form>
          <div class="integration-list">
            <article
              v-for="item in integrations"
              :key="item.id"
            >
              <span class="integration-icon"><Plug :size="18" /></span><div><strong>{{ item.label }}</strong><small>{{ item.endpoint_url }}</small><small v-if="item.last_tested_at">Dernier test {{ new Date(item.last_tested_at).toLocaleString('fr-FR') }} · {{ item.last_test_message }}</small></div><span :class="item.last_test_status === 'success' ? 'active-status' : 'draft-status'">{{ item.last_test_status === 'success' ? 'Joignable' : 'Désactivé' }}</span><button
                class="secondary-button"
                @click="testIntegration(item)"
              >
                Tester
              </button>
            </article><p
              v-if="!integrations.length"
              class="empty-row"
            >
              Aucun connecteur configuré.
            </p>
          </div>
        </section>
        <section
          v-else-if="activeView === 'operations'"
          aria-labelledby="operations-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Administration des donnees
              </p>
              <h1 id="operations-title">
                Conservation et exports
              </h1>
            </div><span class="locked-status"><ShieldCheck :size="15" />Purge desactivee</span>
          </div>
          <div class="operations-grid">
            <section class="operations-band">
              <div class="band-heading">
                <div><h2>Politiques de conservation</h2><p>Les durees restent soumises a validation juridique.</p></div>
              </div>
              <div class="policy-list">
                <article
                  v-for="policy in retentionPolicies"
                  :key="policy.data_type"
                >
                  <div><strong>{{ policy.data_type.replaceAll('_', ' ') }}</strong><small>{{ policy.legal_basis || 'Base legale a documenter' }}</small></div>
                  <label>Duree (jours)<input
                    v-model.number="policy.retention_days"
                    type="number"
                    min="1"
                    max="36500"
                    :disabled="!session.permissions.includes('retention.manage')"
                  ></label>
                  <span class="draft-status">A valider</span>
                  <button
                    v-if="session.permissions.includes('retention.manage')"
                    class="secondary-button"
                    :disabled="saving"
                    @click="saveRetention(policy)"
                  >
                    Enregistrer
                  </button>
                </article>
              </div>
            </section>
            <section class="operations-band export-panel">
              <div class="band-heading">
                <div><h2>Nouvel export</h2><p>Fichier temporaire, trace et limite au perimetre autorise.</p></div>
              </div>
              <form @submit.prevent="createExport">
                <label>Contenu<select v-model="exportForm.export_type"><option value="activity_summary">Synthese d activite</option><option value="audit_log">Journal d audit</option></select></label>
                <label>Format<select v-model="exportForm.format"><option value="json">JSON</option><option value="csv">CSV</option></select></label>
                <label class="reason-field">Motif<input
                  v-model="exportForm.reason"
                  required
                  minlength="5"
                  maxlength="500"
                  placeholder="Finalite de cet export"
                ></label>
                <button
                  class="primary-button"
                  :disabled="saving"
                >
                  <Download :size="17" />Generer
                </button>
              </form>
              <div
                v-if="latestExport"
                class="export-ready"
              >
                <CheckCircle2 :size="20" /><div><strong>{{ latestExport.record_count }} lignes pretes</strong><small>Empreinte {{ latestExport.sha256.slice(0, 16) }}... · expiration dans 15 minutes</small></div>
                <button
                  class="secondary-button"
                  @click="downloadExport"
                >
                  <Download :size="17" />Telecharger
                </button>
              </div>
            </section>
          </div>
        </section>
        <section
          v-else-if="activeView === 'users'"
          aria-labelledby="users-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Administration
              </p><h1 id="users-title">
                Équipe et accès
              </h1>
            </div>
          </div><div
            v-if="invitationMode"
            class="user-invitation"
          >
            <button class="back-button" @click="invitationMode = false">
              <ArrowLeft :size="17" />Retour
            </button>
            <form v-if="!invitationResult" @submit.prevent="createInvitation">
              <h2>Nouvelle invitation locale</h2>
              <label>Nom affiché<input v-model="invitationForm.display_name" required minlength="2" maxlength="160"></label>
              <label>Identifiant<input v-model="invitationForm.username" required minlength="3" maxlength="80" pattern="[a-z0-9._-]+"></label>
              <label>Adresse électronique<input v-model="invitationForm.email" required type="email" maxlength="254"></label>
              <label>Rôle<select v-model="invitationForm.role_code"><option value="professional">Professionnel</option><option value="team_manager">Coordinateur</option><option value="service_manager">Chef de service</option></select></label>
              <label>Unité principale<select v-model="invitationForm.unit_id" required><option
                v-for="item in structure?.items.filter((row) => row.unit_id)"
                :key="item.unit_id!"
                :value="item.unit_id!"
              >{{ item.service_name }} · {{ item.unit_name }}</option></select></label>
              <button class="primary-button" :disabled="saving"><Send :size="17" />Créer l'invitation</button>
            </form>
            <section v-else class="invitation-ticket">
              <span class="active-status">Lien créé</span>
              <h2>Remettre ce lien au professionnel</h2>
              <p>Valable jusqu'au {{ new Date(invitationResult.expires_at).toLocaleString('fr-FR') }} et utilisable une seule fois.</p>
              <code>{{ invitationResult.activation_url }}</code>
              <div><button class="secondary-button" @click="printInvitation"><Printer :size="17" />Imprimer</button><button class="primary-button" @click="invitationMode = false; invitationResult = null">Terminer</button></div>
            </section>
          </div><div
            v-else-if="!selectedUser"
            class="data-table-wrap"
          >
            <button class="primary-button invite-user-button" @click="openInvitation">
              <Plus :size="17" />Inviter un professionnel
            </button>
            <table>
              <thead><tr><th>Utilisateur</th><th>Identifiant</th><th>Rôle</th><th>Unité</th><th>État</th></tr></thead><tbody>
                <tr
                  v-for="user in users"
                  :key="user.id"
                >
                  <td><strong>{{ user.display_name }}</strong><span>{{ user.email }}</span></td><td>{{ user.username }}</td><td>{{ user.roles }}</td><td>{{ user.units || 'Organisation' }}</td><td>
                    <span :class="user.status === 'active' ? 'active-status' : 'archived-status'">{{ user.status === 'active' ? 'Actif' : user.status === 'invited' ? 'Invité' : 'Desactive' }}</span><button
                      class="secondary-button"
                      @click="openUser(user)"
                    >
                      Gerer
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div><article
            v-if="selectedUser && !invitationMode"
            class="user-admin-detail"
          >
            <button
              class="back-button"
              @click="selectedUser = null"
            >
              <ArrowLeft :size="17" />Retour a l equipe
            </button>
            <header><span :class="selectedUser.status === 'active' ? 'active-status' : 'archived-status'">{{ selectedUser.status === 'active' ? 'Actif' : selectedUser.status === 'invited' ? 'Invité' : 'Desactive' }}</span><h2>{{ selectedUser.display_name }}</h2><p>{{ selectedUser.username }} · {{ selectedUser.email }}</p></header>
            <div v-if="selectedUser.status === 'invited'" class="invitation-actions">
              <p>Ce compte attend son activation locale.</p>
              <button class="secondary-button" @click="renewInvitation"><Send :size="17" />Renouveler le lien</button>
              <button class="danger-button" :disabled="userReason.trim().length < 5" @click="revokeInvitation"><X :size="17" />Révoquer</button>
            </div>
            <section v-if="invitationResult" class="invitation-ticket">
              <h3>Nouveau lien à remettre</h3>
              <code>{{ invitationResult.activation_url }}</code>
              <button class="secondary-button" @click="printInvitation"><Printer :size="17" />Imprimer</button>
            </section>
            <label class="admin-reason">Motif de la modification<input
              v-model="userReason"
              minlength="5"
              maxlength="500"
              placeholder="Motif obligatoire pour retirer un acces"
            ></label>
            <section>
              <div class="band-heading">
                <h3>Rattachements</h3>
              </div><div class="membership-list">
                <article
                  v-for="membership in selectedUser.memberships?.filter((item) => !item.ends_at)"
                  :key="membership.id"
                >
                  <div><strong>{{ membership.unit_name }}</strong><small>{{ membership.service_name }}{{ membership.is_primary ? ' · principal' : '' }}</small></div><button
                    class="danger-button"
                    :disabled="userReason.trim().length < 5"
                    @click="revokeUserMembership(membership)"
                  >
                    Retirer
                  </button>
                </article>
              </div><form
                class="membership-form"
                @submit.prevent="addUserMembership"
              >
                <label>Nouvelle unite<select v-model="membershipUnit"><option
                  v-for="unit in structure?.items.filter((item) => item.unit_id)"
                  :key="unit.unit_id || ''"
                  :value="unit.unit_id || ''"
                >{{ unit.establishment_name }} · {{ unit.service_name }} · {{ unit.unit_name }}</option></select></label><button class="secondary-button">
                  Ajouter comme principal
                </button>
              </form>
            </section>
            <section v-if="selectedUser.status !== 'invited'" class="account-status-action">
              <div><strong>{{ selectedUser.status === 'active' ? 'Desactiver le compte' : 'Reactiver le compte' }}</strong><p>La modification ferme immediatement toutes les sessions de cet utilisateur.</p></div><button
                :class="selectedUser.status === 'active' ? 'danger-button' : 'primary-button'"
                :disabled="userReason.trim().length < 5"
                @click="changeUserStatus"
              >
                {{ selectedUser.status === 'active' ? 'Desactiver' : 'Reactiver' }}
              </button>
            </section>
          </article>
        </section>
        <section
          v-else-if="activeView === 'structure'"
          aria-labelledby="structure-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                {{ structure?.organization.name }}
              </p><h1 id="structure-title">
                Structure
              </h1>
            </div>
          </div><form
            class="inline-form"
            @submit.prevent="createUnit"
          >
            <label for="unit-name">Nouvelle unité</label><input
              id="unit-name"
              v-model="newUnitName"
              minlength="2"
              maxlength="120"
              placeholder="Nom de l’unité"
              required
            ><button
              class="primary-button"
              :disabled="saving"
            >
              <Plus :size="17" />Ajouter
            </button>
          </form><div class="structure-list">
            <article
              v-for="row in structure?.items"
              :key="row.unit_id ?? `${row.service_id}-${row.unit_name}`"
            >
              <Building2 :size="20" /><div><strong>{{ row.unit_name }}</strong><span>{{ row.establishment_name }} · {{ row.service_name }}</span></div><span class="active-status">Active</span>
            </article>
          </div>
        </section>
        <section
          v-else-if="activeView === 'audit'"
          aria-labelledby="audit-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                Traçabilité
              </p><h1 id="audit-title">
                Journal d’audit
              </h1>
            </div>
          </div><div class="timeline">
            <article
              v-for="event in auditEvents"
              :key="event.id"
            >
              <span class="timeline-dot" /><div><strong>{{ event.event_type }}</strong><p>{{ event.actor_name || 'Système' }}</p></div><time>{{ new Date(event.occurred_at).toLocaleString('fr-FR') }}</time>
            </article><p
              v-if="!auditEvents.length"
              class="empty-row"
            >
              Aucun événement pour le moment.
            </p>
          </div>
        </section>
        <section
          v-else
          aria-labelledby="access-title"
        >
          <div class="page-heading">
            <div>
              <p class="eyebrow">
                {{ t('security') }}
              </p><h1 id="access-title">
                {{ t('access') }}
              </h1>
            </div>
          </div><dl class="access-details">
            <div><dt>{{ t('account') }}</dt><dd>{{ session.user.display_name }} · {{ session.user.email }}</dd></div><div><dt>{{ t('activeRole') }}</dt><dd>{{ session.roles.map((role) => role.label).join(', ') }}</dd></div><div><dt>{{ t('scope') }}</dt><dd>{{ currentContext ? `${currentContext.establishment_name} · ${currentContext.service_name} · ${currentContext.name}` : t('wholeOrganization') }}</dd></div><div><dt>{{ t('session') }}</dt><dd><span class="status-dot" />{{ t('keycloakSession') }}</dd></div>
            <div>
              <dt>{{ t('language') }}</dt>
              <dd class="language-preference">
                <label class="language-select">
                  <Languages :size="17" />
                  <select
                    :value="locale"
                    @change="updateLocale"
                  >
                    <option value="fr">{{ t('french') }}</option>
                    <option value="en">{{ t('english') }}</option>
                  </select>
                </label>
                <small>{{ t('languageHelp') }}</small>
              </dd>
            </div>
          </dl>
        </section>
      </main>
    </div>
  </div>
</template>
