import { useEffect, useState } from "react";
import { fetchTechs, getBlueFolderCredentials, setBlueFolderCredentials } from "../api/client";

export default function TechSelector({ value, onChange }) {
  const initialCreds = getBlueFolderCredentials();
  const [techs, setTechs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [bfApiKey, setBfApiKey] = useState(initialCreds.apiKey || "");
  const [bfAccount, setBfAccount] = useState(initialCreds.account || "");
  const [showCreds, setShowCreds] = useState(!(initialCreds.apiKey && initialCreds.account));

  const loadTechs = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchTechs({ apiKey: bfApiKey.trim(), account: bfAccount.trim() });
      setTechs(data);
    } catch (e) {
      const msg = e?.response?.data || e?.message || "";
      setError(`Unable to load technicians (check BlueFolder credentials). ${msg}`);
      setShowCreds(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!showCreds) {
      loadTechs();
    }
  }, [showCreds]);

  const saveCreds = () => {
    const key = bfApiKey.trim();
    const account = bfAccount.trim();
    if (!key || !account) {
      setError("Enter account and API key.");
      return;
    }
    setBlueFolderCredentials(key, account);
    setShowCreds(false);
    setError("");
    loadTechs();
  };

  if (showCreds) {
    return (
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <input
          type="text"
          placeholder="Account (subdomain)"
          value={bfAccount}
          onChange={(e) => setBfAccount(e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #475569", background: "rgba(51,65,85,0.4)", color: "#e2e8f0" }}
        />
        <input
          type="password"
          placeholder="BlueFolder API key"
          value={bfApiKey}
          onChange={(e) => setBfApiKey(e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #475569", background: "rgba(51,65,85,0.4)", color: "#e2e8f0", minWidth: 200 }}
        />
        <button
          onClick={saveCreds}
          style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #3b82f6", background: "#2563eb", color: "#e2e8f0", cursor: "pointer", fontSize: 12 }}
        >
          Save & load techs
        </button>
        {error && <span style={{ color: "#f87171", fontSize: 12 }}>{error}</span>}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <select
        value={value || ""}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={loading || techs.length === 0}
        style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #475569", background: "rgba(51,65,85,0.5)", color: "#e2e8f0" }}
      >
        <option value="">{techs.length ? "Select technician…" : "Enter creds to load techs"}</option>
        {techs.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
      <button
        onClick={loadTechs}
        disabled={loading}
        style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #475569", background: "rgba(51,65,85,0.4)", color: "#e2e8f0", cursor: "pointer", fontSize: 12 }}
      >
        Reload techs
      </button>
      <button
        onClick={() => setShowCreds(true)}
        style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #475569", background: "rgba(51,65,85,0.4)", color: "#e2e8f0", cursor: "pointer", fontSize: 12 }}
      >
        Edit creds
      </button>
      {loading && <span style={{ color: "#cbd5e1", fontSize: 12 }}>Loading…</span>}
      {error && <span style={{ color: "#f87171", fontSize: 12 }}>{error}</span>}
    </div>
  );
}
