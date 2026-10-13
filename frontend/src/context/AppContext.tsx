'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import {
  RoleKey,
  ViewState,
  ScreenKey,
  PermissionLevel,
  Retailer,
  CallItem,
  CallBatch,
  ScheduledCallbackItem,
  EscalationItem,
  UserItem,
  AppConfig,
  CampaignContact,
  PtpItem,
  NoLiftItem,
  AllResponseItem,
  ResponseStat,
  TrendItem,
  RecoveryItem,
  RecoverySummaryData,
  DialerStatus,
  AppState,
  ImportRow,
  Me,
} from '@/types';
import { ROLES, PERM } from '@/data/mockData';
import { api, ApiError } from '@/lib/api';

// How often the screens refresh while signed in (calls finish in the background)
const REFRESH_MS = 10000;

interface ModalState {
  isOpen: boolean;
  title: string;
  body: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

// A customer already spoken to about this invoice in the last 20 hours
export interface RecentRow {
  row: number;
  name: string;
  phone: string;
  invoice: string;
  lastCall: string;
  outcome: string;
}

export interface ImportResult {
  batch: string | null;
  queued: number;
  skipped: { row: number; reason: string }[];
  // Set when nothing was imported yet: the user chooses to call these again or skip them
  recent?: RecentRow[];
}

interface AppContextType {
  role: RoleKey;
  setRole: (r: RoleKey) => void;
  viewState: ViewState;
  setViewState: (v: ViewState) => void;
  isLoggedIn: boolean;
  authChecked: boolean;
  // null when signed in, else what went wrong
  login: (user: string, pass: string) => Promise<string | null>;
  logout: () => void;
  meInfo: Me | null;
  selectedRetailerId: string;
  setSelectedRetailerId: (id: string) => void;
  selectedCallId: string;
  setSelectedCallId: (id: string) => void;
  collectionsTab: string;
  setCollectionsTab: (t: string) => void;
  escalations: EscalationItem[];
  assignEscalation: (id: string, owner: string) => void;
  resolveEscalation: (id: string, note?: string) => void;
  // Ticket aliases
  tickets: EscalationItem[];
  addTicket: (t: { cust?: string; cat?: string; who?: string; src?: string; st?: string }) => void;
  campaignContacts: CampaignContact[];
  addCampaignContact: (c: Omit<CampaignContact, 'id'>) => void;
  queueContactCall: (contactId: string) => Promise<boolean>;
  callRetailer: (retailerId: string) => Promise<boolean>;
  notConnected: (what: string) => void;
  users: UserItem[];
  updateUser: (id: string, updates: Partial<UserItem>) => void;
  config: AppConfig;
  batches: CallBatch[];
  importCallSheet: (
    fileName: string,
    rows: ImportRow[],
    start?: boolean,
    recent?: 'call' | 'skip'
  ) => Promise<ImportResult | null>;
  startBatch: (batchId: string) => Promise<boolean>;
  pauseBatch: (batchId: string) => Promise<boolean>;
  dialCallNow: (callId: string, name: string) => Promise<boolean>;
  deleteBatch: (batchId: string) => Promise<boolean>;
  removeSheetRow: (callId: string, name: string) => Promise<boolean>;
  deleteCampaignContacts: (ids: string[]) => Promise<boolean>;
  selectedBatchId: string | null;
  setSelectedBatchId: (id: string | null) => void;
  downloadBatchReport: (b: CallBatch) => void;
  scheduledCallbacks: ScheduledCallbackItem[];
  rescheduleCall: (id: string, newTime: string, note?: string) => void;
  triggerImmediateDial: (id: string) => void;
  cancelScheduledCall: (id: string, reason?: string) => void;
  retailers: Retailer[];
  calls: CallItem[];
  ptps: PtpItem[];
  nolift: NoLiftItem[];
  allResp: AllResponseItem[];
  resp: ResponseStat[];
  respTotal: number;
  trend: TrendItem[];
  recovery: RecoveryItem[];
  summary: RecoverySummaryData;
  auditLog: string[][];
  dialer: DialerStatus;
  lastSync: Date | null;
  refresh: () => Promise<void>;
  toast: string | null;
  showToast: (msg: string) => void;
  modal: ModalState;
  openModal: (title: string, body: ReactNode, footer?: ReactNode, wide?: boolean) => void;
  closeModal: () => void;
  canAct: (scr: ScreenKey) => boolean;
  perm: (scr: ScreenKey, r?: RoleKey) => PermissionLevel;
  me: () => string;
}

const EMPTY_CONFIG: AppConfig = {
  provider: '',
  creds: {},
  numbers: [],
  voice: { voice: '', speed: 1, pitch: 0, punct: true, noise: true, lang: 'Telugu' },
  rules: { cap: 3, starthour: '08:00', endhour: '19:00', cooldown: 5, ptpwindow: 7, escalate: 2, blockdispute: true, blockholiday: true },
  general: { tenant: '', gstin: '', callerid: '', audiodays: 90, auditdays: 365, webhook: '', escalateemail: '', escalatesms: '' },
};
const EMPTY_SUMMARY: RecoverySummaryData = { invoiced: 0, invoiceAccounts: 0, promisedMtd: 0, pipeline: 0 };

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [meInfo, setMeInfo] = useState<Me | null>(null);
  const [viewState, setViewState] = useState<ViewState>('loading');
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [authChecked, setAuthChecked] = useState<boolean>(false);
  const [selectedRetailerId, setSelectedRetailerId] = useState<string>('');
  const [selectedCallId, setSelectedCallId] = useState<string>('');
  const [collectionsTab, setCollectionsTab] = useState<string>('today');
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [data, setData] = useState<AppState | null>(null);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>({ isOpen: false, title: '', body: null });
  const loaded = useRef(false);

  const role: RoleKey = meInfo?.role || 'PA';

  const showToast = useCallback((msg: string) => {
    setToast(msg);
  }, []);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3200);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const signedOut = useCallback(() => {
    setIsLoggedIn(false);
    setMeInfo(null);
    setData(null);
    loaded.current = false;
  }, []);

  const refresh = useCallback(async () => {
    try {
      const state = await api<AppState>('/state');
      setData(state);
      setLastSync(new Date());
      setMeInfo((prev) => ({ ...state.me, company: state.config.general.tenant || prev?.company }));
      setViewState('normal');
      loaded.current = true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        signedOut();
      } else if (err instanceof ApiError && err.status === 0) {
        setViewState('offline');
      } else if (!loaded.current) {
        setViewState('error');
      }
    }
  }, [signedOut]);

  // Signed in already? (the session cookie survives a page reload)
  useEffect(() => {
    api<{ signed_in: boolean; user: Me | null }>('/session')
      .then((s) => {
        if (s.signed_in && s.user) {
          setMeInfo(s.user);
          setIsLoggedIn(true);
        }
      })
      .catch(() => setViewState('offline'))
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!isLoggedIn) return;
    // First load straight after sign-in, then every REFRESH_MS
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [isLoggedIn, refresh]);

  // Runs a change, reports it, and reloads what the screens show
  const act = useCallback(
    async (call: () => Promise<unknown>, done?: string): Promise<boolean> => {
      try {
        await call();
        if (done) showToast(done);
        await refresh();
        return true;
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Something went wrong');
        if (err instanceof ApiError && err.status === 401) signedOut();
        return false;
      }
    },
    [refresh, showToast, signedOut]
  );

  const setRole = (r: RoleKey) => {
    // Roles come from the signed-in user; switching is done by an owner in Team & Permissions
    if (r !== role) showToast(`You are signed in as ${ROLES[role]?.n || role}`);
  };

  const login = async (user: string, pass: string): Promise<string | null> => {
    try {
      const res = await api<{ user: Me }>('/login', { body: { email: user, password: pass } });
      setMeInfo(res.user);
      setViewState('loading');
      setIsLoggedIn(true);
      showToast('Signed in successfully');
      return null;
    } catch (err) {
      // The dashboard answers 500 when it cannot forward to the API (server.py not running)
      if (err instanceof ApiError && err.status !== 401 && err.status !== 400) {
        return 'Cannot reach the RIA server. Start the API (python3 server.py in backend/) and try again.';
      }
      return 'Those credentials did not work. Check and try again.';
    }
  };

  const logout = () => {
    api('/logout', { body: {} }).finally(signedOut);
  };

  const openModal = (title: string, body: ReactNode, footer?: ReactNode, wide = false) => {
    setModal({ isOpen: true, title, body, footer, wide });
  };

  const closeModal = () => {
    setModal({ isOpen: false, title: '', body: null });
  };

  const addEscalation = (e: Omit<EscalationItem, 'id' | 'age'>) => {
    act(() => api('/tickets', { body: e }), 'Ticket logged');
  };

  const assignEscalation = (id: string, owner: string) => {
    act(() => api(`/tickets/${id}`, { method: 'PATCH', body: { owner } }), `${id} assigned to ${owner}`);
  };

  const resolveEscalation = (id: string, note?: string) => {
    act(
      () => api(`/tickets/${id}`, { method: 'PATCH', body: { status: 'Resolved', resolutionNote: note || 'Resolved by reviewer' } }),
      `✓ Ticket ${id} resolved`
    );
  };

  const addTicket = (t: { cust?: string; cat?: string; who?: string; src?: string; st?: string }) => {
    addEscalation({
      category: t.cat || 'Dispute raised',
      customer: t.cust || 'Retailer Account',
      severity: 'High',
      owner: t.who || 'Unassigned',
      sourceCallId: t.src || '',
      status: 'Open',
    });
  };

  const addCampaignContact = (c: Omit<CampaignContact, 'id'>) => {
    act(() => api('/campaign-contacts', { body: c }), `Contact ${c.name} added to campaign list`);
  };

  const queueContactCall = (contactId: string) =>
    act(() => api(`/contacts/${contactId}/call`, { body: {} }), '✓ Queued — RIA will call within calling hours');

  const callRetailer = (retailerId: string) =>
    act(() => api(`/retailers/${retailerId}/call`, { body: {} }), '📞 Queued — RIA will call within calling hours');

  // For buttons whose channel isn't set up yet (WhatsApp, payment links, field visits)
  const notConnected = (what: string) => {
    showToast(`${what} isn't connected yet — nothing was sent.`);
  };

  const updateUser = (id: string, updates: Partial<UserItem>) => {
    act(() => api(`/users/${id}`, { method: 'PATCH', body: updates }), 'User updated');
  };

  // Why a started call won't go out yet, so nobody waits for a call that can't happen
  const hoursNote = () =>
    data?.dialer.paused
      ? ' — but the dialer is paused on the server, so no calls go out until it is restarted without DIALER_START_PAUSED=1'
      : data?.dialer.running === false
      ? ' — but the dialer is not running on the server'
      : data?.dialer.in_calling_hours === false
      ? ` — outside calling hours (${data.dialer.calling_hours}), calls wait until they open`
      : '';

  const startBatch = (batchId: string) =>
    act(() => api(`/batches/${batchId}/start`, { body: {} }), `📞 Calling ${batchId} one after another${hoursNote()}`);

  const pauseBatch = (batchId: string) =>
    act(() => api(`/batches/${batchId}/pause`, { body: {} }), `⏸ Paused ${batchId} — a call already on the line finishes`);

  const dialCallNow = (callId: string, name: string) =>
    act(() => api(`/calls/${callId}/dial`, { body: {} }), `📞 ${name} will be called next${hoursNote()}`);

  const deleteBatch = async (batchId: string) => {
    const ok = await act(() => api(`/batches/${batchId}`, { method: 'DELETE' }), `🗑 Deleted ${batchId}`);
    if (ok && selectedBatchId === batchId) setSelectedBatchId(null);
    return ok;
  };

  const removeSheetRow = (callId: string, name: string) =>
    act(() => api(`/calls/${callId}/cancel`, { body: {} }), `Removed ${name} from this campaign`);

  const deleteCampaignContacts = (ids: string[]) =>
    act(
      () => api('/campaign-contacts/delete', { body: { ids } }),
      `🗑 Deleted ${ids.length} contact${ids.length === 1 ? '' : 's'}`
    );

  const importCallSheet = async (
    fileName: string,
    rows: ImportRow[],
    start = false,
    recent?: 'call' | 'skip'
  ): Promise<ImportResult | null> => {
    try {
      const res = await api<ImportResult>('/batches', { body: { fileName, rows, start, recent } });
      await refresh();
      return res;
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Import failed');
      return null;
    }
  };

  const downloadBatchReport = (b: CallBatch) => {
    const batchCalls = b.calls || [];
    const rows = [
      ['Batch ID', 'Batch Name', 'Created At', 'Imported By', 'Source File'],
      [b.id, b.name, b.createdAt, b.importedBy, b.fileName],
      [],
      ['Total Calls', 'Connected', 'PTPs Committed', 'PTP Amount (INR)', 'Disputes', 'Not Lifted'],
      [b.totalCalls, b.connectedCalls, b.ptpCount, b.ptpAmount, b.disputeCount, b.noLiftCount],
      [],
      ['Call ID', 'Customer Name', 'Phone Number', 'Time', 'Language', 'Duration', 'Disposition', 'PTP Commitment'],
      ...batchCalls.map((c) => [
        c.id,
        c.name,
        c.ph,
        c.time,
        c.lang,
        c.dur,
        c.disp,
        c.ptp,
      ]),
    ];

    const fn = `batch_report_${b.id.toLowerCase().replace(/[^a-z0-9_]/g, '_')}.csv`;
    const url = URL.createObjectURL(
      new Blob(
        [
          '﻿' +
            rows
              .map((r) =>
                r
                  .map((v) => {
                    const s = String(v == null ? '' : v);
                    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
                  })
                  .join(',')
              )
              .join('\r\n'),
        ],
        { type: 'text/csv;charset=utf-8' }
      )
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = fn;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast(`Downloaded ${fn}`);
  };

  const rescheduleCall = (id: string, newTime: string, note?: string) => {
    act(() => api(`/callbacks/${id}/reschedule`, { body: { time: newTime, note } }), `✓ Call ${id} rescheduled to ${newTime}`);
  };

  const triggerImmediateDial = (id: string) => {
    const item = data?.scheduledCallbacks.find((c) => c.id === id);
    act(
      () => api(`/callbacks/${id}/dial`, { body: {} }),
      `📞 Dialing ${item ? `${item.name} (${item.ph})` : id} next${data?.dialer.in_calling_hours === false ? ' — outside calling hours, it waits until they open' : ''}`
    );
  };

  const cancelScheduledCall = (id: string, reason = 'Cancelled by user') => {
    act(() => api(`/callbacks/${id}/cancel`, { body: { reason } }), `Cancelled scheduled call ${id}`);
  };

  const perm = (scr: ScreenKey, r: RoleKey = role): PermissionLevel => {
    return PERM[scr]?.[r] || 'F';
  };

  const canAct = (scr: ScreenKey): boolean => {
    const p = perm(scr);
    return ['F', 'A'].includes(p);
  };

  const me = (): string => {
    return meInfo?.n || 'You';
  };

  const resp = data?.resp || [];

  return (
    <AppContext.Provider
      value={{
        role,
        setRole,
        viewState,
        setViewState,
        isLoggedIn,
        authChecked,
        login,
        logout,
        meInfo,
        selectedRetailerId,
        setSelectedRetailerId,
        selectedCallId,
        setSelectedCallId,
        collectionsTab,
        setCollectionsTab,
        escalations: data?.escalations || [],
        assignEscalation,
        resolveEscalation,
        tickets: data?.escalations || [],
        addTicket,
        campaignContacts: data?.campaignContacts || [],
        addCampaignContact,
        queueContactCall,
        callRetailer,
        notConnected,
        users: data?.users || [],
        updateUser,
        config: data?.config || EMPTY_CONFIG,
        batches: data?.batches || [],
        importCallSheet,
        startBatch,
        pauseBatch,
        dialCallNow,
        deleteBatch,
        removeSheetRow,
        deleteCampaignContacts,
        selectedBatchId,
        setSelectedBatchId,
        downloadBatchReport,
        scheduledCallbacks: data?.scheduledCallbacks || [],
        rescheduleCall,
        triggerImmediateDial,
        cancelScheduledCall,
        retailers: data?.retailers || [],
        calls: data?.calls || [],
        ptps: data?.ptps || [],
        nolift: data?.nolift || [],
        allResp: data?.allResp || [],
        resp,
        respTotal: resp.reduce((a, r) => a + r.n, 0),
        trend: data?.trend || [],
        recovery: data?.recovery || [],
        summary: data?.summary || EMPTY_SUMMARY,
        auditLog: data?.auditLog || [],
        dialer: data?.dialer || {},
        lastSync,
        refresh,
        toast,
        showToast,
        modal,
        openModal,
        closeModal,
        canAct,
        perm,
        me,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within an AppProvider');
  return ctx;
}
