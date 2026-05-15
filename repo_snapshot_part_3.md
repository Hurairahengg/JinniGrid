# Repo Snapshot — Part 3/5

- Root: `/home/hurairahengg/Documents/JinniGrid`
- Total files: `28` | This chunk: `7`
- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra.theres the whole ui with a professional protfolio and contorls such as settings and fleet management and so on yeah. currently im mostly dont and need bug fixes for many thigns so yeah. understand each code its role and keep in ur context i will give u big promtps to update code later duinerstood

## Files in Part 3

```text
ui/css/style.css
app/routes/mainRoutes.py
vm/worker_agent.py
app/services/strategy_registry.py
vm/trading/indicators.py
requirements.txt
app/routes/__init__.py
```

## Contents

---

## `ui/css/style.css`

```css
/* base.css */

*,*::before,*::after { margin:0; padding:0; box-sizing:border-box; }
html { font-size: 14px; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
  height: 100vh;
  -webkit-font-smoothing: antialiased;
}
a { text-decoration: none; color: inherit; }
button { font-family: inherit; border: none; cursor: pointer; background: none; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--scrollbar-track); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
.text-success { color: var(--success) !important; }
.text-danger  { color: var(--danger) !important; }
.text-warning { color: var(--warning) !important; }
.text-accent  { color: var(--accent) !important; }
.text-muted   { color: var(--text-muted) !important; }
.text-stale   { color: var(--stale) !important; }
.mono { font-family: 'JetBrains Mono', monospace; }

/* ── dashboard.css  ───────────────────────────────────────────────────── */
.dashboard {
  display: flex; flex-direction: column; gap: 24px;
  width: 100%; max-width: 1500px;
}

/* ── Section Header ─────────────────────────────────────────────── */

.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.section-header i { color: var(--accent); font-size: 14px; }
.section-header h2 { font-size: 14px; font-weight: 600; color: var(--text-primary); letter-spacing: 0.3px; }
.section-badge {
  margin-left: 8px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px;
  font-weight: 500; padding: 2px 8px; border-radius: 4px;
  background: var(--accent-dim); color: var(--accent);
}

/* ── Portfolio Cards Grid ───────────────────────────────────────── */

.portfolio-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  width: 100%;
}
.portfolio-card {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 14px 16px; display: flex; align-items: flex-start; gap: 12px;
  box-shadow: var(--shadow-sm); animation: fadeInUp 0.4s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
  min-width: 0;
}
.portfolio-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); background: var(--bg-card-hover); }
.portfolio-card:nth-child(1) { animation-delay: 0.02s; }
.portfolio-card:nth-child(2) { animation-delay: 0.04s; }
.portfolio-card:nth-child(3) { animation-delay: 0.06s; }
.portfolio-card:nth-child(4) { animation-delay: 0.08s; }
.portfolio-card:nth-child(5) { animation-delay: 0.10s; }
.portfolio-card:nth-child(6) { animation-delay: 0.12s; }
.portfolio-card:nth-child(7) { animation-delay: 0.14s; }
.portfolio-card:nth-child(8) { animation-delay: 0.16s; }

/* ── Card Icon ──────────────────────────────────────────────────── */

.card-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex-shrink: 0;
}
.card-icon.neutral  { background: var(--accent-dim);  color: var(--accent); }
.card-icon.positive { background: var(--success-dim); color: var(--success); }
.card-icon.negative { background: var(--danger-dim);  color: var(--danger); }
.card-icon.warning  { background: var(--warning-dim); color: var(--warning); }

/* ── Card Info ──────────────────────────────────────────────────── */

.card-info { display: flex; flex-direction: column; gap: 4px; min-width: 0; overflow: hidden; }
.card-value {
  font-family: 'JetBrains Mono', monospace; font-size: 16px;
  font-weight: 700; color: var(--text-primary); line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.card-value.positive { color: var(--success); }
.card-value.negative { color: var(--danger); }
.card-label {
  font-size: 10.5px; font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--text-muted);
  white-space: nowrap;
}

/* ── Equity Chart ───────────────────────────────────────────────── */

.chart-container {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 20px; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.4s ease 0.2s both; width: 100%;
}
.chart-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.chart-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.chart-period { font-size: 11px; color: var(--text-muted); font-weight: 500; }
.chart-wrapper { height: 280px; position: relative; }

/* ── Fleet Summary Badges ───────────────────────────────────────── */

.fleet-summary { display: flex; gap: 14px; flex-wrap: wrap; width: 100%; margin-bottom: 18px; }
.fleet-badge {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 8px; padding: 10px 16px; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.3s ease both;
}
.badge-count { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.badge-label { font-size: 11.5px; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.badge-count.total   { color: var(--text-primary); }
.badge-count.online  { color: var(--success); }
.badge-count.warning { color: var(--warning); }
.badge-count.stale   { color: var(--stale); }
.badge-count.offline { color: var(--text-muted); }
.badge-count.error   { color: var(--danger); }

/* ── Fleet Grid ─────────────────────────────────────────────────── */

.fleet-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  width: 100%;
}

/* ── Node Card ──────────────────────────────────────────────────── */

.node-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.4s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
  min-width: 0;
}
.node-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); background: var(--bg-card-hover); }
.node-card:nth-child(1) { animation-delay: 0.02s; }
.node-card:nth-child(2) { animation-delay: 0.04s; }
.node-card:nth-child(3) { animation-delay: 0.06s; }
.node-card:nth-child(4) { animation-delay: 0.08s; }
.node-card:nth-child(5) { animation-delay: 0.10s; }
.node-card:nth-child(6) { animation-delay: 0.12s; }

/* ── Node Card Top Bar ──────────────────────────────────────────── */

.node-card-top { height: 2px; }
.node-card-top.online  { background: var(--success); }
.node-card-top.running { background: var(--success); }
.node-card-top.idle    { background: var(--accent); }
.node-card-top.warning { background: var(--warning); }
.node-card-top.stale   { background: var(--stale); }
.node-card-top.offline { background: var(--text-muted); }
.node-card-top.error   { background: var(--danger); }

/* ── Node Card Header ───────────────────────────────────────────── */

.node-card-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px 10px; }
.node-name-group { display: flex; align-items: center; gap: 8px; min-width: 0; }
.node-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.node-status-dot.online  { background: var(--success); }
.node-status-dot.running { background: var(--success); }
.node-status-dot.idle    { background: var(--accent); }
.node-status-dot.warning { background: var(--warning); }
.node-status-dot.stale   { background: var(--stale); }
.node-status-dot.offline { background: var(--text-muted); }
.node-status-dot.error   { background: var(--danger); }
.node-name {
  font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
  font-weight: 500; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.node-status-badge {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; padding: 3px 8px; border-radius: 4px; flex-shrink: 0;
}
.node-status-badge.online  { background: var(--success-dim); color: var(--success); }
.node-status-badge.running { background: var(--success-dim); color: var(--success); }
.node-status-badge.idle    { background: var(--accent-dim);  color: var(--accent); }
.node-status-badge.warning { background: var(--warning-dim); color: var(--warning); }
.node-status-badge.stale   { background: var(--stale-dim);   color: var(--stale); }
.node-status-badge.offline { background: rgba(100,116,139,0.15); color: var(--text-muted); }
.node-status-badge.error   { background: var(--danger-dim);  color: var(--danger); }
.node-status-badge.unknown { background: rgba(100,116,139,0.15); color: var(--text-muted); }

/* ── Node Card Body ─────────────────────────────────────────────── */

.node-card-body { padding: 0 16px 14px; }
.node-info-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 0; border-bottom: 1px solid var(--border-subtle);
}
.node-info-row:last-child { border-bottom: none; }
.node-info-label { font-size: 11px; color: var(--text-muted); font-weight: 500; white-space: nowrap; }
.node-info-value {
  font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  color: var(--text-secondary); font-weight: 400; text-align: right;
  max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.node-info-value.strategy { color: var(--accent); font-weight: 500; }
.node-info-value.inactive { color: var(--text-muted); }

/* ── State Pills ────────────────────────────────────────────────── */

.state-pill {
  display: inline-block; font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.4px;
  padding: 2px 8px; border-radius: 4px;
}
.state-pill.online  { background: var(--success-dim); color: var(--success); }
.state-pill.running { background: var(--success-dim); color: var(--success); }
.state-pill.idle    { background: var(--accent-dim);  color: var(--accent); }
.state-pill.warning { background: var(--warning-dim); color: var(--warning); }
.state-pill.stale   { background: var(--stale-dim);   color: var(--stale); }
.state-pill.error   { background: var(--danger-dim);  color: var(--danger); }
.state-pill.offline { background: rgba(100,116,139,0.15); color: var(--text-muted); }
.state-pill.unknown { background: rgba(100,116,139,0.15); color: var(--text-muted); }

/* ── Compact Fleet Table ────────────────────────────────────────── */

.compact-fleet-wrapper {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; overflow-x: auto;
  box-shadow: var(--shadow-sm); margin-top: 12px;
}
.compact-fleet-table { width: 100%; border-collapse: separate; border-spacing: 0; }
.compact-fleet-table th {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 600; padding: 8px 12px;
  text-align: left; border-bottom: 1px solid var(--border-primary);
}
.compact-fleet-table td {
  font-size: 12px; padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary);
}
.compact-fleet-table td.mono { font-family: 'JetBrains Mono', monospace; }
.compact-fleet-table tr:hover td { background: var(--bg-card-hover); }

/* ── View Fleet Link ────────────────────────────────────────────── */

.view-fleet-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--accent); font-weight: 500;
  cursor: pointer; margin-top: 12px; transition: opacity 0.2s;
}
.view-fleet-link:hover { opacity: 0.8; }

/* ── Null Value ─────────────────────────────────────────────────── */

.value-null { color: var(--text-muted); font-style: italic; }

/* ── Dashboard Fleet Section ────────────────────────────────────── */

.dashboard-fleet-section { min-height: 120px; }

/* ── Loading State ──────────────────────────────────────────────── */

.loading-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 16px;
  animation: fadeInUp 0.4s ease both;
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-state p { font-size: 13px; color: var(--text-muted); }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty State ────────────────────────────────────────────────── */

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 14px;
  animation: fadeInUp 0.4s ease both; padding: 40px;
}
.empty-state i { font-size: 52px; color: var(--text-muted); opacity: 0.25; }
.empty-state h3 { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.empty-state p {
  font-size: 13px; color: var(--text-muted); max-width: 420px;
  text-align: center; line-height: 1.6;
}
.empty-state code {
  font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  background: var(--bg-secondary); padding: 2px 8px;
  border-radius: 4px; color: var(--accent);
}

/* ── Error State ────────────────────────────────────────────────── */

.error-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 14px;
  animation: fadeInUp 0.4s ease both; padding: 40px;
}
.error-state i { font-size: 52px; color: var(--danger); opacity: 0.4; }
.error-state h3 { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.error-state p {
  font-size: 13px; color: var(--text-muted); max-width: 420px;
  text-align: center; line-height: 1.6;
}
.retry-btn {
  padding: 8px 20px; background: var(--accent-dim); color: var(--accent);
  border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: 1px solid transparent; transition: all 0.2s ease;
}
.retry-btn:hover { background: var(--accent); color: #fff; }

/* ── Fleet Page ─────────────────────────────────────────────────── */

.fleet-page {
  display: flex; flex-direction: column; gap: 24px;
  width: 100%; max-width: 1500px;
  animation: fadeInUp 0.3s ease both;
}
.fleet-page-header {
  display: flex; align-items: center; justify-content: space-between;
}
.fleet-page-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.fleet-page-meta { display: flex; align-items: center; gap: 14px; }
.auto-refresh-badge {
  display: flex; align-items: center; gap: 6px; font-size: 11px;
  color: var(--text-muted); background: var(--bg-card);
  border: 1px solid var(--border-primary); padding: 4px 10px; border-radius: 5px;
}
.auto-refresh-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--success); animation: pulse-glow 2s ease-in-out infinite;
}
.last-synced {
  font-size: 11px; color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Placeholder Page ───────────────────────────────────────────── */

.placeholder-page {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; min-height: 400px; gap: 16px;
  animation: fadeInUp 0.4s ease both;
}
.placeholder-page i { font-size: 48px; color: var(--text-muted); opacity: 0.3; }
.placeholder-page h2 { font-size: 18px; font-weight: 600; color: var(--text-secondary); }
.placeholder-page p {
  font-size: 13px; color: var(--text-muted); max-width: 360px;
  text-align: center; line-height: 1.6;
}

/* ── Animations ─────────────────────────────────────────────────── */

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Responsive ─────────────────────────────────────────────────── */

@media (max-width: 1100px) {
  .portfolio-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fleet-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .portfolio-grid { grid-template-columns: minmax(0, 1fr); }
  .fleet-grid { grid-template-columns: minmax(0, 1fr); }
}

/* ── layout.css  ────────────────────────────────────────────────── */

body { display: flex; flex-direction: row; }

/* ── Sidebar (always dark) ──────────────────────────────────────── */

.sidebar {
  width: 240px; min-width: 240px; height: 100vh; background: #0d1117;
  display: flex; flex-direction: column; border-right: 1px solid #1e293b; z-index: 10;
}
.sidebar-brand {
  height: 60px; display: flex; align-items: center; gap: 12px;
  padding: 0 20px; border-bottom: 1px solid #1e293b;
}
.brand-mark {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, #06b6d4, #3b82f6);
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace; font-weight: 700;
  font-size: 12px; color: #fff; letter-spacing: -0.5px; flex-shrink: 0;
}
.brand-text { display: flex; flex-direction: column; line-height: 1; }
.brand-name { font-weight: 700; font-size: 13px; color: #e2e8f0; letter-spacing: 1.2px; }
.brand-sub { font-size: 10px; color: #64748b; margin-top: 3px; letter-spacing: 0.5px; }

/* ── Navigation ─────────────────────────────────────────────────── */

.sidebar-nav { flex: 1; display: flex; flex-direction: column; padding: 12px 0; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 12px; padding: 10px 20px;
  color: #94a3b8; font-size: 13px; font-weight: 500;
  border-left: 3px solid transparent; transition: all 0.2s ease;
}
.nav-item:hover { color: #e2e8f0; background: rgba(255,255,255,0.03); }
.nav-item.active { color: #06b6d4; border-left-color: #06b6d4; background: rgba(6,182,212,0.08); }
.nav-item i { width: 18px; text-align: center; font-size: 14px; }

/* ── Sidebar Footer / Theme Toggle ──────────────────────────────── */

.sidebar-footer { padding: 12px 16px; border-top: 1px solid #1e293b; }
.theme-toggle {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 8px 12px; border-radius: 6px; color: #94a3b8;
  font-size: 12px; font-weight: 500; transition: all 0.2s ease;
}
.theme-toggle:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
.theme-toggle i { width: 16px; text-align: center; font-size: 13px; }

/* ── Main Wrapper ───────────────────────────────────────────────── */

.main-wrapper {
  flex: 1; display: flex; flex-direction: column;
  height: 100vh; min-width: 0; overflow: hidden;
}

/* ── Top Bar ────────────────────────────────────────────────────── */

.topbar {
  height: 60px; min-height: 60px; background: var(--bg-topbar);
  border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between; padding: 0 28px;
}
.topbar-left { display: flex; align-items: baseline; gap: 12px; }
.topbar-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.topbar-subtitle { font-size: 11.5px; color: var(--text-muted); font-weight: 400; }
.topbar-right { display: flex; align-items: center; gap: 20px; }
.topbar-status { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); font-weight: 500; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot--online { background: var(--success); }
.status-dot--offline { background: var(--text-muted); }
.status-dot--warning { background: var(--warning); }
.status-dot--error { background: var(--danger); }
.status-dot.pulse { animation: pulse-glow 2s ease-in-out infinite; }

@keyframes pulse-glow {
  0%,100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.5); }
  50% { box-shadow: 0 0 0 6px rgba(16,185,129,0); }
}

.topbar-clock {
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
  font-weight: 500; color: var(--text-secondary); letter-spacing: 0.5px;
}

/* ── Content Area ───────────────────────────────────────────────── */

.content {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 24px 28px;
  background: var(--bg-primary);
  width: 100%;
}

/*theme.css*/

[data-theme="dark"] {
  --bg-primary: #0b0f19;
  --bg-secondary: #111827;
  --bg-card: #151c2c;
  --bg-card-hover: #1a2236;
  --bg-topbar: #0d1117;
  --border-primary: #1e293b;
  --border-subtle: #162033;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent: #06b6d4;
  --accent-dim: rgba(6, 182, 212, 0.15);
  --success: #10b981;
  --success-dim: rgba(16, 185, 129, 0.15);
  --danger: #ef4444;
  --danger-dim: rgba(239, 68, 68, 0.15);
  --warning: #f59e0b;
  --warning-dim: rgba(245, 158, 11, 0.15);
  --stale: #fb923c;
  --stale-dim: rgba(251, 146, 60, 0.15);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
  --scrollbar-track: #0b0f19;
  --scrollbar-thumb: #1e293b;
  --scrollbar-thumb-hover: #334155;
}
[data-theme="light"] {
  --bg-primary: #f0f4f8;
  --bg-secondary: #e2e8f0;
  --bg-card: #ffffff;
  --bg-card-hover: #f8fafc;
  --bg-topbar: #ffffff;
  --border-primary: #e2e8f0;
  --border-subtle: #f1f5f9;
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --accent: #0891b2;
  --accent-dim: rgba(8, 145, 178, 0.12);
  --success: #059669;
  --success-dim: rgba(5, 150, 105, 0.12);
  --danger: #dc2626;
  --danger-dim: rgba(220, 38, 38, 0.12);
  --warning: #d97706;
  --warning-dim: rgba(217, 119, 6, 0.12);
  --stale: #ea580c;
  --stale-dim: rgba(234, 88, 12, 0.12);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.1);
  --scrollbar-track: #f0f4f8;
  --scrollbar-thumb: #cbd5e1;
  --scrollbar-thumb-hover: #94a3b8;
}
body,.topbar,.content,.portfolio-card,.node-card,.section-header,.fleet-summary,
.chart-container,.fleet-page,.loading-state,.empty-state,.error-state,.compact-fleet-wrapper,
.fleet-badge {
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

/* worker-detail.css*/


/* ── Clickable Fleet Enhancement ──────────────────────────── */
.node-card.clickable { cursor: pointer; }
.node-card.clickable:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-dim), var(--shadow-md); }
.node-card-action {
  display: flex; align-items: center; gap: 6px; margin-top: 8px; padding-top: 8px;
  border-top: 1px solid var(--border-subtle); font-size: 11px; color: var(--accent);
  font-weight: 500;
}
.compact-fleet-table tr.clickable { cursor: pointer; }
.compact-fleet-table tr.clickable:hover td { background: var(--bg-card-hover); }

/* ── Worker Detail Page ───────────────────────────────────── */
.worker-detail { display: flex; flex-direction: column; gap: 24px; max-width: 1400px; animation: fadeInUp 0.3s ease both; }

.wd-header {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 20px; display: flex; align-items: center; justify-content: space-between;
  box-shadow: var(--shadow-sm);
}
.wd-header-left { display: flex; align-items: center; gap: 16px; }
.wd-back-btn {
  padding: 8px 14px; background: var(--bg-secondary); border: 1px solid var(--border-primary);
  border-radius: 6px; color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 6px;
}
.wd-back-btn:hover { color: var(--accent); border-color: var(--accent); }
.wd-header-info { display: flex; flex-direction: column; gap: 4px; }
.wd-header-info h2 { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.wd-header-meta {
  display: flex; align-items: center; gap: 8px; font-size: 11.5px;
  color: var(--text-muted); font-family: 'JetBrains Mono', monospace;
}
.meta-sep { opacity: 0.4; }
.wd-header-right { display: flex; align-items: center; gap: 12px; }
.wd-refresh-btn {
  padding: 8px 14px; background: var(--bg-secondary); border: 1px solid var(--border-primary);
  border-radius: 6px; color: var(--text-secondary); font-size: 11px; font-weight: 500;
  cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.wd-refresh-btn:hover { color: var(--accent); border-color: var(--accent); }
.wd-emergency-btn {
  padding: 8px 16px; background: var(--danger-dim); color: var(--danger);
  border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; border: 1px solid transparent; cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.wd-emergency-btn:hover { background: var(--danger); color: #fff; }

/* ── Status Cards Grid ────────────────────────────────────── */
.wd-status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.wd-status-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 6px;
  box-shadow: var(--shadow-sm);
}
.wd-status-card .status-label {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 500;
}
.wd-status-card .status-value {
  font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 600;
  color: var(--text-primary);
}
.status-indicator { display: flex; align-items: center; gap: 6px; }
.wd-status-dot-sm {
  width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0;
}
.wd-status-dot-sm.green { background: var(--success); }
.wd-status-dot-sm.amber { background: var(--warning); }
.wd-status-dot-sm.orange { background: var(--stale); }
.wd-status-dot-sm.red { background: var(--danger); }
.wd-status-dot-sm.blue { background: var(--accent); }
.wd-status-dot-sm.gray { background: var(--text-muted); }

/* ── Content Layout ───────────────────────────────────────── */
.wd-content { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
.wd-main-col { display: flex; flex-direction: column; gap: 20px; }
.wd-side-col { display: flex; flex-direction: column; gap: 20px; }

/* ── Panel ────────────────────────────────────────────────── */
.wd-panel {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm);
}
.wd-panel-header {
  font-size: 13px; font-weight: 600; color: var(--text-primary);
  padding: 16px 20px; border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between;
}
.panel-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 500;
  padding: 2px 8px; border-radius: 4px; background: var(--accent-dim); color: var(--accent);
}
.panel-badge.mock {
  background: var(--warning-dim); color: var(--warning);
}
.wd-panel-body { padding: 20px; }

/* ── File Upload ──────────────────────────────────────────── */
.wd-file-upload {
  border: 2px dashed var(--border-primary); border-radius: 8px; padding: 32px;
  text-align: center; transition: all 0.2s; cursor: pointer;
}
.wd-file-upload:hover { border-color: var(--accent); }
.wd-file-upload.has-file { border-color: var(--success); border-style: solid; }
.wd-file-upload i { font-size: 32px; color: var(--text-muted); opacity: 0.4; }
.wd-file-upload h4 { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-top: 10px; }
.wd-file-upload p { font-size: 11.5px; color: var(--text-muted); margin-top: 4px; }
.file-name {
  font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent);
  font-weight: 500; margin-top: 8px;
}
.wd-file-status {
  display: flex; align-items: center; gap: 6px; justify-content: center;
  margin-top: 8px; font-size: 11px;
}

/* ── Metadata Preview ─────────────────────────────────────── */
.wd-metadata {
  margin-top: 16px; background: var(--bg-secondary); border-radius: 8px;
  padding: 16px; animation: fadeInUp 0.3s ease both;
}
.wd-metadata-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.wd-metadata-item { display: flex; flex-direction: column; gap: 2px; }
.wd-metadata-label {
  font-size: 10px; text-transform: uppercase; color: var(--text-muted);
  font-weight: 500; letter-spacing: 0.4px;
}
.wd-metadata-value {
  font-size: 12px; color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Form Controls ────────────────────────────────────────── */
.wd-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.wd-form-group { display: flex; flex-direction: column; gap: 5px; }
.wd-form-label {
  font-size: 11px; color: var(--text-muted); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.4px;
}
.wd-form-input, .wd-form-select {
  width: 100%; padding: 8px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-primary); border-radius: 6px;
  color: var(--text-primary); font-size: 12px; font-family: 'JetBrains Mono', monospace;
  outline: none; transition: border-color 0.2s;
}
.wd-form-input:focus, .wd-form-select:focus { border-color: var(--accent); }
.wd-form-select { cursor: pointer; }

/* ── Toggle Switch ────────────────────────────────────────── */
.wd-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle);
}
.wd-toggle-row:last-child { border-bottom: none; }
.wd-toggle-label { display: flex; flex-direction: column; gap: 2px; }
.wd-toggle-label span:first-child { font-size: 12px; color: var(--text-primary); font-weight: 500; }
.wd-toggle-label span:last-child { font-size: 10.5px; color: var(--text-muted); }
.wd-toggle {
  position: relative; width: 40px; height: 22px; -webkit-appearance: none;
  appearance: none; background: var(--border-primary); border-radius: 11px;
  cursor: pointer; transition: background 0.2s; flex-shrink: 0; border: none;
}
.wd-toggle:checked { background: var(--accent); }
.wd-toggle::after {
  content: ''; position: absolute; width: 18px; height: 18px; border-radius: 50%;
  background: var(--text-primary); top: 2px; left: 2px; transition: transform 0.2s;
}
.wd-toggle:checked::after { transform: translateX(18px); }

/* ── Parameters Editor ────────────────────────────────────── */
.wd-params-list { display: flex; flex-direction: column; }
.wd-param-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle); gap: 12px;
}
.wd-param-row:last-child { border-bottom: none; }
.wd-param-row.modified { border-left: 3px solid var(--accent); padding-left: 12px; margin-left: -4px; }
.wd-param-info { flex: 1; min-width: 0; }
.wd-param-name { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.wd-param-desc { font-size: 10.5px; color: var(--text-muted); margin-top: 2px; }
.wd-param-type-badge {
  display: inline-block; font-size: 9px; font-weight: 600; text-transform: uppercase;
  padding: 1px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}
.type-int { background: var(--accent-dim); color: var(--accent); }
.type-float { background: var(--warning-dim); color: var(--warning); }
.type-bool { background: var(--success-dim); color: var(--success); }
.type-string { background: var(--stale-dim); color: var(--stale); }
.wd-param-controls { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.wd-param-input {
  width: 100px; padding: 6px 10px; background: var(--bg-secondary);
  border: 1px solid var(--border-primary); border-radius: 6px;
  color: var(--text-primary); font-size: 11.5px; font-family: 'JetBrains Mono', monospace;
  outline: none; transition: border-color 0.2s; text-align: right;
}
.wd-param-input:focus { border-color: var(--accent); }
.wd-param-reset {
  width: 24px; height: 24px; border-radius: 50%; background: transparent;
  border: none; color: var(--text-muted); font-size: 11px; cursor: pointer;
  opacity: 0.5; transition: all 0.2s; display: flex; align-items: center; justify-content: center;
}
.wd-param-reset:hover { opacity: 1; color: var(--accent); }

/* ── Checklist ────────────────────────────────────────────── */
.wd-checklist { display: flex; flex-direction: column; }
.wd-check-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.wd-check-item:last-child { border-bottom: none; }
.wd-check-icon {
  width: 18px; height: 18px; border-radius: 4px; display: flex;
  align-items: center; justify-content: center; font-size: 10px; flex-shrink: 0;
}
.wd-check-icon.pass { background: var(--success-dim); color: var(--success); }
.wd-check-icon.fail { background: var(--danger-dim); color: var(--danger); }
.wd-check-icon.warn { background: var(--warning-dim); color: var(--warning); }
.wd-check-icon.info { background: var(--accent-dim); color: var(--accent); }
.wd-check-text { font-size: 12px; color: var(--text-secondary); }
.wd-check-text.pass { color: var(--text-primary); }
.wd-check-text.dimmed { color: var(--text-muted); font-style: italic; }

/* ── Deploy Action Bar ────────────────────────────────────── */
.wd-action-bar {
  padding: 16px 20px; display: flex; align-items: center;
  justify-content: space-between; border-top: 1px solid var(--border-primary);
}
.wd-action-bar-left, .wd-action-bar-right { display: flex; gap: 10px; }
.wd-btn {
  padding: 8px 18px; border-radius: 6px; font-size: 12px; font-weight: 500;
  border: 1px solid transparent; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 6px;
}
.wd-btn-ghost { background: transparent; border-color: var(--border-primary); color: var(--text-secondary); }
.wd-btn-ghost:hover { color: var(--text-primary); border-color: var(--text-muted); }
.wd-btn-outline { background: transparent; border-color: var(--accent); color: var(--accent); }
.wd-btn-outline:hover { background: var(--accent); color: #fff; }
.wd-btn-primary { background: var(--accent); color: #fff; font-weight: 600; }
.wd-btn-primary:hover { filter: brightness(1.1); }
.wd-btn-primary.deploy {
  background: linear-gradient(135deg, #06b6d4, #3b82f6); box-shadow: var(--shadow-md);
}
.wd-btn-primary.deploy:hover { box-shadow: var(--shadow-lg); transform: translateY(-1px); }

/* ── Activity Timeline ────────────────────────────────────── */
.wd-timeline { display: flex; flex-direction: column; }
.wd-timeline-item {
  display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-subtle);
}
.wd-timeline-item:last-child { border-bottom: none; }
.wd-timeline-time {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted);
  width: 60px; flex-shrink: 0;
}
.wd-timeline-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
  flex-shrink: 0; margin-top: 5px;
}
.wd-timeline-text { font-size: 11.5px; color: var(--text-secondary); }

/* ── Modal ────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  animation: modal-fade-in 0.2s ease;
}
.modal-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 12px; width: 480px; max-width: 90vw; box-shadow: var(--shadow-lg);
  animation: modal-slide-in 0.3s ease;
}
.modal-header {
  padding: 20px 24px; border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between;
}
.modal-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.modal-close { font-size: 18px; cursor: pointer; color: var(--text-muted); transition: color 0.2s; background: none; border: none; }
.modal-close:hover { color: var(--text-primary); }
.modal-body { padding: 20px 24px; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.modal-footer {
  padding: 16px 24px; border-top: 1px solid var(--border-primary);
  display: flex; justify-content: flex-end; gap: 10px;
}
.modal-summary {
  background: var(--bg-secondary); border-radius: 8px; padding: 14px; margin-top: 12px;
}
.modal-summary-row { display: flex; justify-content: space-between; padding: 4px 0; }
.modal-summary-label { font-size: 11.5px; color: var(--text-muted); }
.modal-summary-value { font-size: 12px; font-family: 'JetBrains Mono', monospace; color: var(--text-primary); }
.modal-warning {
  background: var(--warning-dim); border-radius: 6px; padding: 10px 14px;
  margin-top: 12px; font-size: 11.5px; color: var(--warning);
  display: flex; gap: 8px; align-items: flex-start; line-height: 1.5;
}

@keyframes modal-fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes modal-slide-in {
  from { opacity: 0; transform: translateY(-10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── Toast ─────────────────────────────────────────────────── */
.toast-container {
  position: fixed; top: 20px; right: 20px; z-index: 1100;
  display: flex; flex-direction: column; gap: 8px;
}
.toast {
  padding: 12px 18px; border-radius: 8px; box-shadow: var(--shadow-md);
  display: flex; align-items: center; gap: 10px; font-size: 12.5px; font-weight: 500;
  animation: toast-in 0.3s ease; min-width: 300px; max-width: 420px;
}
.toast-success { background: var(--success-dim); border: 1px solid rgba(16,185,129,0.2); color: var(--success); }
.toast-info { background: var(--accent-dim); border: 1px solid rgba(6,182,212,0.2); color: var(--accent); }
.toast-warning { background: var(--warning-dim); border: 1px solid rgba(245,158,11,0.2); color: var(--warning); }
.toast-error { background: var(--danger-dim); border: 1px solid rgba(239,68,68,0.2); color: var(--danger); }
.toast i { font-size: 14px; flex-shrink: 0; }
.toast-dismiss {
  margin-left: auto; cursor: pointer; opacity: 0.6; font-size: 14px;
  background: none; border: none; color: inherit;
}
.toast-dismiss:hover { opacity: 1; }

@keyframes toast-in { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 1200px) {
  .wd-content { grid-template-columns: 1fr; }
  .wd-status-grid { grid-template-columns: repeat(2, 1fr); }
  .wd-form-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .wd-status-grid { grid-template-columns: 1fr; }
}

/* ── Symbol Input + Inline Lookback ───────────────────────── */
.wd-inline-row {
  display: flex; gap: 8px; align-items: center;
}
.wd-inline-row .wd-form-input { flex: 1; min-width: 0; }
.wd-inline-row .wd-form-select { flex: 0 0 130px; }
.wd-field-error {
  font-size: 10.5px; color: var(--danger); margin-top: 4px;
  display: none; align-items: center; gap: 4px;
}
.wd-field-error.visible { display: flex; }
.wd-field-error i { font-size: 10px; }
.wd-form-input.input-error { border-color: var(--danger); }
.wd-symbol-hint {
  font-size: 10px; color: var(--text-muted); margin-top: 3px;
  font-style: italic;
}

/* ══════════════════════════════════════════════════════════════
   JINNI GRID — Pro Dashboard Additions
   ══════════════════════════════════════════════════════════════ */

/* ── Card Sub-label ───────────────────────────────────────── */
.card-sub { font-size: 10px; color: var(--text-muted); margin-top: 1px; }

/* ── Dashboard Layout Grids ───────────────────────────────── */
.dash-split-row { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
.dash-chart-section { min-width: 0; }
.dash-stats-section { min-width: 0; }
.dash-triple-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
.dash-dual-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

/* ── Dashboard Stats Grid ─────────────────────────────────── */
.dash-stats-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; box-shadow: var(--shadow-sm);
}
.dash-stat-item {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 8px 4px; border-radius: 6px; background: var(--bg-secondary);
}
.dash-stat-val {
  font-family: 'JetBrains Mono', monospace; font-size: 14px;
  font-weight: 700; color: var(--text-primary);
}
.dash-stat-val.positive { color: var(--success); }
.dash-stat-val.negative { color: var(--danger); }
.dash-stat-lbl {
  font-size: 9.5px; font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.5px; color: var(--text-muted); text-align: center;
}

/* ── Dashboard Panel Body ─────────────────────────────────── */
.dash-panel-body {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; box-shadow: var(--shadow-sm); min-height: 120px;
}

/* ── Pipeline Flow ────────────────────────────────────────── */
.pipeline-flow {
  display: flex; align-items: stretch; gap: 8px; padding: 8px 0;
}
.pipeline-node {
  flex: 1 1 0; min-width: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; background: var(--bg-secondary); border-radius: 8px; padding: 14px 8px;
}
.pipeline-val { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.pipeline-val.accent { color: var(--accent); }
.pipeline-val.warning { color: var(--warning); }
.pipeline-val.success { color: var(--success); }
.pipeline-val.danger { color: var(--danger); }
.pipeline-lbl {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 500;
}
.pipeline-arrow { flex: 0 0 auto; display: flex; align-items: center; color: var(--text-muted); font-size: 10px; opacity: 0.3; }

/* ── Metric Pill (stat card inside panels) ────────────────── */
.metric-pill {
  background: var(--bg-secondary); border-radius: 8px; padding: 10px 8px;
  text-align: center; min-width: 0;
  transition: background-color 0.3s ease;
}
.metric-pill-value {
  font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 700;
  line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.metric-pill-label {
  font-size: 9.5px; color: var(--text-muted); margin-top: 4px;
  text-transform: uppercase; letter-spacing: 0.3px; white-space: nowrap;
}

/* ── Dashboard Panel (unified card style) ─────────────────── */
.dash-panel {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px 20px; box-shadow: var(--shadow-sm);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

/* ── Remove double-card when tables are inside panels ─────── */
.dash-panel-body .compact-fleet-wrapper,
.dash-panel .compact-fleet-wrapper {
  background: transparent; border: none; box-shadow: none; padding: 0; margin-top: 8px;
  border-radius: 0;
}

/* ── Section alignment (equal heights in grid rows) ───────── */
.dash-triple-row > section,
.dash-dual-row > section {
  display: flex; flex-direction: column;
}
.dash-triple-row > section > .dash-panel-body,
.dash-dual-row > section > .dash-panel-body {
  flex: 1;
}

/* ── Strategy Row (Dashboard) ─────────────────────────────── */
.dash-strat-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: var(--bg-secondary); border-radius: 6px;
}
.dash-strat-info { display: flex; align-items: center; gap: 8px; }
.dash-strat-meta { font-size: 10px; color: var(--text-muted); }
.dash-strat-badges { display: flex; align-items: center; gap: 8px; }

/* ── Portfolio Tabs ───────────────────────────────────────── */
.port-tabs {
  display: flex; gap: 4px; background: var(--bg-card);
  border: 1px solid var(--border-primary); border-radius: 8px;
  padding: 4px; width: fit-content;
}
.port-tab {
  padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500;
  color: var(--text-muted); cursor: pointer; transition: all 0.2s;
  border: none; background: none;
}
.port-tab:hover { color: var(--text-primary); }
.port-tab.active { background: var(--accent); color: #fff; font-weight: 600; }

/* ── Portfolio Filters ────────────────────────────────────── */
.port-filters { display: flex; gap: 14px; flex-wrap: wrap; }
.port-filters .wd-form-group { min-width: 160px; }

/* ── Logs ─────────────────────────────────────────────────── */
.log-filters { display: flex; gap: 14px; flex-wrap: wrap; }
.log-filters .wd-form-group { min-width: 140px; }
.log-auto-label {
  display: flex; align-items: center; gap: 6px; font-size: 11px;
  color: var(--text-muted); cursor: pointer; user-select: none;
}
.log-auto-label input { accent-color: var(--accent); }
.log-count {
  font-size: 11px; color: var(--text-muted); margin-bottom: 8px;
  font-family: 'JetBrains Mono', monospace;
}
.log-table tr.log-row { transition: background 0.15s; }
.log-table tr.log-row.clickable { cursor: pointer; }
.log-table tr.log-row.clickable:hover td { background: var(--bg-card-hover); }
.log-detail-row td { padding: 0 !important; }
.log-payload {
  font-family: 'JetBrains Mono', monospace; font-size: 10.5px;
  color: var(--text-secondary); background: var(--bg-secondary);
  padding: 12px 16px; margin: 4px 12px 8px; border-radius: 6px;
  white-space: pre-wrap; word-break: break-all; max-height: 300px;
  overflow-y: auto; border: 1px solid var(--border-primary);
}

/* ── Responsive additions ─────────────────────────────────── */
@media (max-width: 1200px) {
  .dash-split-row { grid-template-columns: 1fr; }
  .dash-triple-row { grid-template-columns: 1fr; }
  .dash-dual-row { grid-template-columns: 1fr; }
  .dash-stats-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 768px) {
  .dash-stats-grid { grid-template-columns: repeat(2, 1fr); }
  .port-tabs { flex-wrap: wrap; }
  .port-filters { flex-direction: column; }
  .log-filters { flex-direction: column; }
}

/* ══════════════════════════════════════════════════════════════
   VALIDATION MODULE STYLES
   ══════════════════════════════════════════════════════════════ */

/* Progress bar in table */
.val-progress-bar {
  width: 60px; height: 4px; background: var(--border-primary);
  border-radius: 2px; overflow: hidden; display: inline-block;
}
.val-progress-fill {
  height: 100%; background: var(--accent); transition: width 0.3s ease;
  border-radius: 2px;
}
```

---

## `app/routes/mainRoutes.py`

```python
"""
JINNI Grid — Combined API Routes
app/routes/mainRoutes.py
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Query
from pydantic import BaseModel

from app.config import Config
from app.persistence import log_event_db, save_trade_db

from app.services.mainServices import (
    process_heartbeat,
    get_all_workers,
    get_fleet_summary,
    get_system_settings,
    save_system_settings,
    admin_get_stats,
    admin_delete_strategy,
    admin_reset_portfolio,
    admin_clear_trades,
    admin_remove_worker,
    admin_remove_stale_workers,
    admin_clear_events,
    admin_full_reset,
    emergency_stop_all,
    get_portfolio_summary,
    get_equity_history,
    get_portfolio_trades,
    get_portfolio_performance,
    get_events_list,
    create_deployment,
    get_all_deployments,
    get_deployment,
    update_deployment_state,
    stop_deployment,
    enqueue_command,
    poll_commands,
    ack_command,
)

from app.services.strategy_registry import (
    upload_strategy,
    get_all_strategies,
    get_strategy,
    get_strategy_file_content,
    validate_strategy,
)


router = APIRouter()


# =============================================================================
# Health
# =============================================================================

@router.get("/api/health", tags=["Health"])
async def health_check():
    app_config = Config.get_app_config()
    return {
        "status": "ok",
        "service": app_config["name"],
        "version": app_config["version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Worker Heartbeat + Fleet
# =============================================================================

class HeartbeatPayload(BaseModel):
    worker_id: str
    worker_name: Optional[str] = None
    host: Optional[str] = None
    state: Optional[str] = "online"
    agent_version: Optional[str] = None
    mt5_state: Optional[str] = None
    account_id: Optional[str] = None
    broker: Optional[str] = None
    mt5_server: Optional[str] = None
    active_strategies: Optional[List[str]] = None
    open_positions_count: Optional[int] = 0
    floating_pnl: Optional[float] = None
    account_balance: Optional[float] = None
    account_equity: Optional[float] = None
    errors: Optional[List[str]] = None
    total_ticks: Optional[int] = 0
    total_bars: Optional[int] = 0
    current_bars_in_memory: Optional[int] = 0
    on_bar_calls: Optional[int] = 0
    signal_count: Optional[int] = 0
    last_bar_time: Optional[str] = None
    current_price: Optional[float] = None


@router.post("/api/Grid/workers/heartbeat", tags=["Grid"])
@router.post("/api/grid/workers/heartbeat", tags=["Grid"])
async def worker_heartbeat(payload: HeartbeatPayload):
    if not payload.worker_id or not payload.worker_id.strip():
        raise HTTPException(
            status_code=422,
            detail={"ok": False, "error": "worker_id is required"},
        )
    return process_heartbeat(payload.model_dump())


@router.get("/api/Grid/workers", tags=["Grid"])
@router.get("/api/grid/workers", tags=["Grid"])
async def list_workers():
    return {
        "ok": True,
        "workers": get_all_workers(),
        "summary": get_fleet_summary(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Portfolio (filtered — strategy_id, worker_id, symbol)
# =============================================================================

@router.get("/api/portfolio/summary", tags=["Portfolio"])
async def portfolio_summary(
    strategy_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
):
    portfolio = get_portfolio_summary(
        strategy_id=strategy_id, worker_id=worker_id, symbol=symbol
    )
    return {
        "portfolio": portfolio,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/equity-history", tags=["Portfolio"])
async def equity_history():
    history = get_equity_history()
    return {
        "equity_history": history,
        "points": len(history),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/trades", tags=["Portfolio"])
async def portfolio_trades(
    strategy_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(500),
):
    trades = get_portfolio_trades(
        strategy_id=strategy_id, worker_id=worker_id,
        symbol=symbol, limit=limit,
    )
    return {
        "ok": True,
        "trades": trades,
        "count": len(trades),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/performance", tags=["Portfolio"])
async def portfolio_performance(
    strategy_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
):
    perf = get_portfolio_performance(
        strategy_id=strategy_id, worker_id=worker_id, symbol=symbol
    )
    return {
        "ok": True,
        "performance": perf,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@router.post("/api/worker/error", tags=["Worker Commands"])
async def worker_error_report(payload: dict = Body(...)):
    """Receive error reports from workers. Logs as event visible in UI."""
    severity = payload.get("severity", "ERROR")
    message = payload.get("message", "Unknown error")
    worker_id = payload.get("worker_id")
    strategy_id = payload.get("strategy_id")
    deployment_id = payload.get("deployment_id")
    symbol = payload.get("symbol")

    level = "ERROR"
    if severity == "CRITICAL":
        level = "ERROR"  # highest level in our event system

    log_event_db(
        category="execution",
        event_type="worker_error",
        message=f"[{severity}] {message}",
        worker_id=worker_id,
        strategy_id=strategy_id,
        deployment_id=deployment_id,
        symbol=symbol,
        data=payload,
        level=level,
    )

    import logging
    logging.getLogger("jinni.worker").error(
        f"[WORKER-ERROR] [{severity}] worker={worker_id} "
        f"dep={deployment_id}: {message}"
    )

    return {"ok": True, "received": True}

@router.post("/api/portfolio/trades/report", tags=["Portfolio"])
async def report_trade(payload: dict = Body(...)):
    """Receive trade report from worker VM. Saves immediately to DB."""
    import logging
    _log = logging.getLogger("jinni.trades")

    mt5_ticket = payload.get("mt5_ticket") or payload.get("ticket")
    is_mt5 = payload.get("mt5_source", False)
    net_pnl = payload.get("net_pnl") or payload.get("profit", 0)
    reason = payload.get("exit_reason", "UNKNOWN")

    _log.info(
        f"[TRADE-IN] {'MT5' if is_mt5 else 'EST'} | "
        f"ticket={mt5_ticket} "
        f"{payload.get('direction', '?')} {payload.get('symbol', '?')} "
        f"pnl={net_pnl} reason={reason} "
        f"worker={payload.get('worker_id', '?')} "
        f"dep={payload.get('deployment_id', '?')}"
    )

    ok = save_trade_db(payload)

    if ok:
        log_event_db(
            "execution", "trade_closed",
            f"{'[MT5]' if is_mt5 else '[EST]'} "
            f"{payload.get('direction', '?')} {payload.get('symbol', '?')} "
            f"ticket={mt5_ticket} pnl={net_pnl} reason={reason}",
            worker_id=payload.get("worker_id"),
            strategy_id=payload.get("strategy_id"),
            deployment_id=payload.get("deployment_id"),
            symbol=payload.get("symbol"),
            data={
                "mt5_ticket": mt5_ticket,
                "profit": payload.get("profit"),
                "commission": payload.get("commission"),
                "swap": payload.get("swap"),
                "net_pnl": net_pnl,
                "exit_reason": reason,
                "mt5_source": is_mt5,
            },
            level="INFO",
        )
    else:
        _log.warning(f"[TRADE-IN] SAVE FAILED for ticket={mt5_ticket}")

    return {"ok": ok, "timestamp": datetime.now(timezone.utc).isoformat()}

# =============================================================================
# Events / Logs
# =============================================================================

@router.get("/api/events", tags=["Events"])
async def get_events(
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    deployment_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200),
):
    events = get_events_list(
        category=category, level=level, worker_id=worker_id,
        deployment_id=deployment_id, search=search, limit=limit,
    )
    return {
        "ok": True,
        "events": events,
        "count": len(events),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Strategies
# =============================================================================

@router.post("/api/grid/strategies/upload", tags=["Strategies"])
async def upload_strategy_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files accepted.")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8.")
    result = upload_strategy(file.filename, text)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/api/grid/strategies", tags=["Strategies"])
async def list_strategies():
    strategies = get_all_strategies()
    for s in strategies:
        s['is_valid'] = bool(s.get('class_name'))
        s['validation_status'] = 'validated' if s['is_valid'] else 'invalid'
    return {
        "ok": True,
        "strategies": strategies,
        "count": len(strategies),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/strategies/{strategy_id}", tags=["Strategies"])
async def get_strategy_detail(strategy_id: str):
    import json as _json
    rec = get_strategy(strategy_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Strategy not found.")

    # Parameters are stored as parameters_json in DB
    params = {}
    raw = rec.get("parameters_json") or rec.get("parameters") or "{}"
    if isinstance(raw, str):
        try:
            params = _json.loads(raw)
        except Exception:
            params = {}
    elif isinstance(raw, dict):
        params = raw

    rec["parameters"] = params
    rec["parameter_count"] = len(params)
    rec["strategy_name"] = rec.get("name", rec.get("strategy_id", ""))
    rec["is_valid"] = bool(rec.get("class_name"))
    rec["validation_status"] = "validated" if rec["is_valid"] else "invalid"
    return {"ok": True, "strategy": rec}


@router.get("/api/grid/strategies/{strategy_id}/file", tags=["Strategies"])
async def get_strategy_file(strategy_id: str):
    content = get_strategy_file_content(strategy_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Strategy file not found.")
    return {"ok": True, "strategy_id": strategy_id, "file_content": content}


@router.post("/api/grid/strategies/{strategy_id}/validate", tags=["Strategies"])
async def validate_strategy_endpoint(strategy_id: str):
    result = validate_strategy(strategy_id)
    if not result["ok"]:
        return {
            "ok": False,
            "strategy_id": strategy_id,
            "valid": False,
            "error": result.get("error", "Unknown validation error"),
        }
    return result


# =============================================================================
# Deployments
# =============================================================================

class DeploymentCreate(BaseModel):
    strategy_id: str
    worker_id: str
    symbol: str
    tick_lookback_value: Optional[int] = 30
    tick_lookback_unit: Optional[str] = "minutes"
    bar_size_points: float
    max_bars_in_memory: Optional[int] = 500
    lot_size: Optional[float] = 0.01
    strategy_parameters: Optional[Dict[str, Any]] = None


@router.post("/api/grid/deployments", tags=["Deployments"])
async def create_deployment_endpoint(payload: DeploymentCreate):
    strat = get_strategy(payload.strategy_id)
    if not strat:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found. Upload it first.",
        )
    result = create_deployment(payload.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result)

    deployment = result["deployment"]
    file_content = get_strategy_file_content(payload.strategy_id)

    # Build command payload for worker
    cmd_payload = {
        "deployment_id": deployment["deployment_id"],
        "strategy_id": deployment["strategy_id"],
        "strategy_file_content": file_content,
        "strategy_class_name": strat.get("class_name"),
        "symbol": deployment["symbol"],
        "tick_lookback_value": deployment["tick_lookback_value"],
        "tick_lookback_unit": deployment["tick_lookback_unit"],
        "bar_size_points": deployment["bar_size_points"],
        "max_bars_in_memory": deployment["max_bars_in_memory"],
        "lot_size": deployment["lot_size"],
        "strategy_parameters": deployment.get("strategy_parameters") or {},
    }
    enqueue_command(payload.worker_id, "deploy_strategy", cmd_payload)
    update_deployment_state(deployment["deployment_id"], "sent_to_worker")

    return {
        "ok": True,
        "deployment_id": deployment["deployment_id"],
        "deployment": deployment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/deployments", tags=["Deployments"])
async def list_deployments():
    deployments = get_all_deployments()
    # Enrich with strategy names for UI display
    try:
        strat_list = get_all_strategies()
        strat_map = {s["strategy_id"]: s for s in strat_list}
        for d in deployments:
            sid = d.get("strategy_id", "")
            strat = strat_map.get(sid, {})
            d["strategy_name"] = strat.get("name", sid)
            d["strategy_version"] = strat.get("version", "")
    except Exception:
        pass  # Don't break listing if enrichment fails
    return {
        "ok": True,
        "deployments": deployments,
        "count": len(deployments),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/deployments/{deployment_id}", tags=["Deployments"])
async def get_deployment_detail(deployment_id: str):
    rec = get_deployment(deployment_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return {"ok": True, "deployment": rec}


@router.post("/api/grid/deployments/{deployment_id}/stop", tags=["Deployments"])
async def stop_deployment_endpoint(deployment_id: str):
    dep = get_deployment(deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if dep.get("state") in ("stopped", "failed"):
        return {
            "ok": True,
            "deployment": dep,
            "message": "Already stopped/failed.",
        }
    enqueue_command(
        dep["worker_id"], "stop_strategy",
        {"deployment_id": deployment_id},
    )
    result = stop_deployment(deployment_id)
    return result


# =============================================================================
# Worker Commands (poll / ack)
# =============================================================================

@router.get("/api/grid/workers/{worker_id}/commands/poll",
            tags=["Worker Commands"])
async def poll_worker_commands(worker_id: str):
    commands = poll_commands(worker_id)
    return {
        "ok": True,
        "worker_id": worker_id,
        "commands": commands,
        "count": len(commands),
    }


class CommandAck(BaseModel):
    command_id: str


@router.post("/api/grid/workers/{worker_id}/commands/ack",
             tags=["Worker Commands"])
async def ack_worker_command(worker_id: str, payload: CommandAck):
    result = ack_command(worker_id, payload.command_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result)
    return result


# =============================================================================
# Runner Status (worker → mother deployment state sync)
# =============================================================================

class RunnerStatusReport(BaseModel):
    deployment_id: str
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    symbol: Optional[str] = None
    runner_state: str
    bar_size_points: Optional[float] = None
    max_bars_in_memory: Optional[int] = None
    current_bars_count: Optional[int] = 0
    last_signal: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.post("/api/grid/workers/{worker_id}/runner-status",
             tags=["Worker Commands"])
async def report_runner_status(worker_id: str,
                                payload: RunnerStatusReport):
    state_map = {
        "loading_strategy": "loading_strategy",
        "fetching_ticks": "fetching_ticks",
        "generating_initial_bars": "generating_initial_bars",
        "warming_up": "warming_up",
        "running": "running",
        "stopped": "stopped",
        "failed": "failed",
        "idle": "stopped",
    }
    dep_state = state_map.get(payload.runner_state)
    if dep_state:
        update_deployment_state(
            payload.deployment_id, dep_state,
            error=payload.last_error,
        )
    else:
        import logging
        logging.getLogger("jinni.routes").warning(
            f"Unknown runner_state '{payload.runner_state}' from "
            f"{worker_id} (dep={payload.deployment_id})"
        )
    return {"ok": True, "received": True}


# =============================================================================
# System Summary
# =============================================================================

@router.get("/api/system/summary", tags=["System"])
async def system_summary():
    fleet = get_fleet_summary()
    portfolio = get_portfolio_summary()
    total = fleet["total_workers"]
    online = fleet["online_workers"]
    if online > 0:
        system_status = "operational"
    elif total > 0:
        system_status = "degraded"
    else:
        system_status = "no_workers"
    return {
        "total_nodes": total,
        "online_nodes": online,
        "stale_nodes": fleet["stale_workers"],
        "offline_nodes": fleet["offline_workers"],
        "warning_nodes": fleet.get("warning_workers", 0),
        "error_nodes": fleet["error_workers"],
        "total_open_positions": portfolio.get("open_positions", 0),
        "system_status": system_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Settings
# =============================================================================

@router.get("/api/settings", tags=["Settings"])
async def get_settings():
    return {"ok": True, "settings": get_system_settings()}


class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]


@router.put("/api/settings", tags=["Settings"])
async def update_settings(payload: SettingsUpdate):
    result = save_system_settings(payload.settings)
    return {"ok": True, "settings": result}


# =============================================================================
# Admin
# =============================================================================

@router.get("/api/admin/stats", tags=["Admin"])
async def admin_stats():
    return {"ok": True, "stats": admin_get_stats()}


@router.post("/api/admin/strategies/{strategy_id}/delete", tags=["Admin"])
async def admin_delete_strategy_endpoint(strategy_id: str):
    result = admin_delete_strategy(strategy_id)
    return {"ok": True, **result}


@router.post("/api/admin/portfolio/reset", tags=["Admin"])
async def admin_reset_portfolio_endpoint():
    result = admin_reset_portfolio()
    return {"ok": True, **result}


@router.post("/api/admin/trades/clear", tags=["Admin"])
async def admin_clear_trades_endpoint():
    result = admin_clear_trades()
    return {"ok": True, **result}


@router.post("/api/admin/workers/{worker_id}/remove", tags=["Admin"])
async def admin_remove_worker_endpoint(worker_id: str):
    result = admin_remove_worker(worker_id)
    return {"ok": True, **result}


@router.post("/api/admin/workers/stale/remove", tags=["Admin"])
async def admin_remove_stale_workers_endpoint():
    result = admin_remove_stale_workers()
    return {"ok": True, **result}


@router.post("/api/admin/events/clear", tags=["Admin"])
async def admin_clear_events_endpoint():
    result = admin_clear_events()
    return {"ok": True, **result}


class SystemResetConfirm(BaseModel):
    confirm: str


@router.post("/api/admin/system/reset", tags=["Admin"])
async def admin_full_reset_endpoint(payload: SystemResetConfirm):
    if payload.confirm != "RESET_EVERYTHING":
        raise HTTPException(
            status_code=400,
            detail="Must send confirm='RESET_EVERYTHING'",
        )
    result = admin_full_reset()
    return {"ok": True, "cleared": result}


@router.post("/api/admin/emergency-stop", tags=["Admin"])
async def emergency_stop():
    """Stop all strategies + close all positions across all workers."""
    result = emergency_stop_all()
    return result
# =============================================================================
# Validation Jobs
# =============================================================================

from app.persistence import (
    save_validation_job, update_validation_progress,
    complete_validation_job, fail_validation_job,
    get_validation_job, get_all_validation_jobs,
    delete_validation_job,
)


class ValidationJobCreate(BaseModel):
    strategy_id: str
    worker_id: str
    symbol: str
    month: int
    year: int = 2026
    lot_size: Optional[float] = 0.01
    bar_size_points: Optional[float] = 100
    max_bars_memory: Optional[int] = 500
    spread_points: Optional[float] = 0
    commission_per_lot: Optional[float] = 0
    strategy_parameters: Optional[Dict[str, Any]] = None


@router.post("/api/validation/jobs", tags=["Validation"])
async def create_validation_job(payload: ValidationJobCreate):
    """Create a new validation job and send to worker."""
    strat = get_strategy(payload.strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found.")

    import uuid
    job_id = "val-" + str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    file_content = get_strategy_file_content(payload.strategy_id)
    if not file_content:
        raise HTTPException(status_code=404,
                            detail="Strategy file content not found.")

    strat_name = strat.get("name", payload.strategy_id)

    # Save to DB
    save_validation_job(job_id, {
        "strategy_id": payload.strategy_id,
        "strategy_name": strat_name,
        "worker_id": payload.worker_id,
        "symbol": payload.symbol,
        "month": payload.month,
        "year": payload.year,
        "lot_size": payload.lot_size,
        "bar_size_points": payload.bar_size_points,
        "max_bars_memory": payload.max_bars_memory,
        "spread_points": payload.spread_points,
        "commission_per_lot": payload.commission_per_lot,
        "state": "queued",
    })

    # Send command to worker
    cmd_payload = {
        "job_id": job_id,
        "strategy_id": payload.strategy_id,
        "strategy_file_content": file_content,
        "strategy_class_name": strat.get("class_name"),
        "strategy_parameters": payload.strategy_parameters or {},
        "symbol": payload.symbol,
        "month": payload.month,
        "year": payload.year,
        "lot_size": payload.lot_size,
        "bar_size_points": payload.bar_size_points,
        "max_bars_memory": payload.max_bars_memory,
        "spread_points": payload.spread_points,
        "commission_per_lot": payload.commission_per_lot,
    }
    enqueue_command(payload.worker_id, "run_validation", cmd_payload)

    log_event_db("validation", "created",
                 f"Validation job {job_id} created: "
                 f"{strat_name} on {payload.symbol} "
                 f"{payload.year}-{payload.month:02d}",
                 worker_id=payload.worker_id,
                 strategy_id=payload.strategy_id,
                 symbol=payload.symbol)

    return {
        "ok": True,
        "job_id": job_id,
        "timestamp": now,
    }


@router.get("/api/validation/jobs", tags=["Validation"])
async def list_validation_jobs(limit: int = Query(50)):
    jobs = get_all_validation_jobs(limit=limit)
    return {
        "ok": True,
        "jobs": jobs,
        "count": len(jobs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/validation/jobs/{job_id}", tags=["Validation"])
async def get_validation_job_detail(job_id: str):
    job = get_validation_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Validation job not found.")
    return {"ok": True, "job": job}


@router.post("/api/validation/jobs/{job_id}/progress", tags=["Validation"])
async def update_validation_job_progress(job_id: str,
                                          payload: dict = Body(...)):
    progress = payload.get("progress", 0)
    message = payload.get("progress_message", "")
    update_validation_progress(job_id, progress, message)
    return {"ok": True}


@router.post("/api/validation/jobs/{job_id}/results", tags=["Validation"])
async def receive_validation_results(job_id: str,
                                      payload: dict = Body(...)):
    if "error" in payload and payload["error"]:
        fail_validation_job(job_id, payload["error"])
        log_event_db("validation", "failed",
                     f"Validation {job_id} failed: {payload['error']}",
                     level="ERROR")
        return {"ok": True, "state": "failed"}

    results = payload.get("results", {})
    complete_validation_job(job_id, results)

    summary = results.get("summary", {})
    log_event_db("validation", "completed",
                 f"Validation {job_id} complete: "
                 f"{summary.get('total_trades', 0)} trades, "
                 f"net=${summary.get('net_pnl', 0):.2f}",
                 data=summary)

    return {"ok": True, "state": "completed"}


@router.delete("/api/validation/jobs/{job_id}", tags=["Validation"])
async def delete_validation_job_endpoint(job_id: str):
    delete_validation_job(job_id)
    return {"ok": True, "deleted": job_id}


@router.post("/api/validation/jobs/{job_id}/stop", tags=["Validation"])
async def stop_validation_job(job_id: str):
    job = get_validation_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("state") in ("completed", "failed"):
        return {"ok": True, "message": "Already finished."}
    enqueue_command(job["worker_id"], "stop_validation", {"job_id": job_id})
    fail_validation_job(job_id, "Cancelled by user")
    return {"ok": True, "message": "Stop command sent."}
```

---

## `vm/worker_agent.py`

```python
"""
JINNI Grid - Worker Agent
Heartbeat + Command polling + Strategy Runner + Validation Runner management.
worker/worker_agent.py
"""
import os
import sys
import time
import socket
import threading
import yaml
import requests

_worker_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_worker_dir)
if _worker_dir not in sys.path:
    sys.path.insert(0, _worker_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.strategy_worker import StrategyRunner
from core.validation_runner import ValidationRunner
from trading.portfolio import TradeLedger


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if not os.path.exists(config_path):
        print(f"[ERROR] config.yaml not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_host():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname} ({ip})"
    except Exception:
        return socket.gethostname()


class WorkerAgent:
    def __init__(self, config: dict):
        self.worker_id = config["worker"]["worker_id"]
        self.worker_name = config["worker"].get("worker_name", self.worker_id)
        self.mother_url = config["mother_server"]["url"].rstrip("/")
        self.heartbeat_interval = config["heartbeat"].get("interval_seconds", 10)
        self.agent_version = config["agent"].get("version", "0.2.0")
        self.host = detect_host()

        self._runner: StrategyRunner | None = None
        self._runner_lock = threading.Lock()

        # Validation runners (can run multiple)
        self._validation_runners: dict = {}  # job_id -> ValidationRunner
        self._validation_lock = threading.Lock()

        # Local trade ledger for persistence
        self._ledger = TradeLedger(self.worker_id)
        print(f"[AGENT] TradeLedger initialized for worker '{self.worker_id}'")

    # ── Heartbeat ───────────────────────────────────────────

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner
        diag = runner.get_diagnostics() if runner else {}

        runner_state = diag.get("runner_state", "idle")
        if runner_state in ("idle", "running", "warming_up"):
            worker_state = "online"
        elif runner_state == "failed":
            worker_state = "error"
        elif runner_state == "stopped":
            worker_state = "online"
        else:
            worker_state = runner_state if runner else "online"

        active_strategies = []
        if diag.get("strategy_id"):
            active_strategies = [diag["strategy_id"]]

        errors = []
        if diag.get("last_error"):
            errors = [diag["last_error"]]

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "host": self.host,
            "state": worker_state,
            "agent_version": self.agent_version,
            "mt5_state": diag.get("mt5_state"),
            "account_id": diag.get("account_id"),
            "broker": diag.get("broker"),
            "active_strategies": active_strategies,
            "open_positions_count": diag.get("open_positions_count", 0),
            "floating_pnl": diag.get("floating_pnl", 0.0),
            "errors": errors,
            "total_ticks": diag.get("total_ticks", 0),
            "total_bars": diag.get("total_bars", 0),
            "current_bars_in_memory": diag.get("current_bars_in_memory", 0),
            "on_bar_calls": diag.get("on_bar_calls", 0),
            "signal_count": diag.get("signal_count", 0),
            "last_bar_time": str(diag["last_bar_time"]) if diag.get("last_bar_time") else None,
            "current_price": diag.get("current_price"),
            "account_balance": diag.get("account_balance"),
            "account_equity": diag.get("account_equity"),
        }

    def send_heartbeat(self):
        endpoint = f"{self.mother_url}/api/Grid/workers/heartbeat"
        payload = self._build_heartbeat_payload()
        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            data = resp.json()
            status = "REGISTERED" if data.get("registered") else "OK"
            print(f"[HEARTBEAT] {status} | worker={self.worker_id}")
        except requests.exceptions.ConnectionError:
            print(f"[WARNING] Could not reach Mother Server at {self.mother_url}")
        except Exception as e:
            print(f"[ERROR] Heartbeat: {type(e).__name__}: {e}")

    # ── Trade Reporting ─────────────────────────────────────

    def _report_trade(self, report: dict):
        try:
            self._ledger.add_trade(
                report,
                deployment_id=report.get("deployment_id"),
                strategy_id=report.get("strategy_id"),
            )
        except Exception as e:
            print(f"[ERROR] Local trade save failed: {e}")

        payload = {
            "trade_id": report.get("id"),
            "deployment_id": report.get("deployment_id"),
            "strategy_id": report.get("strategy_id"),
            "worker_id": report.get("worker_id"),
            "symbol": report.get("symbol", ""),
            "direction": report.get("direction", ""),
            "entry_price": report.get("entry_price", 0),
            "exit_price": report.get("exit_price"),
            "entry_time": str(report.get("entry_time", "")),
            "exit_time": str(report.get("exit_time", "")),
            "exit_reason": report.get("exit_reason"),
            "sl_level": report.get("sl_level"),
            "tp_level": report.get("tp_level"),
            "lot_size": report.get("lot_size", 0.01),
            "ticket": report.get("ticket"),
            "points_pnl": report.get("points_pnl", 0),
            "profit": report.get("profit", 0),
            "bars_held": report.get("bars_held", 0),
        }
        endpoint = f"{self.mother_url}/api/portfolio/trades/report"
        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"[TRADE] Reported to Mother")
            else:
                print(f"[ERROR] Trade report HTTP {resp.status_code}")
        except Exception as e:
            print(f"[ERROR] Trade report failed: {e}")

    # ── Validation Callbacks ────────────────────────────────

    def _validation_progress_cb(self, data: dict):
        endpoint = f"{self.mother_url}/api/validation/jobs/{data['job_id']}/progress"
        try:
            requests.post(endpoint, json=data, timeout=10)
        except Exception as e:
            print(f"[VALIDATION] Progress report failed: {e}")

    def _validation_results_cb(self, data: dict):
        endpoint = f"{self.mother_url}/api/validation/jobs/{data['job_id']}/results"
        try:
            resp = requests.post(endpoint, json=data, timeout=30)
            if resp.status_code == 200:
                print(f"[VALIDATION] Results sent for job {data['job_id']}")
            else:
                print(f"[VALIDATION] Results POST failed: {resp.status_code}")
        except Exception as e:
            print(f"[VALIDATION] Results send failed: {e}")

        # Cleanup runner
        with self._validation_lock:
            self._validation_runners.pop(data["job_id"], None)

    # ── Command Polling ─────────────────────────────────────

    def poll_commands(self):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/poll"
        try:
            resp = requests.get(endpoint, timeout=10)
            data = resp.json()
            commands = data.get("commands", [])
            for cmd in commands:
                self._handle_command(cmd)
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"[ERROR] Command poll: {type(e).__name__}: {e}")

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get("command_type")
        cmd_id = cmd.get("command_id")
        payload = cmd.get("payload", {})
        print(f"[COMMAND] Received: {cmd_type} ({cmd_id})")
        self._ack_command(cmd_id)

        if cmd_type == "deploy_strategy":
            self._handle_deploy(payload)
        elif cmd_type == "stop_strategy":
            self._handle_stop(payload)
        elif cmd_type == "run_validation":
            self._handle_validation(payload)
        elif cmd_type == "stop_validation":
            self._handle_stop_validation(payload)
        else:
            print(f"[COMMAND] Unknown command type: {cmd_type}")

    def _ack_command(self, command_id: str):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/ack"
        try:
            requests.post(endpoint, json={"command_id": command_id}, timeout=10)
        except Exception as e:
            print(f"[ERROR] Ack failed: {e}")

    def _report_runner_status(self, status: dict):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/runner-status"
        try:
            requests.post(endpoint, json=status, timeout=10)
        except Exception as e:
            print(f"[ERROR] Runner status report failed: {e}")

    # ── Deploy / Stop ───────────────────────────────────────

    def _handle_deploy(self, payload: dict):
        with self._runner_lock:
            if self._runner:
                print(f"[WARNING] Replacing existing runner")
                self._runner.stop()
                self._runner = None
            payload["worker_id"] = self.worker_id
            runner = StrategyRunner(
                deployment_config=payload,
                status_callback=self._report_runner_status,
                trade_callback=self._report_trade,
            )
            self._runner = runner
            runner.start()

    def _handle_stop(self, payload: dict):
        with self._runner_lock:
            if self._runner:
                dep_id = payload.get("deployment_id")
                if dep_id and self._runner.deployment_id != dep_id:
                    print(f"[COMMAND] Stop ignored — deployment_id mismatch.")
                    return
                self._runner.stop()
                self._runner = None
                print(f"[RUNNER] Stopped deployment {dep_id}")

    # ── Validation ──────────────────────────────────────────

    def _handle_validation(self, payload: dict):
        job_id = payload.get("job_id")
        if not job_id:
            print("[VALIDATION] No job_id in payload")
            return

        with self._validation_lock:
            if job_id in self._validation_runners:
                print(f"[VALIDATION] Job {job_id} already running")
                return

            runner = ValidationRunner(
                job_config=payload,
                progress_callback=self._validation_progress_cb,
                results_callback=self._validation_results_cb,
            )
            self._validation_runners[job_id] = runner
            runner.start()
            print(f"[VALIDATION] Started job {job_id}")

    def _handle_stop_validation(self, payload: dict):
        job_id = payload.get("job_id")
        if not job_id:
            return
        with self._validation_lock:
            runner = self._validation_runners.pop(job_id, None)
            if runner:
                runner.stop()
                print(f"[VALIDATION] Stopped job {job_id}")

    # ── Main Loop ───────────────────────────────────────────

    def run(self):
        print("")
        print("=" * 56)
        print("  JINNI Grid Worker Agent")
        print("=" * 56)
        print(f"  Worker ID:    {self.worker_id}")
        print(f"  Worker Name:  {self.worker_name}")
        print(f"  Host:         {self.host}")
        print(f"  Mother URL:   {self.mother_url}")
        print(f"  Heartbeat:    {self.heartbeat_interval}s")
        print(f"  Agent:        v{self.agent_version}")
        print("=" * 56)
        print("")

        try:
            while True:
                self.send_heartbeat()
                self.poll_commands()
                time.sleep(self.heartbeat_interval)

        except KeyboardInterrupt:
            print(f"\n[SHUTDOWN] Stopping worker agent '{self.worker_id}'...")
            with self._runner_lock:
                if self._runner:
                    self._runner.stop()
            with self._validation_lock:
                for r in self._validation_runners.values():
                    r.stop()
            sys.exit(0)


def main():
    config = load_config()
    agent = WorkerAgent(config)
    agent.run()


if __name__ == "__main__":
    main()
```

---

## `app/services/strategy_registry.py`

```python
"""
JINNI Grid — Strategy Registry (DB-backed)
app/services/strategy_registry.py

Strategies are stored:
  - Source code: data/strategies/{strategy_id}.py (filesystem)
  - Metadata: SQLite via app/persistence.py
"""

import ast
import hashlib
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from app.persistence import (
    save_strategy, get_all_strategies_db, get_strategy_db, log_event_db
)

log = logging.getLogger("jinni.strategy")

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "strategies"
)

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(STRATEGY_DIR, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))
    return safe or "unnamed_strategy"


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def _safe_eval_node(node):
    """
    Safely evaluate an AST node to a Python literal.
    Handles: str, int, float, bool, None, dict, list, tuple, set.
    Returns None if the node cannot be safely evaluated.
    """
    try:
        # ast.literal_eval on the source representation
        source = ast.unparse(node)
        return ast.literal_eval(source)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None

def _extract_strategy_class(source: str) -> Optional[dict]:
    """Parse source to find a class extending BaseStrategy."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        log.warning(f"Strategy syntax error: {e}")
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name == "BaseStrategy":
                info = {"class_name": node.name}
                for item in node.body:
                    # Class-level simple assignments: strategy_id = "xyz"
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if not isinstance(target, ast.Name):
                                continue
                            val = _safe_eval_node(item.value)
                            if val is not None:
                                info[target.id] = val
                    # Class-level annotated assignments: strategy_id: str = "xyz"
                    elif isinstance(item, ast.AnnAssign):
                        if (isinstance(item.target, ast.Name)
                                and item.value is not None):
                            val = _safe_eval_node(item.value)
                            if val is not None:
                                info[item.target.id] = val
                log.info(f"Extracted strategy class: {node.name} fields={list(info.keys())}")
                return info

    # Log what classes WERE found for debugging
    classes_found = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if classes_found:
        log.warning(f"Found classes {classes_found} but none extend BaseStrategy")
    else:
        log.warning("No classes found in strategy source at all")
    return None


# =============================================================================
# Public API
# =============================================================================

def upload_strategy(filename: str, source_code: str) -> dict:
    """Upload and persist a strategy file."""
    _ensure_dir()

    # Check syntax first
    try:
        ast.parse(source_code)
    except SyntaxError as e:
        return {
            "ok": False,
            "error": f"Python syntax error at line {e.lineno}: {e.msg}",
        }

    info = _extract_strategy_class(source_code)
    if info is None:
        # Give a detailed error
        try:
            tree = ast.parse(source_code)
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        except Exception:
            classes = []
        if classes:
            return {
                "ok": False,
                "error": f"Found classes {classes} but none extend BaseStrategy. "
                         f"Your class must inherit from BaseStrategy.",
            }
        return {
            "ok": False,
            "error": "No class found in file. Strategy must contain a class extending BaseStrategy.",
        }

    strategy_id = info.get("strategy_id", "")
    if not strategy_id:
        strategy_id = info["class_name"].lower()

    class_name = info["class_name"]
    name = info.get("name", class_name)
    description = info.get("description", "")
    version = info.get("version", "1.0")
    min_lookback = info.get("min_lookback", 0)
    parameters = info.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    safe_name = _sanitize_filename(strategy_id)
    file_path = os.path.join(STRATEGY_DIR, f"{safe_name}.py")
    fhash = _file_hash(source_code)

    # Atomic write
    tmp_path = file_path + ".tmp"
    with _lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            os.replace(tmp_path, file_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {"ok": False, "error": f"File write failed: {e}"}

    now = datetime.now(timezone.utc).isoformat()

    # Persist metadata to DB
    save_strategy(strategy_id, {
        "filename": filename,
        "class_name": class_name,
        "name": name,
        "description": description,
        "version": version,
        "min_lookback": min_lookback,
        "file_hash": fhash,
        "file_path": file_path,
        "parameters": parameters,
        "uploaded_at": now,
        "is_valid": True,
    })

    log.info(f"Strategy uploaded: {strategy_id} ({class_name}) hash={fhash}")

    log_event_db("strategy", "uploaded",
                 f"Strategy {strategy_id} uploaded from {filename}",
                 strategy_id=strategy_id,
                 data={"class_name": class_name, "version": version, "hash": fhash})

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "class_name": class_name,
        "name": name,
        "version": version,
        "file_hash": fhash,
    }


def get_all_strategies() -> list:
    """Return all valid strategies from DB."""
    db_strategies = get_all_strategies_db()
    result = []
    for s in db_strategies:
        params = s.get("parameters", {})
        if isinstance(params, str):
            try:
                import json
                params = json.loads(params)
            except Exception:
                params = {}
        result.append({
            "strategy_id": s["strategy_id"],
            "strategy_name": s.get("name", s["strategy_id"]),
            "name": s.get("name", s["strategy_id"]),
            "filename": s.get("filename", ""),
            "class_name": s.get("class_name", ""),
            "description": s.get("description", ""),
            "version": s.get("version", ""),
            "min_lookback": s.get("min_lookback", 0),
            "file_hash": s.get("file_hash", ""),
            "uploaded_at": s.get("uploaded_at", ""),
            "validation_status": "validated" if s.get("is_valid") else "invalid",
            "parameter_count": len(params) if isinstance(params, dict) else 0,
            "parameters": params,
            "error": None,
        })
    return result


def get_strategy(strategy_id: str) -> Optional[dict]:
    return get_strategy_db(strategy_id)


def get_strategy_file_content(strategy_id: str) -> Optional[str]:
    """Read strategy source code from disk."""
    rec = get_strategy_db(strategy_id)
    if not rec:
        return None

    file_path = rec.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        # Try default path
        safe_name = _sanitize_filename(strategy_id)
        file_path = os.path.join(STRATEGY_DIR, f"{safe_name}.py")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def validate_strategy(strategy_id: str) -> dict:
    content = get_strategy_file_content(strategy_id)
    if content is None:
        return {"ok": False, "error": "Strategy file not found."}

    info = _extract_strategy_class(content)
    if info is None:
        return {"ok": False, "error": "No BaseStrategy class found in file."}

    try:
        compile(content, f"{strategy_id}.py", "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error: {e}"}

    log_event_db("strategy", "validated",
                 f"Strategy {strategy_id} passed validation",
                 strategy_id=strategy_id)

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "class_name": info["class_name"],
        "valid": True,
    }


def load_strategies_from_disk():
    """Scan data/strategies/ for .py files and register any not already in DB."""
    _ensure_dir()
    count = 0

    for fname in os.listdir(STRATEGY_DIR):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(STRATEGY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            continue

        info = _extract_strategy_class(source)
        if info is None:
            continue

        strategy_id = info.get("strategy_id", "")
        if not strategy_id:
            strategy_id = info["class_name"].lower()

        # Check if already in DB
        existing = get_strategy_db(strategy_id)
        if existing:
            continue

        save_strategy(strategy_id, {
            "filename": fname,
            "class_name": info["class_name"],
            "name": info.get("name", info["class_name"]),
            "description": info.get("description", ""),
            "version": info.get("version", "1.0"),
            "min_lookback": info.get("min_lookback", 0),
            "file_hash": _file_hash(source),
            "file_path": fpath,
            "parameters": info.get("parameters", {}),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": True,
        })
        count += 1

    if count > 0:
        log.info(f"Loaded {count} strategies from disk into DB")
```

---

## `vm/trading/indicators.py`

```python
"""
JINNI GRID — Indicator Engine
worker/indicators.py

Ported from JINNI ZERO backtester shared.py / engine_core.py.
Supports: SMA, EMA, WMA, HMA precomputation on range bar series.
Populates ctx.indicators (current bar values) and ctx.ind_series (full series).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# =============================================================================
# Core MA Functions (matching JINNI ZERO backtester exactly)
# =============================================================================

def precompute_sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period
    for i in range(period, n):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period
    return result


def precompute_ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    # Seed with SMA
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    k = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        val = values[i] * k + prev * (1 - k)
        result[i] = val
        prev = val
    return result


def precompute_wma(values: List[float], period: int) -> List[Optional[float]]:
    """Weighted Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    denom = period * (period + 1) / 2.0
    for i in range(period - 1, n):
        w_sum = 0.0
        for j in range(period):
            w_sum += values[i - period + 1 + j] * (j + 1)
        result[i] = w_sum / denom
    return result


def precompute_hma(values: List[float], period: int) -> List[Optional[float]]:
    """
    Hull Moving Average — full series.
    HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) )
    """
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result

    half = max(int(period / 2), 1)
    sqrt_p = max(int(math.sqrt(period)), 1)

    wma_half = precompute_wma(values, half)
    wma_full = precompute_wma(values, period)

    # Build diff series: 2*WMA(half) - WMA(full)
    diff = []
    diff_start = None
    for i in range(n):
        if wma_half[i] is not None and wma_full[i] is not None:
            diff.append(2.0 * wma_half[i] - wma_full[i])
            if diff_start is None:
                diff_start = i
        else:
            diff.append(0.0)

    if diff_start is None:
        return result

    # Only use valid portion of diff
    valid_diff = diff[diff_start:]
    hma_of_diff = precompute_wma(valid_diff, sqrt_p)

    for i, val in enumerate(hma_of_diff):
        target_idx = diff_start + i
        if target_idx < n:
            result[target_idx] = val

    return result


def precompute_ma(values: List[float], kind: str, period: int) -> List[Optional[float]]:
    """
    Dispatch to the correct MA precompute function.
    Matches JINNI ZERO backtester shared.py exactly.
    """
    kind_upper = kind.upper()
    if kind_upper == "SMA":
        return precompute_sma(values, period)
    elif kind_upper == "EMA":
        return precompute_ema(values, period)
    elif kind_upper == "WMA":
        return precompute_wma(values, period)
    elif kind_upper == "HMA":
        return precompute_hma(values, period)
    else:
        print(f"[INDICATORS] WARNING: Unknown MA kind '{kind}', falling back to SMA")
        return precompute_sma(values, period)


# =============================================================================
# Source Extraction
# =============================================================================

def _source_values(bars: list, source: str) -> List[float]:
    """Extract price series from bars by source name."""
    if source == "open":
        return [float(b.get("open", 0)) for b in bars]
    elif source == "high":
        return [float(b.get("high", 0)) for b in bars]
    elif source == "low":
        return [float(b.get("low", 0)) for b in bars]
    else:
        return [float(b.get("close", 0)) for b in bars]


def precompute_indicator_series(bars: list, spec: dict) -> List[Optional[float]]:
    """
    Precompute a full indicator series from bars + spec.
    Spec format (from strategy.build_indicators()):
        {"key": "hma_200", "kind": "HMA", "period": 200, "source": "close"}
    """
    kind = spec.get("kind", "SMA").upper()
    source = spec.get("source", "close")
    period = int(spec.get("period", 14))
    values = _source_values(bars, source)
    return precompute_ma(values, kind, period)


# =============================================================================
# Indicator Engine (live — recomputes on every new bar)
# =============================================================================

class IndicatorEngine:
    """
    Manages indicator computation for live trading.

    On each new bar:
      1. Recomputes full series for all declared indicators
      2. Updates ctx.indicators with current-bar values
      3. Updates ctx.ind_series with full series (for strategy lookback)

    This matches backtester behavior where indicators are precomputed
    over the full bar array. For live, we recompute on the growing
    bar deque — slightly less efficient but guarantees identical values.
    """

    def __init__(self, indicator_defs: List[Dict[str, Any]]):
        self._defs = indicator_defs
        self._warned: set = set()

        if self._defs:
            keys = [d["key"] for d in self._defs]
            print(f"[INDICATORS] Registered {len(self._defs)} indicators: {keys}")
        else:
            print("[INDICATORS] No indicators requested by strategy.")

    def update(self, bars: list, ctx) -> None:
        """Recompute all indicators from current bar list and update ctx."""
        for defn in self._defs:
            key = defn["key"]
            kind = defn.get("kind", "SMA").upper()
            source = defn.get("source", "close")
            period = int(defn.get("period", 14))

            values = _source_values(bars, source)
            series = precompute_ma(values, kind, period)

            # Store full series
            ctx._ind_series[key] = series

            # Store current value (last bar)
            if series and len(series) > 0:
                ctx._indicators[key] = series[-1]
            else:
                ctx._indicators[key] = None

    def get_series_at(self, indicator_store: dict, key: str, index: int) -> Optional[float]:
        """Get indicator value at a specific bar index."""
        series = indicator_store.get(key)
        if series is None or index < 0 or index >= len(series):
            return None
        return series[index]
```

---

## `requirements.txt`

```text
fastapi>=0.110.0
uvicorn>=0.27.0
pyyaml>=6.0
python-multipart>=0.0.9
```

---

## `app/routes/__init__.py`

```python
# JINNI Grid - Route package
```
