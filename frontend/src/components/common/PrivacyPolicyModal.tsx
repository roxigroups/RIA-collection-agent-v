'use client';

import React, { useEffect } from 'react';

interface PrivacyPolicyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAccept?: () => void;
}

export default function PrivacyPolicyModal({ isOpen, onClose, onAccept }: PrivacyPolicyModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="privacy-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacy-modal-title"
    >
      <div className="privacy-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="privacy-modal-header">
          <div>
            <div className="privacy-badge">OFFICIAL PRIVACY POLICY</div>
            <h2 id="privacy-modal-title">RIA — Roxy Intelligent AI Telecalling Agent</h2>
            <div className="privacy-meta">
              <span>Version 1.1</span>
              <span>•</span>
              <span>Effective: 15-10-2026</span>
              <span>•</span>
              <span>Ref: RIA-LEG-PP-001</span>
            </div>
          </div>
          <button
            type="button"
            className="privacy-close-btn"
            onClick={onClose}
            aria-label="Close Privacy Policy"
          >
            ✕
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="privacy-modal-body">
          <div className="privacy-callout info">
            <strong>Legal Notice:</strong> We follow the <b>Digital Personal Data Protection Act, 2023</b> and the <b>Digital Personal Data Protection Rules, 2025</b> (together, &ldquo;DPDP law&rdquo;), and the <b>Information Technology Act, 2000</b>.
          </div>

          {/* Section 1 */}
          <section className="privacy-section">
            <h3>1. Who we are</h3>
            <p>
              RIA (Roxy Intelligent AI Telecalling Agent) is provided by <strong>Roxy Distributors LLP</strong> (LLPIN [LLPIN]), Registered office address, Hyderabad, Telangana — PIN (&ldquo;we&rdquo;, &ldquo;us&rdquo;). This policy explains what personal data we collect through our website <code>riaaiagent.com</code>, our demo agent, and the RIA application at <code>riaaiagent.cc</code>, why we collect it, and the choices and rights you have.
            </p>
          </section>

          {/* Section 2 */}
          <section className="privacy-section">
            <h3>2. Who this policy covers</h3>
            <div className="privacy-table-wrap">
              <table className="privacy-table">
                <thead>
                  <tr>
                    <th>You are</th>
                    <th>How we deal with you</th>
                    <th>Our role under DPDP law</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>A website visitor or demo user</strong></td>
                    <td>You browse riaaiagent.com, fill the contact form, chat on WhatsApp or talk to the demo agent</td>
                    <td><strong>Data Fiduciary</strong> — we decide how your data is used</td>
                  </tr>
                  <tr>
                    <td><strong>A user of the RIA application</strong></td>
                    <td>You or your company subscribe to RIA and sign in to riaaiagent.cc</td>
                    <td><strong>Data Fiduciary</strong> for your account data</td>
                  </tr>
                  <tr>
                    <td><strong>A retailer, dealer or shop that RIA calls</strong></td>
                    <td>A distributor who supplies you uses RIA to call you about invoices and payments</td>
                    <td><strong>Data Processor</strong> — we act on the distributor&rsquo;s instructions. The distributor is the Data Fiduciary for your data</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="privacy-subnote">
              If you are a retailer called by RIA, the distributor who supplies you decides why your data is used. You can contact that distributor, or us, and we will pass your request to them.
            </p>
          </section>

          {/* Section 3 */}
          <section className="privacy-section">
            <h3>3. What we collect</h3>
            <h4>3.1 Website and demo</h4>
            <ul>
              <li><strong>Contact form:</strong> your full name, phone number, email address (optional) and company name (optional). The form passes your details to our team on WhatsApp at +91 81066 68552.</li>
              <li><strong>WhatsApp chats:</strong> chats you start from our website.</li>
              <li><strong>Demo agent (riaaiagent.com/demo):</strong> the country code you choose, your voice while you talk to the demo through your browser microphone (a live WebRTC voice session), and the text of the conversation. Your browser asks for microphone permission first; the demo does not start without it.</li>
              <li><strong>Technical data:</strong> IP address, browser and device type, pages visited, collected for security and visitor statistics.</li>
            </ul>

            <h4>3.2 RIA application (riaaiagent.cc)</h4>
            <ul>
              <li><strong>Account data:</strong> company name and GSTIN; each user&rsquo;s name, email, phone number, role and password (stored only in scrambled, salted hashed form — we cannot read it).</li>
              <li><strong>Activity records:</strong> sign-ins and actions users take (for example importing a call sheet, starting or pausing a campaign, editing a ticket), with time and user. Passwords are never recorded.</li>
              <li><strong>Billing data:</strong> plan, invoices and payment records.</li>
            </ul>

            <h4>3.3 Data about retailers that distributors upload or that RIA records on calls</h4>
            <ul>
              <li><strong>Call-sheet data:</strong> business or shop name, contact person&rsquo;s name, mobile number, invoice number, invoice amount, due date, preferred language.</li>
              <li><strong>Call data:</strong> call time, duration and status; the audio recording of each answered call; a written transcript; the outcome (for example a promise to pay with date and amount, a callback time, a dispute or an &ldquo;already paid&rdquo; claim); notes; tickets and follow-ups.</li>
              <li><strong>Do-not-call status:</strong> if the person asks not to be called again.</li>
            </ul>

            <div className="privacy-callout warning">
              <strong>Security Guardrail:</strong> We do not ask for, and RIA is strictly instructed <u>never to ask for</u>, bank passwords, PINs, OTPs, or debit/credit card numbers.
            </div>
          </section>

          {/* Section 4 */}
          <section className="privacy-section">
            <h3>4. Why we use it</h3>
            <div className="privacy-table-wrap">
              <table className="privacy-table">
                <thead>
                  <tr>
                    <th>Purpose</th>
                    <th>Data used</th>
                    <th>Basis under DPDP law</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Reply to enquiry and arrange demo</td>
                    <td>Contact form, WhatsApp chats</td>
                    <td>Your consent, given when you submit the form or message us</td>
                  </tr>
                  <tr>
                    <td>Run the demo agent</td>
                    <td>Demo voice and conversation</td>
                    <td>Your consent, given when you start the demo</td>
                  </tr>
                  <tr>
                    <td>Provide the RIA application: sign-in, dashboards, reports, support</td>
                    <td>Account and activity data</td>
                    <td>Your consent, given when your account is created</td>
                  </tr>
                  <tr>
                    <td>Make collection calls for a distributor and record results</td>
                    <td>Call-sheet and call data</td>
                    <td>On the distributor&rsquo;s instructions; the distributor is responsible for its lawful basis</td>
                  </tr>
                  <tr>
                    <td>Keep the service secure, prevent misuse, keep audit records</td>
                    <td>Technical and activity data</td>
                    <td>Your consent, and our legal duty under DPDP Rules (Rule 6)</td>
                  </tr>
                  <tr>
                    <td>Billing, tax and legal duties</td>
                    <td>Account and billing data</td>
                    <td>Compliance with law (GST and statutory records)</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="privacy-callout success">
              <strong>Strict Data Commitments:</strong>
              <ul style={{ margin: '6px 0 0', paddingLeft: '18px' }}>
                <li>We <strong>do not sell</strong> personal data.</li>
                <li>We <strong>do not use one distributor&rsquo;s retailer data for any other distributor</strong>.</li>
                <li>We <strong>do not use call recordings or transcripts to train AI models</strong>, ours or anyone else&rsquo;s.</li>
                <li>We <strong>do not send marketing</strong> to retailers that RIA calls.</li>
              </ul>
            </div>
          </section>

          {/* Section 5 */}
          <section className="privacy-section">
            <h3>5. How RIA calls work</h3>
            <ul>
              <li><strong>AI Disclosure:</strong> RIA is an AI voice agent. At the start of each call it explicitly says who it is calling for, that it is an AI assistant, and that the call is recorded.</li>
              <li><strong>Identity Verification:</strong> RIA shares invoice and balance details only after the person confirms they are the customer or handle the customer&rsquo;s payments.</li>
              <li><strong>Time Windows:</strong> Calls are made only between <strong>8:00 AM and 7:00 PM IST</strong>, or within a narrower window set by the distributor.</li>
              <li><strong>Do-Not-Call (DND):</strong> Anyone can ask RIA, the distributor or us not to be called again. The number is immediately marked &ldquo;do not call&rdquo; and is not dialled again for that distributor.</li>
              <li><strong>Zero Harassment:</strong> RIA does not threaten, argue about disputed amounts, or offer unapproved discounts. Disputes and special requests are escalated directly to the distributor&rsquo;s staff as tickets.</li>
            </ul>
          </section>

          {/* Section 6 */}
          <section className="privacy-section">
            <h3>6. Who we share it with</h3>
            <p>
              We share data only with the distributor who uploaded the call sheet, authorized law enforcement authorities when required by law, and the following essential sub-processors bound by strict confidentiality and data protection contracts:
            </p>
            <div className="privacy-table-wrap">
              <table className="privacy-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>What it does for RIA</th>
                    <th>Data it handles</th>
                    <th>Location</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>OpenAI</strong></td>
                    <td>Understands what the person says and writes RIA&rsquo;s replies; speech-to-text</td>
                    <td>Call audio, transcripts, relevant invoice details</td>
                    <td>United States</td>
                  </tr>
                  <tr>
                    <td><strong>Smallest AI</strong></td>
                    <td>Turns RIA&rsquo;s replies into natural speech (TTS)</td>
                    <td>Text of RIA&rsquo;s replies; call audio when used for STT</td>
                    <td>Global / Cloud</td>
                  </tr>
                  <tr>
                    <td><strong>Vobiz</strong></td>
                    <td>Indian telecom carrier line placing and receiving calls</td>
                    <td>Phone numbers, call timestamps and durations</td>
                    <td>India</td>
                  </tr>
                  <tr>
                    <td><strong>Google Cloud</strong></td>
                    <td>Cloud infrastructure, LiveKit servers, Cloud SQL, and secure call audio storage</td>
                    <td>All platform data, including encrypted call audio</td>
                    <td>India / Global Cloud</td>
                  </tr>
                  <tr>
                    <td><strong>Cloudflare</strong></td>
                    <td>Application delivery, DDoS mitigation, web security</td>
                    <td>IP address, browser information, in-transit telemetry</td>
                    <td>Global Edge Network</td>
                  </tr>
                  <tr>
                    <td><strong>Google Workspace</strong></td>
                    <td>Transactional emails (sign-up codes and password resets)</td>
                    <td>User name and email address</td>
                    <td>Global</td>
                  </tr>
                  <tr>
                    <td><strong>WhatsApp (Meta)</strong></td>
                    <td>Receives website contact-form messages and inquiries</td>
                    <td>Name, phone, email, company, inquiry message</td>
                    <td>Global</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="privacy-subnote">
              <strong>Transfers outside India:</strong> We transfer data only to countries not restricted by the Government of India under DPDP law, and only under contracts requiring equal data protection.
            </p>
          </section>

          {/* Section 7 */}
          <section className="privacy-section">
            <h3>7. How long we keep it</h3>
            <div className="privacy-table-wrap">
              <table className="privacy-table">
                <thead>
                  <tr>
                    <th>Data Category</th>
                    <th>Retention Period</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Website enquiries and WhatsApp chats</td>
                    <td>12 months from last contact (unless you become a customer)</td>
                  </tr>
                  <tr>
                    <td>Demo conversations</td>
                    <td>Temporary session only; not retained long-term</td>
                  </tr>
                  <tr>
                    <td>Call audio recordings</td>
                    <td><strong>90 days from the call</strong>, unless a distributor sets a shorter period or a dispute needs them longer</td>
                  </tr>
                  <tr>
                    <td>Transcripts, outcomes, promises, tickets</td>
                    <td>While the distributor&rsquo;s subscription is active, and up to 90 days after it ends</td>
                  </tr>
                  <tr>
                    <td>User accounts</td>
                    <td>While the subscription is active, and up to 90 days after it ends</td>
                  </tr>
                  <tr>
                    <td>Security and activity logs</td>
                    <td>At least 1 year (DPDP Rules, Rule 6), and up to 365 days unless required longer</td>
                  </tr>
                  <tr>
                    <td>Invoices and billing records</td>
                    <td>As long as Indian tax law requires (e.g. 7 years for GST)</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="privacy-subnote">
              When a retention period ends, data is deleted or permanently anonymized. Where DPDP law requires, we will notify you at least 48 hours before deleting your data for account inactivity.
            </p>
          </section>

          {/* Section 8 */}
          <section className="privacy-section">
            <h3>8. How we protect it</h3>
            <ul>
              <li><strong>Encryption:</strong> Strong HTTPS/TLS encryption in transit and AES encryption at rest.</li>
              <li><strong>Hashed Passwords:</strong> Passwords stored strictly using one-way cryptographic hashing.</li>
              <li><strong>Tenant Isolation:</strong> Each company sees only its own data; role-based access controls (RBAC) ensure users access only what their role permits.</li>
              <li><strong>Audit Logging:</strong> Immutable activity logging tracking actions taken in the application.</li>
              <li><strong>Breach Notification:</strong> In the event of a personal data breach, we will inform affected individuals and the Data Protection Board of India without delay as required by DPDP law.</li>
            </ul>
          </section>

          {/* Section 9 */}
          <section className="privacy-section">
            <h3>9. Your rights under DPDP law</h3>
            <p>Under the DPDP Act, you have the right to:</p>
            <ul>
              <li>Ask what personal data we hold about you and how we use it;</li>
              <li>Ask us to correct, complete, update or delete your personal data;</li>
              <li>Withdraw your consent at any time (withdrawal does not affect prior lawful processing);</li>
              <li>Nominate another person to act for you in the event of death or incapacity;</li>
              <li>Make a grievance complaint to us, and escalate to the Data Protection Board of India if unresolved.</li>
            </ul>
            <p>
              To exercise these rights, email us at <a href="mailto:privacy@riaaiagent.com">privacy@riaaiagent.com</a>. We will respond within 30 days.
            </p>
          </section>

          {/* Section 10 */}
          <section className="privacy-section">
            <h3>10. Children</h3>
            <p>
              RIA is a business service intended exclusively for adults (18+). We do not knowingly collect personal data from minors. If you believe a minor has provided data, contact us and it will be deleted immediately.
            </p>
          </section>

          {/* Section 11 */}
          <section className="privacy-section">
            <h3>11. Grievance and contact</h3>
            <div className="privacy-contact-card">
              <div className="privacy-contact-row">
                <span className="label">Grievance Officer:</span>
                <span className="val">Sangamreddy Gyan Vardhan, System Architect</span>
              </div>
              <div className="privacy-contact-row">
                <span className="label">Organisation:</span>
                <span className="val">Roxy Distributors LLP, Hyderabad, Telangana</span>
              </div>
              <div className="privacy-contact-row">
                <span className="label">Email:</span>
                <span className="val"><a href="mailto:privacy@riaaiagent.com">privacy@riaaiagent.com</a></span>
              </div>
              <div className="privacy-contact-row">
                <span className="label">Phone:</span>
                <span className="val">+91 81066 68552</span>
              </div>
              <div className="privacy-contact-row">
                <span className="label">Regulatory Authority:</span>
                <span className="val">Data Protection Board of India (official portal)</span>
              </div>
            </div>
          </section>

          {/* Section 12 */}
          <section className="privacy-section">
            <h3>12. Changes to this policy</h3>
            <p>
              We will post any update with a new &ldquo;last updated&rdquo; date. If a change materially affects how your data is handled, we will notify you before the change takes effect.
            </p>
          </section>
        </div>

        {/* Footer */}
        <div className="privacy-modal-footer">
          <div className="privacy-footer-note">
            DPDP Act, 2023 Compliant · Roxy Distributors LLP
          </div>
          <div className="privacy-footer-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
            {onAccept && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={onAccept}
              >
                I Accept &amp; Continue
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
