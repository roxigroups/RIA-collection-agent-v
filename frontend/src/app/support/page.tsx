'use client';

import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import { useApp } from '@/context/AppContext';

const SUPPORT_EMAIL = 'gyan.ria@groupgroup.in';

export default function SupportPage() {
  const { showToast } = useApp();

  const copyEmail = async () => {
    try {
      await navigator.clipboard.writeText(SUPPORT_EMAIL);
      showToast('Email address copied');
    } catch {
      showToast(`Email us at ${SUPPORT_EMAIL}`);
    }
  };

  return (
    <AppShell screenKey="support">
      <PageHead screenKey="support" />

      <div className="card support-card">
        <div className="card-h">
          <h3>Contact us</h3>
        </div>
        <div className="card-b">
          <div className="support-mail">
            <span className="support-ic" aria-hidden="true">✉</span>
            <div>
              <div className="meta">Email</div>
              <a className="link support-addr" href={`mailto:${SUPPORT_EMAIL}`}>
                {SUPPORT_EMAIL}
              </a>
            </div>
          </div>

          <div className="support-actions">
            <a className="btn btn-primary btn-sm" href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('RIA support')}`}>
              Email us
            </a>
            <button type="button" className="btn btn-ghost btn-sm" onClick={copyEmail}>
              Copy address
            </button>
          </div>

          <div className="note">
            <b>To help us answer quickly,</b> include your company name, what you were doing, and the call ID or a
            screenshot if something went wrong.
          </div>
        </div>
      </div>
    </AppShell>
  );
}
