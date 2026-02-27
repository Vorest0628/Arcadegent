import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  buildChatStreamUrl,
  deleteChatSession,
  getChatSession,
  listChatSessions,
  sendChat
} from "./api/client";
import { ArcadeBrowser } from "./components/ArcadeBrowser";
import type {
  ChatHistoryTurn,
  ChatSessionSummary,
  ChatStreamEnvelope,
  ChatStreamEventName
} from "./types";

type ViewMode = "chat" | "arcades";

const QUICK_PROMPTS = [
  "帮我找北京适合下班后去的机厅",
  "我在广州，推荐几家有 maimai 的店",
  "给我一条从当前位置到最近机厅的路线建议"
];

const STREAM_EVENT_NAMES: ChatStreamEventName[] = [
  "session.started",
  "subagent.changed",
  "assistant.token",
  "tool.started",
  "tool.progress",
  "tool.completed",
  "tool.failed",
  "navigation.route_ready",
  "assistant.completed",
  "session.failed"
];

const SUBAGENT_LABEL: Record<string, string> = {
  intent_router: "意图路由",
  search_agent: "检索阶段",
  navigation_agent: "导航阶段",
  summary_agent: "总结阶段"
};

const TOOL_LABEL: Record<string, string> = {
  db_query_tool: "数据检索",
  geo_resolve_tool: "位置解析",
  route_plan_tool: "路线规划",
  summary_tool: "结果总结",
  select_next_subagent: "阶段选择"
};

type StreamProgressItem = {
  id: number;
  event: ChatStreamEventName;
  text: string;
  at: string;
};

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

function formatSubagentLabel(subagent: string | null): string {
  if (!subagent) {
    return "等待阶段信号";
  }
  return SUBAGENT_LABEL[subagent] ?? subagent;
}

function formatToolLabel(toolName: string | undefined): string {
  if (!toolName) {
    return "工具";
  }
  return TOOL_LABEL[toolName] ?? toolName;
}

function toProgressText(envelope: ChatStreamEnvelope): string {
  const toolNameRaw = envelope.data.tool;
  const toolName = typeof toolNameRaw === "string" ? toolNameRaw : undefined;
  if (envelope.event === "session.started") {
    return "会话开始";
  }
  if (envelope.event === "subagent.changed") {
    const nextRaw = envelope.data.to_subagent ?? envelope.data.active_subagent;
    const next = typeof nextRaw === "string" ? nextRaw : null;
    return `切换到 ${formatSubagentLabel(next)}`;
  }
  if (envelope.event === "assistant.token") {
    return "正在生成回复";
  }
  if (envelope.event === "tool.started") {
    return `${formatToolLabel(toolName)} 执行中`;
  }
  if (envelope.event === "tool.progress") {
    return `${formatToolLabel(toolName)} 处理中`;
  }
  if (envelope.event === "tool.completed") {
    return `${formatToolLabel(toolName)} 已完成`;
  }
  if (envelope.event === "tool.failed") {
    return `${formatToolLabel(toolName)} 失败`;
  }
  if (envelope.event === "navigation.route_ready") {
    return "路线已生成";
  }
  if (envelope.event === "assistant.completed") {
    return "最终回复已生成";
  }
  if (envelope.event === "session.failed") {
    return "会话执行失败";
  }
  return envelope.event;
}

function makeSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `s_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
  }
  return `s_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
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
  error,
  streamConnected,
  activeSubagent,
  streamItems
}: {
  turns: ChatHistoryTurn[];
  loading: boolean;
  sending: boolean;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent) => Promise<void>;
  onQuickAsk: (prompt: string) => void;
  error: string;
  streamConnected: boolean;
  activeSubagent: string | null;
  streamItems: StreamProgressItem[];
}) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, loading, sending, streamItems]);

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
              <li
                key={`${turn.created_at}-${index}`}
                className={`chat-message ${turn.role}`}
                style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
              >
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

      {sending || streamItems.length ? (
        <section className={`chat-stage-board ${streamConnected ? "is-live" : ""}`}>
          <div className="chat-stage-head">
            <span className={`chat-stage-dot ${streamConnected ? "is-live" : ""}`} />
            <strong>执行阶段</strong>
            <small>{sending ? (streamConnected ? "实时同步中" : "连接中...") : "本轮已结束"}</small>
          </div>
          <p className="chat-stage-current">{formatSubagentLabel(activeSubagent)}</p>
          <ul className="chat-stage-list">
            {streamItems.length === 0 ? (
              <li className="chat-stage-empty">等待阶段事件...</li>
            ) : (
              streamItems.map((item) => (
                <li key={`${item.id}-${item.event}`}>
                  <span>{item.text}</span>
                  <small>{formatTimeLabel(item.at)}</small>
                </li>
              ))
            )}
          </ul>
        </section>
      ) : null}

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
  const [streamConnected, setStreamConnected] = useState(false);
  const [activeSubagent, setActiveSubagent] = useState<string | null>(null);
  const [streamItems, setStreamItems] = useState<StreamProgressItem[]>([]);

  const streamRef = useRef<EventSource | null>(null);

  const activeSession = useMemo(
    () => sessions.find((session) => session.session_id === activeSessionId) ?? null,
    [sessions, activeSessionId]
  );

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    setStreamConnected(false);
  }, []);

  const pushStreamEnvelope = useCallback((envelope: ChatStreamEnvelope) => {
    setStreamItems((previous) => {
      const next: StreamProgressItem = {
        id: envelope.id,
        event: envelope.event,
        text: toProgressText(envelope),
        at: envelope.at
      };
      const filtered = previous.filter((item) => item.id !== envelope.id);
      return [...filtered.slice(-7), next];
    });
  }, []);

  const startStream = useCallback(
    (sessionId: string) => {
      stopStream();
      setStreamItems([]);
      setActiveSubagent(null);
      const source = new EventSource(buildChatStreamUrl(sessionId));
      streamRef.current = source;

      const handleEvent = (raw: Event) => {
        const message = raw as MessageEvent<string>;
        if (!message.data) {
          return;
        }
        let parsed: unknown;
        try {
          parsed = JSON.parse(message.data);
        } catch {
          return;
        }
        if (!parsed || typeof parsed !== "object") {
          return;
        }
        const envelope = parsed as ChatStreamEnvelope;
        if (typeof envelope.id !== "number") {
          return;
        }
        if (typeof envelope.event !== "string") {
          return;
        }
        if (typeof envelope.data !== "object" || envelope.data === null) {
          return;
        }

        if (envelope.event === "session.started") {
          const current = envelope.data.active_subagent;
          if (typeof current === "string" && current) {
            setActiveSubagent(current);
          }
        }
        if (envelope.event === "subagent.changed") {
          const next = envelope.data.to_subagent ?? envelope.data.active_subagent;
          if (typeof next === "string" && next) {
            setActiveSubagent(next);
          }
        }

        pushStreamEnvelope(envelope);

        if (envelope.event === "assistant.completed" || envelope.event === "session.failed") {
          stopStream();
        }
      };

      source.onopen = () => {
        setStreamConnected(true);
      };
      source.onerror = () => {
        setStreamConnected(false);
      };
      STREAM_EVENT_NAMES.forEach((eventName) => {
        source.addEventListener(eventName, handleEvent as EventListener);
      });
    },
    [pushStreamEnvelope, stopStream]
  );

  async function loadSessionList(preferredSessionId?: string) {
    setSessionsLoading(true);
    try {
      const rows = await listChatSessions(60);
      setSessions(rows);
      if (!rows.length) {
        setActiveSessionId(null);
        setTurns([]);
        setActiveSubagent(null);
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
      setActiveSubagent(detail.active_subagent || null);
      if (!sending) {
        setStreamItems([]);
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "加载会话失败");
    } finally {
      setTurnsLoading(false);
    }
  }

  useEffect(() => {
    void loadSessionList();
  }, []);

  useEffect(() => {
    return () => {
      stopStream();
    };
  }, [stopStream]);

  function openChatView() {
    setViewMode("chat");
    setSidebarOpen(false);
  }

  function openArcadesView() {
    setViewMode("arcades");
    setSidebarOpen(false);
  }

  function startNewSession() {
    stopStream();
    setViewMode("chat");
    setActiveSessionId(null);
    setTurns([]);
    setInputValue("");
    setChatError("");
    setSidebarOpen(false);
    setActiveSubagent(null);
    setStreamItems([]);
  }

  async function submitChat(event: FormEvent) {
    event.preventDefault();
    const message = inputValue.trim();
    if (!message || sending) {
      return;
    }

    const sessionId = activeSessionId || makeSessionId();

    setSending(true);
    setChatError("");
    setInputValue("");
    setActiveSessionId(sessionId);
    startStream(sessionId);

    try {
      const response = await sendChat({
        session_id: sessionId,
        message,
        page_size: 5
      });
      await loadSession(response.session_id);
      await loadSessionList(response.session_id);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "发送失败");
      setInputValue(message);
      setStreamItems([]);
      setActiveSubagent(null);
    } finally {
      setSending(false);
      stopStream();
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
        setActiveSubagent(null);
        setStreamItems([]);
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
          <button
            type="button"
            onClick={() => void loadSessionList(activeSessionId || undefined)}
            disabled={sessionsLoading}
          >
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
                    stopStream();
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
            streamConnected={streamConnected}
            activeSubagent={activeSubagent}
            streamItems={streamItems}
          />
        ) : (
          <ArcadeBrowser />
        )}
      </main>
    </div>
  );
}
