import { store } from '../store';
import { api } from '../api';
import type { Params, PanelEntry, PanelEntryDetail, TaskCard } from '../types';
import { formatInterval, formatRelative } from '../markdown';
import { renderTaskEditor } from './taskEditor';

type PanelTab = 'tasks' | 'panel' | 'config';

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export function createPanel(): HTMLElement {
  const el = document.createElement('aside');
  el.id = 'panel';

  let activeTab: PanelTab = 'tasks';
  let editingTask: TaskCard | null | 'new' = null; // null = not editing, 'new' = new task
  let editingConfig = false;
  const expandedPanel = new Set<string>(); // tids currently expanded
  const panelDetails = new Map<string, PanelEntryDetail>(); // tid → latest detail fetch
  let panelPollTimer: number | null = null;

  function render() {
    if (!store.currentSessionId) {
      el.innerHTML = `<div class="panel-empty">Select a session</div>`;
      return;
    }

    const tabsHtml = `
      <div class="panel-tabs">
        <button class="panel-tab${activeTab === 'tasks' ? ' active' : ''}" data-tab="tasks">Tasks</button>
        <button class="panel-tab${activeTab === 'panel' ? ' active' : ''}" data-tab="panel">Panel</button>
        <button class="panel-tab${activeTab === 'config' ? ' active' : ''}" data-tab="config">Config</button>
      </div>
    `;

    let contentHtml = '';

    if (activeTab === 'tasks') {
      contentHtml = renderTasksTab();
    } else if (activeTab === 'panel') {
      contentHtml = renderPanelTab();
    } else {
      contentHtml = renderConfigTab();
    }

    el.innerHTML = `
      ${tabsHtml}
      <div class="panel-content" id="panel-content">
        ${contentHtml}
      </div>
    `;

    // Bind tab buttons
    el.querySelectorAll('.panel-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        activeTab = (btn as HTMLElement).dataset.tab as PanelTab;
        editingTask = null;
        editingConfig = false;
        render();
      });
    });

    // Bind task actions
    if (activeTab === 'tasks') {
      bindTasksTab();
    } else if (activeTab === 'panel') {
      bindPanelTab();
    } else {
      bindConfigTab();
    }

    updatePanelPolling();
  }

  function renderTasksTab(): string {
    if (editingTask !== null) return ''; // replaced by editor below

    const cards = store.taskCards;
    if (!cards.length) {
      return `
        <div class="tasks-empty">No task cards yet.</div>
        <button class="btn-sm btn-primary" id="btn-new-task">+ New Task</button>
      `;
    }

    const cardsHtml = cards.map(card => renderTaskCard(card)).join('');
    return `
      <div class="task-cards">${cardsHtml}</div>
      <div class="tasks-footer">
        <button class="btn-sm btn-primary" id="btn-new-task">+ New Task</button>
        <button class="btn-sm" id="btn-refresh-tasks">↻ Refresh</button>
      </div>
    `;
  }

  function renderTaskCard(card: TaskCard): string {
    const isDuty = card.name === 'duty';
    const dutyPill = isDuty ? `<span class="hb-pill">duty</span>` : '';
    const intervalStr = formatInterval(card.interval);
    const lastRun = formatRelative(card.last_finished_at);
    const statusClass = `task-status-${card.status}`;

    // Content preview: first 3 non-empty lines
    const preview = card.description.split('\n').filter(l => l.trim()).slice(0, 3).join('\n');

    return `
      <div class="task-card" data-name="${escHtml(card.name)}">
        <div class="task-card-header">
          <span class="task-name">${escHtml(card.name)}</span>
          ${dutyPill}
          <span class="task-status-badge ${statusClass}">${card.status}</span>
        </div>
        <div class="task-card-meta">
          <span class="task-interval">${escHtml(intervalStr)}</span>
          ${card.start_at || card.end_at ? `<span class="task-window">window: ${escHtml(card.start_at ?? '∞')} → ${escHtml(card.end_at ?? '∞')}</span>` : ''}
          <span class="task-last-run">last run: ${escHtml(lastRun)}</span>
        </div>
        ${preview ? `<div class="task-preview">${escHtml(preview)}</div>` : ''}
        <div class="task-card-actions">
          <button class="btn-sm btn-edit" data-name="${escHtml(card.name)}">Edit</button>
        </div>
      </div>
    `;
  }

  function bindTasksTab() {
    el.querySelector('#btn-new-task')?.addEventListener('click', () => {
      editingTask = 'new';
      showTaskEditor(null);
    });

    el.querySelector('#btn-refresh-tasks')?.addEventListener('click', async () => {
      const sid = store.currentSessionId;
      if (!sid) return;
      const res = await api.getTasks(sid).catch(console.error);
      if (store.currentSessionId !== sid) return; // stale guard (Problem 2)
      if (res) {
        store.taskCards = res.cards;
        store.emit('tasks');
        render();
      }
    });

    el.querySelectorAll('.btn-edit').forEach(btn => {
      btn.addEventListener('click', () => {
        const name = (btn as HTMLElement).dataset.name;
        const card = store.taskCards.find(c => c.name === name) ?? null;
        editingTask = card;
        showTaskEditor(card);
      });
    });
  }

  function showTaskEditor(card: TaskCard | null) {
    const content = el.querySelector('#panel-content');
    if (!content || !store.currentSessionId) return;
    const sessionId = store.currentSessionId;

    const editor = renderTaskEditor(card, sessionId, async () => {
      editingTask = null;
      // Refresh tasks — guard against stale session (Problem 2)
      const res = await api.getTasks(sessionId).catch(console.error);
      if (store.currentSessionId !== sessionId) return;
      if (res) {
        store.taskCards = res.cards;
        store.emit('tasks');
      }
      render();
    });

    content.innerHTML = '';
    content.appendChild(editor);
  }

  function renderConfigTab(): string {
    if (editingConfig) return ''; // replaced by textarea below

    const params = store.currentParams;
    if (!params) return '<div class="config-empty">No config loaded.</div>';

    const excluded = new Set(['is_meta_session']);
    const rows = Object.entries(params)
      .filter(([k]) => !excluded.has(k))
      .map(([k, v]) => {
        let displayVal: string;
        if (v === null || v === undefined) {
          displayVal = '<span class="cfg-null">— (default)</span>';
        } else if (typeof v === 'object') {
          displayVal = `<code>${escHtml(JSON.stringify(v))}</code>`;
        } else if (typeof v === 'boolean') {
          displayVal = v ? '<span class="cfg-true">true</span>' : '<span class="cfg-false">false</span>';
        } else {
          displayVal = escHtml(String(v));
        }
        return `<tr><td class="cfg-key">${escHtml(k)}</td><td class="cfg-val">${displayVal}</td></tr>`;
      })
      .join('');

    return `
      <table class="config-table">
        <tbody>${rows}</tbody>
      </table>
      <div class="config-footer">
        <button class="btn-sm btn-primary" id="btn-edit-config">Edit JSON</button>
      </div>
    `;
  }

  function bindConfigTab() {
    el.querySelector('#btn-edit-config')?.addEventListener('click', () => {
      editingConfig = true;
      showConfigEditor();
    });
  }

  function showConfigEditor() {
    const content = el.querySelector('#panel-content');
    if (!content || !store.currentSessionId) return;
    const sessionId = store.currentSessionId;
    const params = store.currentParams;

    const textarea = document.createElement('textarea');
    textarea.className = 'config-json-editor';
    textarea.rows = 20;
    textarea.value = JSON.stringify(params, null, 2);

    const errorEl = document.createElement('div');
    errorEl.className = 'form-error hidden';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn-primary';
    saveBtn.textContent = 'Save';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-sm';
    cancelBtn.textContent = 'Cancel';

    saveBtn.addEventListener('click', async () => {
      try {
        const parsed = JSON.parse(textarea.value) as Params;
        const res = await api.setConfig(sessionId, parsed);
        if (store.currentSessionId !== sessionId) return; // stale guard (Problem 2)
        store.currentParams = res.params;
        store.emit('config');
        editingConfig = false;
        render();
      } catch (e) {
        errorEl.textContent = `Error: ${e}`;
        errorEl.classList.remove('hidden');
      }
    });

    cancelBtn.addEventListener('click', () => {
      editingConfig = false;
      render();
    });

    const actions = document.createElement('div');
    actions.className = 'form-row';
    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);

    content.innerHTML = '';
    content.appendChild(textarea);
    content.appendChild(errorEl);
    content.appendChild(actions);
  }

  // ================= PANEL TAB =================

  function renderPanelTab(): string {
    const entries = store.panelEntries;
    if (!entries.length) {
      return `
        <div class="tasks-empty">No panel entries yet.</div>
        <div class="tasks-footer">
          <button class="btn-sm" id="btn-refresh-panel">↻ Refresh</button>
        </div>
      `;
    }
    const rowsHtml = entries.map(e => renderPanelRow(e)).join('');
    return `
      <div class="task-cards">${rowsHtml}</div>
      <div class="tasks-footer">
        <button class="btn-sm" id="btn-refresh-panel">↻ Refresh</button>
      </div>
    `;
  }

  function renderPanelRow(entry: PanelEntry): string {
    const statusClass = `panel-status-${entry.status}`;
    const expanded = expandedPanel.has(entry.tid);
    const detail = panelDetails.get(entry.tid);
    const tailOneLine = panelTailOneLine(entry, detail);
    const fullJsonHtml = expanded
      ? `<pre class="panel-json">${escHtml(JSON.stringify(entryToJsonView(entry, detail), null, 2))}</pre>`
      : '';
    const outputTailHtml = expanded
      ? renderOutputTailBlock(detail)
      : '';
    const actionsHtml = expanded
      ? `
        <div class="task-card-actions">
          <button class="btn-sm" data-panel-action="fetch" data-tid="${escHtml(entry.tid)}">Fetch full output</button>
          <button class="btn-sm" data-panel-action="kill" data-tid="${escHtml(entry.tid)}">Kill</button>
        </div>
      `
      : '';

    return `
      <div class="task-card panel-row${expanded ? ' expanded' : ''}" data-tid="${escHtml(entry.tid)}">
        <div class="task-card-header panel-row-header" data-tid="${escHtml(entry.tid)}">
          <span class="task-status-badge ${statusClass}">${escHtml(entry.status)}</span>
          <span class="task-name">${escHtml(entry.tool_name)}</span>
          <span class="hb-pill panel-tid">${escHtml(entry.tid)}</span>
        </div>
        <div class="task-preview panel-tail" title="${escHtml(tailOneLine)}">${escHtml(tailOneLine) || '<span class="cfg-null">(no output yet)</span>'}</div>
        ${fullJsonHtml}
        ${outputTailHtml}
        ${actionsHtml}
      </div>
    `;
  }

  function entryToJsonView(entry: PanelEntry, detail: PanelEntryDetail | undefined): Record<string, unknown> {
    // Prefer the detail payload (same shape + output_tail) if loaded.
    return detail ? { ...detail } : { ...entry };
  }

  function renderOutputTailBlock(detail: PanelEntryDetail | undefined): string {
    if (!detail) {
      return `<div class="panel-output-tail panel-output-empty">Click “Fetch full output” to load the last 40 lines.</div>`;
    }
    if (detail.output_tail == null) {
      return `<div class="panel-output-tail panel-output-empty">(no output file)</div>`;
    }
    return `<pre class="panel-output-tail">${escHtml(detail.output_tail)}</pre>`;
  }

  function panelTailOneLine(_entry: PanelEntry, detail: PanelEntryDetail | undefined): string {
    const tail = detail?.output_tail;
    if (!tail) return '';
    const lines = tail.split('\n').filter(l => l.length > 0);
    return lines.length ? lines[lines.length - 1] : '';
  }

  function bindPanelTab() {
    el.querySelector('#btn-refresh-panel')?.addEventListener('click', () => {
      refreshPanel();
    });

    el.querySelectorAll('.panel-row-header').forEach(hdr => {
      hdr.addEventListener('click', () => {
        const tid = (hdr as HTMLElement).dataset.tid;
        if (!tid) return;
        if (expandedPanel.has(tid)) {
          expandedPanel.delete(tid);
        } else {
          expandedPanel.add(tid);
        }
        render();
      });
    });

    el.querySelectorAll('[data-panel-action]').forEach(btn => {
      btn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const action = (btn as HTMLElement).dataset.panelAction;
        const tid = (btn as HTMLElement).dataset.tid;
        const sid = store.currentSessionId;
        if (!sid || !tid) return;
        if (action === 'kill') {
          try {
            await api.killPanelEntry(sid, tid);
          } catch (e) {
            console.error('Failed to kill panel entry:', e);
            return;
          }
          if (store.currentSessionId !== sid) return;
          await refreshPanel();
        } else if (action === 'fetch') {
          try {
            const detail = await api.getPanelEntry(sid, tid);
            if (store.currentSessionId !== sid) return;
            panelDetails.set(tid, detail);
            render();
          } catch (e) {
            console.error('Failed to fetch panel entry:', e);
          }
        }
      });
    });
  }

  async function refreshPanel(): Promise<void> {
    const sid = store.currentSessionId;
    if (!sid) return;
    try {
      const entries = await api.getPanel(sid);
      if (store.currentSessionId !== sid) return; // stale (Problem 2)
      store.panelEntries = entries;
      store.emit('panel');
      // If user has entries expanded, refresh their details too so the
      // tail-one-line on the collapsed row and the output block stay fresh.
      if (activeTab === 'panel' && expandedPanel.size > 0) {
        await Promise.all([...expandedPanel].map(async tid => {
          try {
            const detail = await api.getPanelEntry(sid, tid);
            if (store.currentSessionId !== sid) return;
            panelDetails.set(tid, detail);
          } catch (e) {
            console.error('Failed to refresh panel detail:', e);
          }
        }));
      }
      if (activeTab === 'panel') render();
    } catch (e) {
      console.error('Failed to refresh panel:', e);
    }
  }

  function updatePanelPolling() {
    const shouldPoll = activeTab === 'panel' && !!store.currentSessionId;
    if (shouldPoll && panelPollTimer == null) {
      panelPollTimer = window.setInterval(refreshPanel, 2000);
      // Fire an immediate refresh so the tab populates without waiting 2s.
      refreshPanel();
    } else if (!shouldPoll && panelPollTimer != null) {
      window.clearInterval(panelPollTimer);
      panelPollTimer = null;
    }
  }

  // ================= STORE WIRING =================

  store.on('tasks', () => {
    if (activeTab === 'tasks' && editingTask === null) render();
  });
  store.on('panel', () => {
    if (activeTab === 'panel') render();
  });
  store.on('config', () => {
    if (activeTab === 'config' && !editingConfig) render();
  });
  store.on('currentSession', () => {
    editingTask = null;
    editingConfig = false;
    expandedPanel.clear();
    panelDetails.clear();
    store.panelEntries = [];
    render();
  });

  render();
  return el;
}


