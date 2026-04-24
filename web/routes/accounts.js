import { api, fmt } from '/web/app.js';

function relTime(isoStr) {
  if (!isoStr) return '';
  const diffMs = Date.now() - new Date(isoStr).getTime();
  const h = Math.floor(diffMs / 3_600_000);
  const m = Math.floor((diffMs % 3_600_000) / 60_000);
  if (h > 0) return `${h}h ${m}m ago`;
  if (m > 0) return `${m}m ago`;
  return 'just now';
}

function sessionBlock(sess) {
  if (!sess) {
    return `<p class="muted" style="margin:4px 0;font-size:13px">No active session in the last 24h</p>`;
  }
  const billable = (sess.input_tokens || 0) + (sess.output_tokens || 0)
    + (sess.cache_create_5m_tokens || 0) + (sess.cache_create_1h_tokens || 0);
  return `
    <div class="flex" style="align-items:baseline;gap:6px;margin:4px 0">
      <span style="font-size:22px;font-weight:600;letter-spacing:-0.02em">${fmt.compact(billable)}</span>
      <span class="muted" style="font-size:12px">tokens</span>
      <span class="spacer"></span>
      <span style="font-weight:500">${fmt.usd(sess.cost_usd)}</span>
    </div>
    <div class="muted" style="font-size:12px">
      <a href="#/sessions/${encodeURIComponent(sess.session_id)}">${relTime(sess.started_at) || 'view session'}</a>
    </div>`;
}

function weekBlock(week) {
  if (!week) return `<p class="muted" style="margin:4px 0;font-size:13px">No data</p>`;
  const billable = (week.input_tokens || 0) + (week.output_tokens || 0)
    + (week.cache_create_5m_tokens || 0) + (week.cache_create_1h_tokens || 0);
  return `
    <div class="flex" style="align-items:baseline;gap:6px;margin:4px 0">
      <span style="font-size:22px;font-weight:600;letter-spacing:-0.02em">${fmt.compact(billable)}</span>
      <span class="muted" style="font-size:12px">tokens</span>
      <span class="spacer"></span>
      <span style="font-weight:500">${fmt.usd(week.cost_usd)}</span>
    </div>
    <div class="muted" style="font-size:12px">resets Monday</div>`;
}

function accountCard(acc) {
  const body = acc.error
    ? `<p class="muted" style="font-size:13px">${fmt.htmlSafe(acc.error)}</p>`
    : `
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:4px">Current Session</div>
      ${sessionBlock(acc.current_session)}
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin:14px 0 4px">This Week</div>
      ${weekBlock(acc.this_week)}`;
  return `
    <div class="card" style="min-width:0">
      <h3 style="margin:0 0 12px;font-size:15px">${fmt.htmlSafe(acc.name)}</h3>
      ${body}
    </div>`;
}

export default async function (root) {
  let accounts;
  try {
    accounts = await api('/api/accounts/summary');
  } catch {
    root.innerHTML = `<div class="card"><p class="muted">Could not load accounts — check the console for errors.</p></div>`;
    return;
  }

  if (!accounts.length) {
    root.innerHTML = `
      <div class="card">
        <h2 style="margin:0 0 8px">Accounts</h2>
        <p class="muted">No accounts configured. Copy <code>accounts.example.json</code> to <code>accounts.json</code> in the project root and fill in your paths, then restart the dashboard.</p>
      </div>`;
    return;
  }

  root.innerHTML = `
    <div style="margin-bottom:14px">
      <h2 style="margin:0;font-size:16px;letter-spacing:-0.01em">Accounts</h2>
    </div>
    <div class="row cols-${Math.min(accounts.length, 3)}" style="align-items:start">
      ${accounts.map(accountCard).join('')}
    </div>`;
}
