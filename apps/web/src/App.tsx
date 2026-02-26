import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { deleteChatSession, getChatSession, listChatSessions, sendChat } from "./api/client";
import { ArcadeBrowser } from "./components/ArcadeBrowser";
import type { ChatHistoryTurn, ChatSessionSummary } from "./types";

type ViewMode = "chat" | "arcades";

const QUICK_PROMPTS = [
  "帮我找北京适合下班后去的机厅",
  "我在广州，推荐几家有 maimai 的店",
  "给我一条从当前位置到最近机厅的路线建议"
];

function formatTimeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function toVisibleTurns(turns: ChatHistoryTurn[]): ChatHistoryTurn[] {
  return turns.filter((turn) => turn.role === "user" || turn.role === "assistant");
}

function SidebarSessionItem({
  item,
  active,
  onClick,
  onDelete,
  deleting
}: {
  item: ChatSessionSummary;
  active: boolean;
  onClick: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <li>
      <div className={`sidebar-session-wrap ${active ? "is-active" : ""}`}>
        <button type="button" onClick={onClick} className="sidebar-session">
          <strong>{item.title}</strong>
          <span>{item.preview || "暂无摘要"}</span>
          <small>{formatTimeLabel(item.updated_at)}</small>
        </button>
        <button type="button" className="sidebar-session-delete" onClick={onDelete} disabled={deleting}>
          {deleting ? "..." : "删"}
        </button>
      </div>
    </li>
  );
}

function ChatPanel({
  turns,
  loading,
  sending,
  inputValue,
  onInputChange,
  onSubmit,
  onQuickAsk,
  error
}: {
  turns: ChatHistoryTurn[];
  loading: boolean;
  sending: boolean;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent) => Promise<void>;
  onQuickAsk: (prompt: string) => void;
  error: string;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, loading, sending]);

  return (
    <div className="chat-view">
      <div className="chat-scroll">
        {turns.length === 0 ? (
          <div className="chat-empty">
            <p className="chat-empty-title">今天想查哪家机厅？</p>
            <p className="chat-empty-subtitle">你可以直接提问，也可以先点一个预设问题。</p>
            <div className="chat-quick-grid">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="quick-chip"
                  onClick={() => onQuickAsk(prompt)}
                  disabled={sending}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="chat-message-list">
            {turns.map((turn, index) => (
              <li key={`${turn.created_at}-${index}`} className={`chat-message ${turn.role}`}>
                <div className="chat-bubble">
                  <p>{turn.content}</p>
                  <small>{formatTimeLabel(turn.created_at)}</small>
                </div>
              </li>
            ))}
          </ul>
        )}

        {loading ? <p className="chat-loading">加载会话中...</p> : null}
        <div ref={endRef} />
      </div>

      {error ? <div className="chat-error">{error}</div> : null}

      <form className="chat-composer" onSubmit={(event) => void onSubmit(event)}>
        <input
          value={inputValue}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="尽管问，带图也行"
          disabled={sending}
        />
        <button type="submit" disabled={sending || inputValue.trim().length === 0}>
          {sending ? "发送中..." : "发送"}
        </button>
      </form>
    </div>
  );
}

export function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatHistoryTurn[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [turnsLoading, setTurnsLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [chatError, setChatError] = useState("");

  const activeSession = useMemo(
    () => sessions.find((session) => session.session_id === activeSessionId) ?? null,
    [sessions, activeSessionId]
  );

  async function loadSessionList(preferredSessionId?: string) {
    setSessionsLoading(true);
    try {
      const rows = await listChatSessions(60);
      setSessions(rows);
      if (!rows.length) {
        setActiveSessionId(null);
        setTurns([]);
        return;
      }
      const targetId =
        preferredSessionId && rows.some((item) => item.session_id === preferredSessionId)
          ? preferredSessionId
          : activeSessionId && rows.some((item) => item.session_id === activeSessionId)
            ? activeSessionId
            : rows[0].session_id;
      if (targetId && targetId !== activeSessionId) {
        await loadSession(targetId);
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "加载会话列表失败");
    } finally {
      setSessionsLoading(false);
    }
  }

  async function loadSession(sessionId: string) {
    setTurnsLoading(true);
    setChatError("");
    try {
      const detail = await getChatSession(sessionId);
      setActiveSessionId(sessionId);
      setTurns(toVisibleTurns(detail.turns));
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "加载会话失败");
    } finally {
      setTurnsLoading(false);
    }
  }

  useEffect(() => {
    void loadSessionList();
  }, []);

  function openChatView() {
    setViewMode("chat");
    setSidebarOpen(false);
  }

  function openArcadesView() {
    setViewMode("arcades");
    setSidebarOpen(false);
  }

  function startNewSession() {
    setViewMode("chat");
    setActiveSessionId(null);
    setTurns([]);
    setInputValue("");
    setChatError("");
    setSidebarOpen(false);
  }

  async function submitChat(event: FormEvent) {
    event.preventDefault();
    const message = inputValue.trim();
    if (!message || sending) {
      return;
    }

    setSending(true);
    setChatError("");
    setInputValue("");

    try {
      const response = await sendChat({
        session_id: activeSessionId || undefined,
        message,
        page_size: 5
      });
      await loadSession(response.session_id);
      await loadSessionList(response.session_id);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "发送失败");
      setInputValue(message);
    } finally {
      setSending(false);
    }
  }

  function quickAsk(prompt: string) {
    setInputValue(prompt);
    setViewMode("chat");
    setSidebarOpen(false);
  }

  async function removeSession(sessionId: string) {
    if (deletingSessionId || sending) {
      return;
    }
    const ok = window.confirm("确认删除这个历史会话吗？");
    if (!ok) {
      return;
    }
    setDeletingSessionId(sessionId);
    setChatError("");
    try {
      await deleteChatSession(sessionId);
      const isActive = activeSessionId === sessionId;
      if (isActive) {
        setActiveSessionId(null);
        setTurns([]);
      }
      await loadSessionList(isActive ? undefined : activeSessionId || undefined);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "删除会话失败");
    } finally {
      setDeletingSessionId(null);
    }
  }

  return (
    <div className="app-shell">
      <aside className={`app-sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <div className="sidebar-top">
          <h1>Arcadegent</h1>
          <button type="button" className="sidebar-new" onClick={startNewSession}>
            + 新建会话
          </button>
        </div>

        <nav className="sidebar-nav">
          <button
            type="button"
            className={`sidebar-nav-btn ${viewMode === "chat" ? "is-active" : ""}`}
            onClick={openChatView}
          >
            Agent 对话
          </button>
          <button
            type="button"
            className={`sidebar-nav-btn ${viewMode === "arcades" ? "is-active" : ""}`}
            onClick={openArcadesView}
          >
            机厅检索
          </button>
        </nav>

        <div className="sidebar-history-head">
          <strong>历史会话</strong>
          <button type="button" onClick={() => void loadSessionList(activeSessionId || undefined)} disabled={sessionsLoading}>
            刷新
          </button>
        </div>

        <ul className="sidebar-history-list">
          {sessionsLoading ? <li className="sidebar-empty">会话加载中...</li> : null}
          {!sessionsLoading && sessions.length === 0 ? <li className="sidebar-empty">暂无历史会话</li> : null}
          {!sessionsLoading
            ? sessions.map((item) => (
                <SidebarSessionItem
                  key={item.session_id}
                  item={item}
                  active={item.session_id === activeSessionId}
                  deleting={deletingSessionId === item.session_id}
                  onClick={() => {
                    setViewMode("chat");
                    void loadSession(item.session_id);
                    setSidebarOpen(false);
                  }}
                  onDelete={() => void removeSession(item.session_id)}
                />
              ))
            : null}
        </ul>
      </aside>

      <button
        type="button"
        className={`sidebar-backdrop ${sidebarOpen ? "is-open" : ""}`}
        aria-label="关闭侧边栏"
        onClick={() => setSidebarOpen(false)}
      />

      <main className="app-main">
        <header className="topbar">
          <button type="button" className="menu-btn" onClick={() => setSidebarOpen((value) => !value)}>
            ☰
          </button>
          <div>
            <h2>{viewMode === "chat" ? "Agent 对话" : "机厅检索"}</h2>
            <p>{activeSession ? `最近更新 ${formatTimeLabel(activeSession.updated_at)}` : ""}</p>
          </div>
        </header>

        {viewMode === "chat" ? (
          <ChatPanel
            turns={turns}
            loading={turnsLoading}
            sending={sending}
            inputValue={inputValue}
            onInputChange={setInputValue}
            onSubmit={submitChat}
            onQuickAsk={quickAsk}
            error={chatError}
          />
        ) : (
          <ArcadeBrowser />
        )}
      </main>
    </div>
  );
}
