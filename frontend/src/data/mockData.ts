// Fixed UI settings: roles and permissions, navigation, page titles, CSV column
// names and empty-state texts. Live data comes from the API (AppContext).
import {
  NavItem,
  PermissionLevel,
  ReportItem,
  RoleInfo,
  RoleKey,
} from '@/types';

export const ROLES: Record<RoleKey, RoleInfo> = {
  OW: { k: 'OW', n: 'Distributor Owner', sub: 'Full access — approvals, billing, contacts' },
  CM: { k: 'CM', n: 'Credit / Collection Manager', sub: 'Day-to-day collection queue, dispute reviews' },
  CE: { k: 'CE', n: 'Collection Executive / Field Agent', sub: 'Assigned accounts, field visits, PTP tracking' },
  AC: { k: 'AC', n: 'Accountant', sub: 'Payment matching, ledger updates, invoice reconciliation' },
  PA: { k: 'PA', n: 'Principal Auditor', sub: 'Read-only compliance, dispute and audit trail reviews' },
  TA: { k: 'TA', n: 'Tenant Admin', sub: 'User management, contacts, role assignment' },
};

export const PERM: Record<string, Record<RoleKey, PermissionLevel>> = {
  dashboard:   { OW: 'F', CM: 'F', CE: 'V', AC: 'F', PA: 'V', TA: 'F' },
  collections: { OW: 'F', CM: 'F', CE: 'F', AC: 'V', PA: 'V', TA: 'V' },
  calls:       { OW: 'F', CM: 'F', CE: 'V', AC: 'X', PA: 'V', TA: 'F' },
  calldetail:  { OW: 'F', CM: 'F', CE: 'V', AC: 'V', PA: 'V', TA: 'F' },
  reschedule:  { OW: 'F', CM: 'F', CE: 'F', AC: 'V', PA: 'V', TA: 'F' },
  retailers:   { OW: 'F', CM: 'F', CE: 'F', AC: 'V', PA: 'V', TA: 'F' },
  tickets:     { OW: 'F', CM: 'F', CE: 'F', AC: 'F', PA: 'V', TA: 'F' },
  contacts:    { OW: 'F', CM: 'F', CE: 'F', AC: 'F', PA: 'V', TA: 'F' },
  reports:     { OW: 'F', CM: 'F', CE: 'V', AC: 'F', PA: 'V', TA: 'F' },
  support:     { OW: 'F', CM: 'F', CE: 'F', AC: 'F', PA: 'F', TA: 'F' },
};

export const NAV: NavItem[] = [
  { k: 'dashboard', t: 'Dashboard', ic: '⌂', scr: 'SCR-02' },
  { k: 'collections', t: 'Collections', ic: '₹', scr: 'SCR-03' },
  { k: 'calls', t: 'Call Campaign', ic: '☏', scr: 'SCR-05' },
  { k: 'reschedule', t: 'Reschedule', ic: '⏰', scr: 'SCR-17' },
  { k: 'tickets', t: 'Tickets', ic: '⚑', scr: 'SCR-11' },
  { k: 'contacts', t: 'Contacts', ic: '📇', scr: 'SCR-16' },
  { k: 'reports', t: 'Reports', ic: '📊', scr: 'SCR-18' },
  { k: 'support', t: 'Support', ic: '✉', scr: 'SCR-19' },
];

export const TITLES: Record<string, [string, string, string]> = {
  dashboard: ['SCR-02', 'Dashboard', 'Graphs and everyone who uses RIA.'],
  collections: ['SCR-03', 'Collections', 'Promises to pay, calls not lifted, and how every retailer responded today.'],
  calls: ['SCR-05', 'Call Campaign', 'Import the daily campaign call list as a CSV and follow every call through the day.'],
  calldetail: ['SCR-06', 'Call Detail', 'The evidential record of one call.'],
  reschedule: ['SCR-17', 'Reschedule & Callback Queue', 'Autonomous 5-min retries for unlifted calls and customer-requested callback time slots.'],
  retailers: ['SCR-04', 'Retailer 360', 'Everything known about one retailer, and what to do next.'],
  tickets: ['SCR-11', 'Tickets', 'Everything RIA could not, or should not, handle alone.'],
  contacts: ['SCR-16', 'Contacts', 'All customer accounts and retailers added across all campaigns so far.'],
  reports: ['SCR-18', 'Reports', 'Ready-made CSV reports of calls, payment commitments, disputes, missed calls and activity.'],
  support: ['SCR-19', 'Support', 'Questions or problems with RIA? Contact our team.'],
};

export const AV: Record<string, string> = {
  PA: '#53617C',
  TA: '#1E52C9',
  OW: '#0F2350',
  CM: '#0E8794',
  CE: '#157F4C',
  AC: '#B07C00',
};

export const PTP_ST: Record<string, [string, string]> = {
  due: ['Due today', 'c-gold'],
  upcoming: ['Upcoming', 'c-blue'],
  kept: ['Kept', 'c-green'],
  broken: ['Broken', 'c-red']
};

export const REPORTS: ReportItem[] = [
  { k: 'daily_summary', n: 'Daily Call Report', d: 'All calls, dispositions, PTPs committed and recovery totals for today.', fmt: 'CSV', fn: 'ria_daily_call_report_2026_04_14.csv' },
  { k: 'ptp_pipeline', n: 'Payment Commitments', d: 'Every promise to pay due in the next 14 days with retailer phone numbers.', fmt: 'CSV', fn: 'ria_payment_commitments.csv' },
  { k: 'disputes', n: 'Disputes & Issues', d: 'All retailers who disputed invoices, reasons given and assigned tickets.', fmt: 'CSV', fn: 'ria_disputes_and_issues.csv' },
  { k: 'no_lift', n: 'Missed Calls & Follow-ups', d: 'Retailers not reached after 2+ attempts for field executive follow-up.', fmt: 'CSV', fn: 'ria_missed_calls_followups.csv' },
  { k: 'audit_log', n: 'Activity Log', d: 'Immutable log of human approvals, config changes and rule overrides.', fmt: 'CSV', fn: 'ria_activity_log.csv' }
];

export const CSV_ALIASES: Record<string, string[]> = {
  business_name: ['business_name', 'business name', 'business', 'store_name', 'company', 'retailer_name', 'store', 'firm', 'name'],
  name: ['name', 'customer_name', 'contact_name', 'person', 'owner_name', 'business_name', 'business'],
  phno: ['phno', 'phone', 'mobile', 'ph', 'contact', 'tel', 'phone_number'],
  due_date: ['due_date', 'due date', 'duedate', 'due_dt', 'ptp_date', 'target_date', 'date', 'invoice_date', 'invoice date', 'inv_date', 'bill_date'],
  invoice_date: ['due_date', 'due date', 'duedate', 'due_dt', 'invoice_date', 'invoice date', 'inv_date', 'date', 'bill_date'],
  invoice_number: ['invoice_number', 'invoice number', 'inv_no', 'invoice_no', 'inv_num', 'bill_no', 'invoice', 'code', 'id'],
  invoice_amount: ['invoice_amount', 'invoice amount', 'amount', 'inv_amt', 'due_amount', 'due amount', 'balance', 'os', 'od', 'total_amount'],
  amount: ['amount', 'invoice_amount', 'invoice amount', 'os', 'total_amount', 'total_due', 'balance', 'total_os', 'order_amount'],
  due_amount: ['due_amount', 'due amount', 'invoice_amount', 'invoice amount', 'dueamt', 'od', 'overdue', 'past_due', 'od_amount', 'pending_amount'],
  credit_period: ['credit_period', 'credit period', 'creditperiod', 'terms', 'payment_terms', 'credit_days', 'days'],
  lang: ['lang', 'language', 'preferred_lang', 'vernacular'],
  code: ['code', 'retailer_code', 'cust_code', 'invoice_number', 'invoice_no', 'id'],
  city: ['city', 'location', 'area', 'town'],
  bucket: ['bucket', 'aging', 'ageing', 'days_past_due', 'dpd'],
};

export const EMPTIES: Record<string, [string, string, string]> = {
  dashboard: ['📊', 'No calls or recovery data today', 'Import the daily call list from the Calls tab to begin the run.'],
  collections: ['₹', 'No active promises or responses', 'Once calls are placed, promises and outcomes will populate here in real time.'],
  calls: ['☏', 'No calls in the queue', 'Drop a CSV call sheet above or click Load Sample Batch to run modelled calls.'],
  calldetail: ['🔍', 'No call selected', 'Pick a call from the Collections or Calls tab to view its transcript and outcome.'],
  retailers: ['🏪', 'No retailer selected', 'Pick a retailer from the table to see 360° account details and invoice ledger.'],
  tickets: ['⚑', 'No open escalations', 'Disputes, broken promises, and human escalations will surface here automatically.'],
  contacts: ['📇', 'No contacts added to campaigns yet', 'Upload a campaign call sheet or click Add Contact to register new customers.']
};
