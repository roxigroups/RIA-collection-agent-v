export type RoleKey = 'OW' | 'CM' | 'CE' | 'AC' | 'PA' | 'TA';

export interface RoleInfo {
  k: RoleKey;
  n: string;
  sub: string;
}

export type PermissionLevel = 'F' | 'A' | 'V' | 'X';

export type ScreenKey =
  | 'login'
  | 'dashboard'
  | 'collections'
  | 'retailers'
  | 'calls'
  | 'calldetail'
  | 'reschedule'
  | 'tickets'
  | 'contacts'
  | 'reports'
  | 'support';

export type ViewState = 'normal' | 'loading' | 'empty' | 'error' | 'offline';

export interface NavItem {
  k: ScreenKey;
  t: string;
  ic: string;
  scr: string;
}

export interface CampaignContact {
  id: string;
  name: string;
  phno: string;
  creditPeriod: string;
  addedAt?: string;
}

export interface EscalationItem {
  id: string;
  category: string;
  customer: string;
  severity: 'High' | 'Medium' | 'Low';
  owner: string;
  age: string;
  sourceCallId: string;
  status: 'Open' | 'Resolved';
  resolutionNote?: string;
}

export type Ticket = EscalationItem;

export interface CallBatch {
  id: string;
  name: string;
  createdAt: string;
  importedBy: string;
  fileName: string;
  totalCalls: number;
  completedCalls: number;
  connectedCalls: number;
  ptpCount: number;
  ptpAmount: number;
  disputeCount: number;
  noLiftCount: number;
  status: 'Completed' | 'In Progress' | 'Scheduled';
  // Where the run is: waiting for "Start calling", being called, paused, or finished
  dialState: 'ready' | 'running' | 'paused' | 'done';
  queuedCalls: number;
  liveCalls: number;
  customerNames?: string[];
  phones?: string[];
  calls: CallItem[];
}

export interface ScheduledCallbackItem {
  id: string;
  ret: string;
  name: string;
  ph: string;
  outstanding: number;
  type: 'customer_requested' | 'no_lift_retry' | 'busy_retry';
  priority: 'High' | 'Medium' | 'Normal';
  scheduledTime: string;
  relativeDue: string;
  isDueNow?: boolean;
  attempt: number;
  maxAttempts: number;
  aiNote: string;
  status: 'Queued' | 'Dialing' | 'Completed' | 'Exhausted' | 'Cancelled';
  sourceCallId: string;
  lastOutcome?: string;
}

export interface Retailer {
  id: string;
  name: string;
  code: string;
  city: string;
  owner: string;
  phone: string;
  lang: string;
  bucket: string;
  os: number;
  od: number;
  lim: number;
  lastCall: string;
  ptp: string;
  disp: string;
  score: number;
  auto: string;
  creditPeriod?: string;
  history?: Array<{
    d: string;
    typ: string;
    dur: string;
    disp: string;
  }>;
  invoices?: Array<{
    inv: string;
    amt: number;
    due: string;
    st: string;
  }>;
}

export interface TranscriptTurn {
  who: string;
  txt: string;
  lang: string;
  // Seconds into the call's recording, and how long the turn lasted
  t?: number;
  d?: number;
  // RIA stopped here because the customer started talking
  cut?: boolean;
}

export interface CallItem {
  id: string;
  ret: string;
  name: string;
  ph: string;
  time: string;
  lang: string;
  dur: string;
  disp: string;
  ptp: string;
  auto: string;
  score: number;
  turns: TranscriptTurn[];
  batchId?: string;
  summary?: string;
  // Calls still to come: the dialer's id and where the call is
  callId?: string;
  callState?: 'queued' | 'dialing' | 'live';
  dialNow?: boolean;
}

// GET /api/live: who RIA is on the phone with now, and who is next
export interface LiveCall {
  callId: string;
  name: string;
  business: string;
  ph: string;
  invoice: string;
  amount: number;
  state: 'ringing' | 'on_call';
  seconds: number;
  batchId: string | null;
  batchName: string;
}

export interface NextCall {
  callId: string;
  name: string;
  ph: string;
  invoice: string;
  amount: number;
  dialNow: boolean;
  batchId: string | null;
  batchName: string;
}

// GET /api/batches/<id>/sheet: one line of the imported call sheet and its call
export interface SheetRow {
  row: number;
  callId: string;
  name: string;
  business: string;
  ph: string;
  invoice: string;
  amount: number;
  dueDate: string;
  state: 'queued' | 'dialing' | 'live' | 'done' | 'cancelled';
  dialNow: boolean;
  outcome: string;
  promised: string;
  notes: string;
  duration: string;
  recordId: string;
  seconds: number;
  attempts: number;
}

export interface LiveState {
  live: LiveCall[];
  next: NextCall[];
  waiting: number;
  dialer: DialerStatus;
}

export interface PtpItem {
  id: string;
  ret: string;
  name: string;
  due: string;
  amt: number;
  st: 'due' | 'upcoming' | 'kept' | 'broken';
  auto: string;
  ph: string;
}

export interface NoLiftItem {
  ret: string;
  name: string;
  att: number;
  last: string;
  next: string;
  auto: string;
  ph: string;
}

export interface ResponseStat {
  k: string;
  l: string;
  n: number;
  c: string;
  d: string;
}

export interface UserItem {
  id: string;
  n: string;
  e: string;
  role: RoleKey;
  ph: string;
  st: string;
}

export interface TrendItem {
  d: string;
  placed: number;
  conn: number;
  ptp: number;
}

export interface RecoveryItem {
  d: string;
  dem: number;
  rec: number;
}

export interface PhoneNumberItem {
  num: string;
  lbl: string;
  pri: boolean;
  on: boolean;
}

export interface AppConfig {
  provider: string;
  creds: Record<string, Record<string, string>>;
  numbers: PhoneNumberItem[];
  voice: {
    voice: string;
    speed: number;
    pitch: number;
    punct: boolean;
    noise: boolean;
    lang: string;
  };
  rules: {
    cap: number;
    starthour: string;
    endhour: string;
    cooldown: number;
    ptpwindow: number;
    escalate: number;
    blockdispute: boolean;
    blockholiday: boolean;
  };
  general: {
    tenant: string;
    gstin: string;
    callerid: string;
    audiodays: number;
    auditdays: number;
    webhook: string;
    escalateemail: string;
    escalatesms: string;
  };
}

export interface ReportItem {
  k: string;
  n: string;
  d: string;
  fmt: string;
  fn: string;
}

export interface AllResponseItem {
  ret: string;
  name: string;
  ph: string;
  disp: string;
  st: string;
  sc: string;
  auto: string;
}

export interface RecoverySummaryData {
  invoiced: number;
  invoiceAccounts: number;
  promisedMtd: number;
  pipeline: number;
}

export interface Me {
  id: string;
  n: string;
  e: string;
  role: RoleKey;
  company?: string;
}

export interface DialerStatus {
  paused?: boolean;
  configured?: boolean;
  in_calling_hours?: boolean;
  calling_hours?: string;
  active?: number;
  running?: boolean;
  error?: string;
}

// Everything GET /api/state returns (backend/dashboard_db.py Dashboard.state)
export interface AppState {
  me: Me;
  retailers: Retailer[];
  calls: CallItem[];
  batches: CallBatch[];
  scheduledCallbacks: ScheduledCallbackItem[];
  escalations: EscalationItem[];
  campaignContacts: CampaignContact[];
  users: UserItem[];
  config: AppConfig;
  ptps: PtpItem[];
  nolift: NoLiftItem[];
  allResp: AllResponseItem[];
  resp: ResponseStat[];
  trend: TrendItem[];
  recovery: RecoveryItem[];
  summary: RecoverySummaryData;
  auditLog: string[][];
  dialer: DialerStatus;
}

// A call sheet row as the import screen sends it
export interface ImportRow {
  businessName: string;
  name?: string;
  phone: string;
  invoiceNumber: string;
  invoiceDate: string;
  invoiceAmount: number;
  lang?: string;
}
