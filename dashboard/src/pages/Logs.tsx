import { LogViewer } from "../components/LogViewer";

export default function Logs() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>Logs del Sistema</h1>
      <LogViewer />
    </div>
  );
}
