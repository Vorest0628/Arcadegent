import { formatTimeLabel } from "../lib/chatStream";

type AppTopbarProps = {
  viewMode: "chat" | "arcades";
  activeSessionUpdatedAt: string | null;
  onToggleSidebar: () => void;
};

export function AppTopbar({ viewMode, activeSessionUpdatedAt, onToggleSidebar }: AppTopbarProps) {
  return (
    <header className="topbar">
      <button type="button" className="menu-btn" onClick={onToggleSidebar}>
        ☰
      </button>
      <div>
        <h2>{viewMode === "chat" ? "Agent 对话" : "机厅检索"}</h2>
        <p>{activeSessionUpdatedAt ? `最近更新 ${formatTimeLabel(activeSessionUpdatedAt)}` : ""}</p>
      </div>
    </header>
  );
}
