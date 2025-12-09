import { useState, useEffect, useRef } from "react";
import { Command } from "@tauri-apps/plugin-shell";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  Settings,
  LayoutDashboard,
  Search,
  Smartphone
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import velocityLogo from "./assets/logo.png";
import "./App.css";

interface HistoryItem {
  timestamp: string;
  type: "text" | "url" | "image";
  preview: string;
  content: string;
}

interface ServerStatus {
  status: string;
  version: string;
  ip: string;
  hostname: string;
  port: number;
  token: string;
  clients: number;
  requests: number;
}

function App() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "history" | "qr" | "settings">("dashboard");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null);
  const [connectionStatus, setConnectionStatus] = useState("Connecting...");
  const [showToken, setShowToken] = useState(false);
  const [serverEnabled, setServerEnabled] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [updateInfo, setUpdateInfo] = useState<{ available: boolean; latestVersion: string; currentVersion: string } | null>(null);
  const [autostart, setAutostart] = useState(false);

  // Store child process reference
  const childRef = useRef<{ pid: number; kill: () => Promise<void> } | null>(null);

  // Start sidecar function
  const startServer = async () => {
    try {
      console.log("Attempting to spawn sidecar...");
      setConnectionStatus("Starting server...");
      const command = Command.sidecar("server");
      const child = await command.spawn();
      childRef.current = child;
      console.log("Sidecar spawned with PID:", child.pid);
      setConnectionStatus("Connecting...");
      setServerEnabled(true);
    } catch (err: unknown) {
      console.error("Failed to spawn sidecar:", err);
      const errorMsg = err instanceof Error ? err.message : String(err);
      setConnectionStatus("Spawn Error: " + errorMsg.substring(0, 30));
      setServerEnabled(false);
    }
  };

  // Stop sidecar function
  const stopServer = async () => {
    console.log("Stopping server...");
    try {
      // Kill by process ref first
      if (childRef.current) {
        try {
          await childRef.current.kill();
        } catch (e) {
          console.log("child.kill() failed, trying pkill...", e);
        }
        childRef.current = null;
      }

      // Also kill any server process using pkill with multiple patterns
      try {
        // Kill debug server (target/debug/server)
        const killDebug = Command.create("pkill", ["-9", "-f", "target/debug/server"]);
        await killDebug.execute();
        console.log("Killed debug server");
      } catch (e) {
        console.log("No debug server to kill");
      }

      try {
        // Kill release server (server-x86_64)
        const killRelease = Command.create("pkill", ["-9", "-f", "server-x86_64"]);
        await killRelease.execute();
        console.log("Killed release server");
      } catch (e) {
        console.log("No release server to kill");
      }

      setServerEnabled(false);
      setConnectionStatus("Server stopped");
      setServerStatus(null);
    } catch (err) {
      console.error("Failed to stop sidecar:", err);
    }
  };

  // Toggle server on/off
  const toggleServer = async () => {
    console.log("Toggle clicked, serverEnabled:", serverEnabled);
    if (serverEnabled) {
      console.log("Stopping server...");
      await stopServer();
    } else {
      console.log("Starting server...");
      await startServer();
    }
  };

  // Spawn Sidecar on Mount
  useEffect(() => {
    startServer();
  }, []);

  // Poll History & Status
  useEffect(() => {
    // Don't poll if server is disabled
    if (!serverEnabled) {
      return;
    }

    const fetchData = async () => {
      try {
        const statusRes = await fetch("http://localhost:8080/status");
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setServerStatus(statusData);
          setConnectionStatus("Connected");

          // Fetch history with token from status
          if (statusData.token) {
            const historyRes = await fetch(`http://localhost:8080/history?limit=50&token=${statusData.token}`);
            if (historyRes.ok) {
              const data = await historyRes.json();
              setHistory(data.items || []);
            }
          }
        } else {
          setConnectionStatus("Reconnecting...");
        }
      } catch (e) {
        console.error("Fetch error:", e);
        setConnectionStatus("Reconnecting...");
      }
    };

    const interval = setInterval(fetchData, 500); // Poll every 500ms for real-time feel
    fetchData();
    return () => clearInterval(interval);
  }, [serverEnabled]); // Re-run when serverEnabled changes

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Open file using xdg-open (more reliable on Linux)
  const openFile = async (path: string) => {
    try {
      const cmd = Command.create("xdg-open", [path]);
      await cmd.execute();
    } catch (err) {
      console.error("Failed to open file:", err);
    }
  };

  // Clear all history (with server-side deletion)
  const clearHistory = async () => {
    if (!serverStatus?.token) return;

    try {
      const response = await fetch(`http://localhost:8080/history?token=${serverStatus.token}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        // Smooth clear with animation
        setHistory([]);
        setSearchQuery("");
      }
    } catch (err) {
      console.error("Failed to clear history:", err);
    }
  };

  // Filter history by search query
  const filteredHistory = history.filter(item => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      item.content?.toLowerCase().includes(query) ||
      item.preview?.toLowerCase().includes(query) ||
      item.type?.toLowerCase().includes(query)
    );
  });

  // Check for updates from GitHub releases
  const CURRENT_VERSION = "2.0.0"; // Match your release version

  // Compare semantic versions: returns true if a > b
  const isNewerVersion = (a: string, b: string): boolean => {
    const partsA = a.split('.').map(Number);
    const partsB = b.split('.').map(Number);
    for (let i = 0; i < Math.max(partsA.length, partsB.length); i++) {
      const numA = partsA[i] || 0;
      const numB = partsB[i] || 0;
      if (numA > numB) return true;
      if (numA < numB) return false;
    }
    return false;
  };

  const checkForUpdates = async () => {
    try {
      const response = await fetch("https://api.github.com/repos/Trex099/Velocity-Bridge/releases/latest");
      if (response.ok) {
        const data = await response.json();
        const latestVersion = data.tag_name?.replace(/^v/, "") || "";
        // Only show update if GitHub version is actually greater
        if (latestVersion && isNewerVersion(latestVersion, CURRENT_VERSION)) {
          setUpdateInfo({
            available: true,
            latestVersion,
            currentVersion: CURRENT_VERSION
          });
        } else {
          setUpdateInfo({
            available: false,
            latestVersion: latestVersion || CURRENT_VERSION,
            currentVersion: CURRENT_VERSION
          });
        }
      }
    } catch (err) {
      console.error("Failed to check for updates:", err);
    }
  };

  // Check for updates on startup
  useEffect(() => {
    checkForUpdates();
    checkAutostart();
  }, []);

  // Check if autostart is enabled
  const checkAutostart = async () => {
    try {
      const cmd = Command.create("bash", ["-c", "test -f $HOME/.config/autostart/velocity-bridge.desktop"]);
      const result = await cmd.execute();
      setAutostart(result.code === 0);
    } catch {
      setAutostart(false);
    }
  };

  // Toggle autostart
  const toggleAutostart = async () => {
    const desktopEntry = `[Desktop Entry]
Type=Application
Name=Velocity Bridge
Exec=velocity-bridge
Icon=velocity-bridge
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true`;

    try {
      if (autostart) {
        // Remove autostart
        await Command.create("bash", ["-c", "rm -f $HOME/.config/autostart/velocity-bridge.desktop"]).execute();
        setAutostart(false);
      } else {
        // Create autostart directory and file
        await Command.create("bash", ["-c", "mkdir -p $HOME/.config/autostart"]).execute();
        await Command.create("bash", ["-c", `echo '${desktopEntry}' > "$HOME/.config/autostart/velocity-bridge.desktop"`]).execute();
        setAutostart(true);
      }
    } catch (err) {
      console.error("Failed to toggle autostart:", err);
    }
  };

  const isConnected = connectionStatus === "Connected";

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo-area">
          <img src={velocityLogo} alt="Velocity" className="logo-icon" style={{ width: '28px', height: '28px' }} />
          <span className="logo-text">Velocity</span>
        </div>

        <nav className="nav-menu">
          <button
            className={"nav-item" + (activeTab === "dashboard" ? " active" : "")}
            onClick={() => setActiveTab("dashboard")}
          >
            <LayoutDashboard size={20} />
            <span>Dashboard</span>
          </button>

          <button
            className={"nav-item" + (activeTab === "history" ? " active" : "")}
            onClick={() => setActiveTab("history")}
          >
            <Search size={20} />
            <span>History</span>
          </button>

          <button
            className={"nav-item" + (activeTab === "qr" ? " active" : "")}
            onClick={() => setActiveTab("qr")}
          >
            <Smartphone size={20} />
            <span>iOS Setup</span>
          </button>

          <button
            className={"nav-item" + (activeTab === "settings" ? " active" : "")}
            onClick={() => setActiveTab("settings")}
          >
            <Settings size={20} />
            <span>Settings</span>
          </button>
        </nav>

        <div className="status-area">
          <div className={"status-indicator " + (isConnected ? "online" : "offline")}></div>
          <span className="status-text">{connectionStatus}</span>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">

        {/* Update Available Banner */}
        {updateInfo?.available && (
          <div style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            padding: '12px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            fontSize: '14px'
          }}>
            <span>
              🎉 <strong>Update available!</strong> Version {updateInfo.latestVersion} is now available (you have {updateInfo.currentVersion})
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => openUrl("https://github.com/Trex099/Velocity-Bridge/releases/latest")}
                style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: 'white', color: '#667eea', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
              >
                Download
              </button>
              <button
                onClick={() => setUpdateInfo(null)}
                style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.5)', background: 'transparent', color: 'white', cursor: 'pointer', fontSize: '13px' }}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Dashboard View */}
        {activeTab === "dashboard" && (
          <div className="view-dashboard">
            <header className="view-header">
              <h1>Dashboard</h1>
            </header>

            {/* System Status Card */}
            <div className="dashboard-card">
              <div className="card-header">
                <span className="card-label">SYSTEM STATUS</span>
                <button className="status-toggle" onClick={toggleServer}>
                  <span className={"toggle-indicator " + (serverEnabled ? "online" : "offline")}></span>
                  <span>{serverEnabled ? "Online" : "Offline"}</span>
                </button>
              </div>
              <div className="status-display">
                <span className={"status-dot " + (serverEnabled && isConnected ? "active" : "")}></span>
                <span className="status-label">{serverEnabled ? (isConnected ? "Active" : "Starting...") : "Stopped"}</span>
              </div>
            </div>

            {/* Connection Link Card */}
            <div className="dashboard-card">
              <div className="card-header">
                <span className="card-label">CONNECTION LINK</span>
              </div>

              <div className="connection-field">
                <label>Network Address (use hostname.local or IP)</label>
                <div className="field-row">
                  <input
                    type="text"
                    readOnly
                    value={"http://" + (serverStatus?.hostname || serverStatus?.ip || "...") + ":8080"}
                    className="dark-input"
                  />
                  <button
                    className="field-btn"
                    onClick={() => navigator.clipboard.writeText("http://" + (serverStatus?.hostname || serverStatus?.ip) + ":8080")}
                  >
                    Copy
                  </button>
                </div>
              </div>

              <div className="connection-field">
                <label>Access Token</label>
                <div className="field-row">
                  <input
                    type={showToken ? "text" : "password"}
                    readOnly
                    value={serverStatus?.token || "Not Configured"}
                    className="dark-input"
                  />
                  <button
                    className="field-btn"
                    onClick={() => setShowToken(!showToken)}
                  >
                    {showToken ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* History View */}
        {activeTab === "history" && (
          <div className="view-history">
            <header className="view-header">
              <h1>Clipboard History</h1>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <div className="search-bar">
                  <Search size={16} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Search history..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <button
                  onClick={clearHistory}
                  style={{ padding: '8px 16px', borderRadius: '8px', border: 'none', background: '#ff4444', color: 'white', cursor: 'pointer', fontSize: '14px', fontWeight: '500' }}
                >
                  Clear All
                </button>
              </div>
            </header>

            <div className="history-list">
              {filteredHistory.length === 0 ? (
                <div className="empty-state">
                  <span>{searchQuery ? 'No matching items' : 'No items found'}</span>
                </div>
              ) : (
                filteredHistory.map((item, i) => {
                  // Detect if content is a URL
                  const isUrl = item.type === "url" || (item.content && (item.content.startsWith("http://") || item.content.startsWith("https://")));
                  const isImage = item.type === "image";

                  return (
                    <div key={i} className="history-item">
                      <div className="item-header">
                        <span className="item-type">
                          {isImage ? "🖼️ IMAGE" : isUrl ? "🔗 URL" : "📄 TEXT"}
                        </span>
                        <span className="item-time">
                          {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div className="item-content">
                        {isImage ? (
                          <span style={{ color: '#666', fontSize: '13px' }}>
                            {item.preview?.replace(/^🖼️\s*/, '') || 'Image saved'}
                          </span>
                        ) : isUrl ? (
                          <a href={item.content} target="_blank" rel="noopener noreferrer" style={{ color: '#007AFF', textDecoration: 'underline' }}>
                            {item.preview || item.content}
                          </a>
                        ) : (
                          item.preview || item.content
                        )}
                      </div>
                      <div className="item-actions" style={{ gap: '8px' }}>
                        {isImage ? (
                          <button onClick={() => copyToClipboard(item.content)}>Copy Path</button>
                        ) : (
                          <button onClick={() => copyToClipboard(item.content)}>Copy</button>
                        )}
                        {isUrl && (
                          <button onClick={() => openUrl(item.content)}>Open</button>
                        )}
                        {isImage && (
                          <button onClick={() => openFile(item.content)}>Open</button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )
        }

        {/* QR Codes View */}
        {
          activeTab === "qr" && (
            <div className="view-qr" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 20px', textAlign: 'center' }}>
              <h1 style={{ fontSize: '28px', fontWeight: '700', marginBottom: '8px' }}>📱 iOS Setup</h1>
              <p style={{ color: '#666', marginBottom: '40px', fontSize: '15px' }}>
                Scan these QR codes with your iPhone Camera to install the Shortcuts
              </p>

              <div style={{ display: 'flex', flexDirection: 'row', gap: '48px', marginBottom: '24px', flexWrap: 'wrap', justifyContent: 'center' }}>
                <div style={{ background: '#f8f9fa', borderRadius: '16px', padding: '32px 40px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '20px', color: '#333' }}>📋 Text Clipboard</h4>
                  <QRCodeSVG
                    value="https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
                    size={140}
                    level="M"
                  />
                  <span style={{ fontSize: '12px', color: '#888', marginTop: '16px' }}>Copy text from iPhone to Linux</span>
                </div>
                <div style={{ background: '#f8f9fa', borderRadius: '16px', padding: '32px 40px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '20px', color: '#333' }}>🖼️ Image Clipboard</h4>
                  <QRCodeSVG
                    value="https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
                    size={140}
                    level="M"
                  />
                  <span style={{ fontSize: '12px', color: '#888', marginTop: '16px' }}>Send photos from iPhone to Linux</span>
                </div>
              </div>

              <div style={{ background: '#f5f5f7', borderRadius: '12px', padding: '24px 32px', maxWidth: '480px', textAlign: 'left' }}>
                <h3 style={{ margin: '0 0 16px 0', fontSize: '15px', fontWeight: '600' }}>Setup Instructions</h3>
                <ol style={{ margin: 0, paddingLeft: '20px', color: '#555', lineHeight: '2', fontSize: '14px' }}>
                  <li>Scan a QR code with your iPhone Camera</li>
                  <li>Tap the notification to open in Shortcuts</li>
                  <li>Tap "Add Shortcut"</li>
                  <li>Enter your Server IP and Token</li>
                  <li>Use Share menu to send content!</li>
                </ol>

                <div style={{ marginTop: '20px', padding: '12px 16px', background: '#e8f4fd', borderRadius: '8px', fontSize: '13px' }}>
                  <strong>💡 Pro Tip:</strong> Set up <strong>Back Tap</strong> for instant access!
                  <div style={{ marginTop: '8px', color: '#555' }}>
                    Settings → Accessibility → Touch → Back Tap
                    <br />
                    • <strong>Double Tap</strong> → Text Clipboard shortcut
                    <br />
                    • <strong>Triple Tap</strong> → Image Clipboard shortcut
                  </div>
                </div>
              </div>
            </div>
          )
        }

        {/* Settings View */}
        {
          activeTab === "settings" && (
            <div className="view-settings">
              <header className="view-header">
                <h1>Settings</h1>
              </header>

              <div className="settings-section">
                <h2>General</h2>
                <div className="setting-item">
                  <label>Start at Login</label>
                  <input
                    type="checkbox"
                    checked={autostart}
                    onChange={toggleAutostart}
                  />
                </div>
                <div className="setting-item">
                  <label>Notifications</label>
                  <input type="checkbox" defaultChecked />
                </div>
              </div>

              <div className="settings-section">
                <h2>Security</h2>
                <div className="setting-item">
                  <label>Security Token</label>
                  <div className="token-field">
                    <input
                      type={showToken ? "text" : "password"}
                      value={serverStatus?.token || ""}
                      disabled
                    />
                    <button onClick={() => setShowToken(!showToken)}>
                      {showToken ? "Hide" : "Show"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="settings-section">
                <h2>Updates</h2>
                <div className="setting-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <label>Current Version</label>
                    <span style={{ fontFamily: 'monospace', background: '#f0f0f0', padding: '4px 8px', borderRadius: '4px' }}>v{CURRENT_VERSION}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button
                      onClick={checkForUpdates}
                      style={{ padding: '8px 16px', borderRadius: '8px', border: 'none', background: '#007AFF', color: 'white', cursor: 'pointer', fontSize: '14px' }}
                    >
                      Check for Updates
                    </button>
                    {updateInfo && !updateInfo.available && (
                      <span style={{ color: '#22c55e', fontSize: '13px' }}>✓ You're up to date!</span>
                    )}
                  </div>
                </div>
              </div>

              {/* iOS Setup QR Codes Card */}
              <div className="dashboard-card">
                <div className="card-header">
                  <span className="card-label">iOS SETUP</span>
                  <Smartphone size={18} style={{ color: '#007AFF' }} />
                </div>
                <p style={{ fontSize: '13px', color: '#666', margin: '8px 0 16px' }}>
                  Scan with your iPhone Camera to install Shortcuts
                </p>

                <div className="qr-container">
                  <div className="qr-item">
                    <h4>📋 Text Clipboard</h4>
                    <QRCodeSVG
                      value="https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
                      size={120}
                      level="M"
                    />
                    <span className="qr-label">Copy text to Linux</span>
                  </div>
                  <div className="qr-item">
                    <h4>🖼️ Image Clipboard</h4>
                    <QRCodeSVG
                      value="https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
                      size={120}
                      level="M"
                    />
                    <span className="qr-label">Send photos to Linux</span>
                  </div>
                </div>

                <div style={{ background: '#f5f5f7', borderRadius: '8px', padding: '12px', marginTop: '16px' }}>
                  <p style={{ fontSize: '12px', color: '#666', margin: 0 }}>
                    <strong>Setup:</strong> 1. Scan QR  →  2. Add Shortcut  →  3. Enter IP & Token
                  </p>
                </div>
              </div>
            </div>
          )
        }

      </main >
    </div >
  );
}

export default App;
