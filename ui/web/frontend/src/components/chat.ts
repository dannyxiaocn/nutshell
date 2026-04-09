import { store } from '../store';
import { api } from '../api';
import type { DisplayEvent } from '../types';
import { renderMarkdown, escapeHtml, formatTs } from '../markdown';

export function createChat(): HTMLElement {
  const el = document.createElement('main');
  el.id = 'chat';
  el.innerHTML = `
    <div id="messages" class="messages"></div>
    <div id="chat-input-area" class="chat-input-area">
      <textarea id="chat-input" placeholder="Type a message… (Shift+Enter for newline, Enter to send)" rows="3"></textarea>
      <div class="chat-input-actions">
        <button id="btn-interrupt" class="btn-sm btn-warn" title="Interrupt current turn">⚡ Interrupt</button>
        <button id="btn-send" class="btn-primary">Send</button>
      </div>
    </div>
  `;

  const messages = el.querySelector('#messages') as HTMLDivElement;
  const inputEl = el.querySelector('#chat-input') as HTMLTextAreaElement;
  const sendBtn = el.querySelector('#btn-send') as HTMLButtonElement;
  const interruptBtn = el.querySelector('#btn-interrupt') as HTMLButtonElement;

  // Streaming bubble lives INSIDE the messages div so it scrolls with the conversation
  let streamingEl: HTMLDivElement | null = null;
  let isStreaming = false;

  function getOrCreateStreamingBubble(): HTMLDivElement {
    if (!streamingEl) {
      streamingEl = document.createElement('div');
      streamingEl.className = 'msg msg-agent msg-streaming';
      streamingEl.innerHTML = `
        <div class="msg-header">
          <span class="msg-label">agent</span>
          <span class="streaming-badge">
            <span class="streaming-dot"></span><span class="streaming-dot"></span><span class="streaming-dot"></span>
            <span class="streaming-label">generating…</span>
          </span>
        </div>
        <div class="msg-body msg-streaming-body markdown-body"></div>
      `;
      messages.appendChild(streamingEl);
    }
    return streamingEl;
  }

  function removeStreamingBubble() {
    if (streamingEl) {
      streamingEl.remove();
      streamingEl = null;
    }
    isStreaming = false;
  }

  function clearMessages() {
    removeStreamingBubble();
    messages.innerHTML = '';
    isStreaming = false;
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function appendEvent(event: DisplayEvent) {
    const msgEl = renderEvent(event);
    if (msgEl) {
      messages.appendChild(msgEl);
      scrollToBottom();
    }
  }

  function handleEvent(event: DisplayEvent) {
    switch (event.type) {
      case 'model_status':
        if (event.state === 'running') {
          // Show streaming bubble with dots (no text yet)
          isStreaming = true;
          const bubble = getOrCreateStreamingBubble();
          const body = bubble.querySelector('.msg-streaming-body') as HTMLElement;
          body.innerHTML = '';
          scrollToBottom();
          store.modelState = { state: 'running', source: event.source ?? null };
        } else {
          // Idle: if no agent message came, remove bubble
          if (isStreaming) removeStreamingBubble();
          store.modelState = { state: 'idle', source: null };
        }
        store.emit('modelState');
        break;

      case 'partial_text':
        // Live-update the streaming bubble body with the thinking text
        if (!isStreaming) isStreaming = true;
        {
          const bubble = getOrCreateStreamingBubble();
          const body = bubble.querySelector('.msg-streaming-body') as HTMLElement;
          if (event.content) {
            body.innerHTML = renderMarkdown(event.content);
          }
          scrollToBottom();
        }
        break;

      case 'agent':
        // Final response: remove streaming bubble, append real message
        removeStreamingBubble();
        appendEvent(event);
        break;

      default:
        appendEvent(event);
    }
  }

  // Expose these methods to main.ts
  type ChatMethods = { clearMessages(): void; appendEvent(e: DisplayEvent): void; handleEvent(e: DisplayEvent): void };
  (el as HTMLElement & ChatMethods).clearMessages = clearMessages;
  (el as HTMLElement & ChatMethods).appendEvent = appendEvent;
  (el as HTMLElement & ChatMethods).handleEvent = handleEvent;

  async function sendMessage() {
    const content = inputEl.value.trim();
    if (!content || !store.currentSessionId) return;
    const sessId = store.currentSessionId;
    const sess = store.currentSession;
    if (sess?.id.endsWith('_meta') || sess?.params?.is_meta_session) return;
    inputEl.value = '';
    inputEl.style.height = 'auto';
    try {
      await api.sendMessage(sessId, content);
    } catch (e) {
      appendEvent({ type: 'error', content: `Failed to send: ${e}` });
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
  });

  interruptBtn.addEventListener('click', async () => {
    if (!store.currentSessionId) return;
    await api.interruptSession(store.currentSessionId).catch(console.error);
  });

  // Update input disabled state for meta sessions
  store.on('currentSession', () => {
    const sess = store.currentSession;
    const isMeta = sess?.id.endsWith('_meta') || sess?.params?.is_meta_session;
    inputEl.disabled = !!isMeta;
    sendBtn.disabled = !!isMeta;
    inputEl.placeholder = isMeta ? 'Direct chat with meta sessions is disabled.' : 'Type a message… (Shift+Enter for newline, Enter to send)';
  });

  return el;
}

function renderEvent(event: DisplayEvent): HTMLElement | null {
  const div = document.createElement('div');

  switch (event.type) {
    case 'agent': {
      if (!event.content) return null;
      const isHb = event.triggered_by === 'heartbeat';
      div.className = 'msg msg-agent';
      const label = isHb ? '⏱ agent' : 'agent';
      let usageHtml = '';
      if (event.usage) {
        const u = event.usage;
        const parts: string[] = [];
        if (u.input != null) parts.push(`in:${u.input}`);
        if (u.output != null) parts.push(`out:${u.output}`);
        if (u.cache_read != null) parts.push(`cached:${u.cache_read}`);
        if (u.cache_write != null) parts.push(`wrote:${u.cache_write}`);
        if (parts.length) usageHtml = `<span class="usage-stats">${escapeHtml(parts.join(' · '))}</span>`;
      }
      div.innerHTML = `
        <div class="msg-header">
          <span class="msg-label">${escapeHtml(label)}</span>
          ${usageHtml}
          <span class="msg-ts">${formatTs(event.ts)}</span>
        </div>
        <div class="msg-body markdown-body">${renderMarkdown(event.content)}</div>
      `;
      break;
    }

    case 'user': {
      if (!event.content) return null;
      div.className = 'msg msg-user';
      div.innerHTML = `
        <div class="msg-header">
          <span class="msg-label">you</span>
          <span class="msg-ts">${formatTs(event.ts)}</span>
        </div>
        <div class="msg-body markdown-body">${renderMarkdown(event.content)}</div>
      `;
      break;
    }

    case 'tool': {
      div.className = 'msg msg-tool';
      div.innerHTML = renderToolEvent(event);
      break;
    }

    case 'heartbeat_trigger': {
      div.className = 'msg msg-heartbeat-trigger';
      div.innerHTML = `<span>⏱ heartbeat triggered</span><span class="msg-ts">${formatTs(event.ts)}</span>`;
      break;
    }

    case 'heartbeat_finished': {
      div.className = 'msg msg-heartbeat-finished';
      div.innerHTML = `<em>[session finished]</em>`;
      break;
    }

    case 'status': {
      div.className = 'msg msg-status';
      div.innerHTML = `<em>${escapeHtml(event.value ?? '')}</em>`;
      break;
    }

    case 'error': {
      div.className = 'msg msg-error';
      div.innerHTML = `<span class="msg-label">error</span><div class="msg-body">${escapeHtml(event.content ?? '')}</div>`;
      break;
    }

    default:
      return null;
  }

  return div;
}

function renderToolEvent(event: DisplayEvent): string {
  const name = event.name ?? 'unknown';
  const input = event.input ?? {};

  if (name === 'bash' || name === 'shell') {
    const cmd = String(input['command'] ?? input['cmd'] ?? JSON.stringify(input));
    const isLong = cmd.length > 200 || cmd.includes('\n');
    const cmdHtml = isLong
      ? `<details class="tool-collapse"><summary>command (${cmd.split('\n').length} lines)</summary><pre class="tool-pre">${escapeHtml(cmd)}</pre></details>`
      : `<pre class="tool-pre">${escapeHtml(cmd)}</pre>`;
    return `
      <div class="msg-header">
        <span class="tool-pill">${escapeHtml(name)}</span>
        <span class="msg-ts">${formatTs(event.ts)}</span>
      </div>
      ${cmdHtml}
    `;
  }

  if (name === 'web_search') {
    const query = String(input['query'] ?? input['q'] ?? '');
    return `
      <div class="msg-header">
        <span class="tool-pill">web_search</span>
        <span class="msg-ts">${formatTs(event.ts)}</span>
      </div>
      <div class="tool-query">🔍 ${escapeHtml(query)}</div>
    `;
  }

  // generic: key=value pairs
  const pairs = Object.entries(input)
    .slice(0, 8)
    .map(([k, v]) => {
      const val = typeof v === 'string' ? v : JSON.stringify(v);
      return `<span class="kv-pair"><span class="kv-key">${escapeHtml(k)}</span>=<span class="kv-val">${escapeHtml(val.slice(0, 120))}</span></span>`;
    })
    .join(' ');

  return `
    <div class="msg-header">
      <span class="tool-pill">${escapeHtml(name)}</span>
      <span class="msg-ts">${formatTs(event.ts)}</span>
    </div>
    <div class="tool-args">${pairs}</div>
  `;
}
