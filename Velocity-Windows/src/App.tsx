import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { motion, AnimatePresence } from "framer-motion";
import { Command } from "@tauri-apps/plugin-shell";
import { openPath, openUrl } from "@tauri-apps/plugin-opener";

import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { enable, disable, isEnabled } from "@tauri-apps/plugin-autostart";
import {
  Settings,
  LayoutDashboard,
  Search,
  Smartphone,
  Download,
  RotateCcw,
  CheckCircle2
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import velocityLogo from "./assets/logo.png";
import Onboarding from "./components/Onboarding";
import "./App.css";

// iOS Shortcut URLs - update here if shortcuts are recreated
const SHORTCUT_IOS_TO_LINUX_URL = "https://www.icloud.com/shortcuts/4c4f2c081bb448fa9ff714a96a44103e";
const SHORTCUT_BIDIRECTIONAL_URL = "https://www.icloud.com/shortcuts/610688b5208c46499ce271bbfb07570a";

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
  install_method?: "appimage" | "native";
}

interface PortOwner {
  pid: number;
  process_name?: string | null;
}

const RESTART_DELAY_MS = 1500;
const DEFAULT_SERVER_PORT = 8080;

function App() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "history" | "qr" | "settings">("dashboard");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null);
  const [connectionStatus, setConnectionStatus] = useState("Connecting...");
  const [showToken, setShowToken] = useState(false);
  const [serverEnabled, setServerEnabled] = useState(true);
  const [serverPort, setServerPort] = useState(DEFAULT_SERVER_PORT);
  const [useManualConnection, setUseManualConnection] = useState(() => {
    return localStorage.getItem("velocityUseManualConnection") === "true";
  });
  const [manualAddress, setManualAddress] = useState(() => {
    return localStorage.getItem("velocityManualAddress") || "";
  });
  const [manualToken, setManualToken] = useState(() => {
    return localStorage.getItem("velocityManualToken") || "";
  });
  const [isSettingToken, setIsSettingToken] = useState(false);
  const [isSettingAddress, setIsSettingAddress] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [updateInfo, setUpdateInfo] = useState<{ available: boolean; latestVersion: string; currentVersion: string; installType?: string; updaterHandle?: any } | null>(null);
  const [updateStatus, setUpdateStatus] = useState<string>("");
  const [isDownloading, setIsDownloading] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [autostart, setAutostart] = useState(false);
  const [isTogglingAutostart, setIsTogglingAutostart] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [startMinimized, setStartMinimized] = useState(false);
  const [isTogglingNotifications, setIsTogglingNotifications] = useState(false);
  const [isTogglingStartMinimized, setIsTogglingStartMinimized] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState<boolean | null>(null);
  const [isFlashActive, setIsFlashActive] = useState(false);
  const [firewallNeedsRule, setFirewallNeedsRule] = useState<boolean | null>(null);

  const handleOnboardingComplete = () => {
    // 1. Instant Flash
    setIsFlashActive(true);

    // 2. Switch components while screen is white
    setTimeout(() => {
      invoke("set_onboarding_completed", { completed: true }).catch((err) => {
        console.error("Failed to persist onboarding state:", err);
      });
      setShowOnboarding(false);

      // 3. Fade out the flash smoothly
      setTimeout(() => {
        setIsFlashActive(false);
      }, 100);
    }, 400);
  };

  // Store child process reference
  const childRef = useRef<{ pid: number; kill: () => Promise<void> } | null>(null);
  const commandRef = useRef<any | null>(null);
  const restartTimerRef = useRef<number | null>(null);
  const isStartingRef = useRef(false);
  const isStoppingRef = useRef(false);
  const serverEnabledRef = useRef(serverEnabled);
  const serverPortRef = useRef(serverPort);

  useEffect(() => {
    serverEnabledRef.current = serverEnabled;
  }, [serverEnabled]);

  useEffect(() => {
    serverPortRef.current = serverPort;
  }, [serverPort]);

  useEffect(() => {
    localStorage.setItem("velocityUseManualConnection", String(useManualConnection));
  }, [useManualConnection]);

  useEffect(() => {
    localStorage.setItem("velocityManualAddress", manualAddress);
  }, [manualAddress]);

  useEffect(() => {
    localStorage.setItem("velocityManualToken", manualToken);
  }, [manualToken]);

  useEffect(() => {
    let isMounted = true;
    invoke<boolean>("get_onboarding_completed")
      .then((completed) => {
        if (isMounted) {
          setShowOnboarding(!completed);
        }
      })
      .catch(() => {
        if (isMounted) {
          setShowOnboarding(true);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    invoke<{ rule_present: boolean }>("get_firewall_status")
      .then((result) => setFirewallNeedsRule(!result.rule_present))
      .catch(() => setFirewallNeedsRule(false));
  }, []);

  const buildLocalServerUrl = (path = "") => `http://127.0.0.1:${serverPortRef.current}${path}`;
  const firewallPort = serverStatus?.port ?? serverPort;
  const firewallCommand =
    `$backend = "$env:LOCALAPPDATA\\Velocity-Bridge\\velocity-backend.exe"\n` +
    `$ui = "$env:LOCALAPPDATA\\Velocity-Bridge\\velocity_tauri.exe"\n` +
    `New-NetFirewallRule -DisplayName "Velocity Bridge Backend" -Direction Inbound -Action Allow -Program $backend -Profile Any -Protocol TCP -LocalPort ${firewallPort}\n` +
    `New-NetFirewallRule -DisplayName "Velocity Bridge App" -Direction Inbound -Action Allow -Program $ui -Profile Any -Protocol TCP`;

  const formatPortOwner = (owner: PortOwner) => {
    return owner.process_name ? `${owner.process_name} (PID ${owner.pid})` : `PID ${owner.pid}`;
  };

  const getPortConflict = async (port: number) => {
    try {
      return await invoke<PortOwner | null>("get_port_conflict", { port });
    } catch {
      return null;
    }
  };

  const ensurePreferredPort = async () => {
    const preferred = serverPortRef.current;
    const conflict = await getPortConflict(preferred);
    if (!conflict) {
      return preferred;
    }

    const message = `Port ${preferred} is already in use by ${formatPortOwner(conflict)}.

Stop it and use ${preferred}?`;
    const shouldStop = confirm(message);
    if (shouldStop) {
      try {
        await invoke<boolean>("stop_port_owner", { port: preferred });
      } catch (err) {
        console.warn("Failed to stop port owner:", err);
      }

      const retry = await getPortConflict(preferred);
      if (!retry) {
        return preferred;
      }
    }

    return await invoke<number>("pick_server_port", { preferred: Math.min(preferred + 1, 8100) });
  };

  const chooseServerPort = async () => {
    const port = await ensurePreferredPort();
    serverPortRef.current = port;
    setServerPort(port);
    return port;
  };

  const clearRestartTimer = () => {
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  };

  const clearCommandListeners = () => {
    if (!commandRef.current) return;
    commandRef.current.removeAllListeners();
    commandRef.current.stdout.removeAllListeners();
    commandRef.current.stderr.removeAllListeners();
    commandRef.current = null;
  };

  const scheduleServerRestart = (reason: string) => {
    if (isStoppingRef.current || isStartingRef.current || !serverEnabledRef.current) {
      return;
    }

    clearRestartTimer();
    setConnectionStatus(reason);
    restartTimerRef.current = window.setTimeout(() => {
      restartTimerRef.current = null;
      if (!isStoppingRef.current && serverEnabledRef.current && !childRef.current) {
        void startServer();
      }
    }, RESTART_DELAY_MS);
  };

  const handleBackendExit = (reason: string) => {
    childRef.current = null;
    clearCommandListeners();
    setServerStatus(null);

    if (isStoppingRef.current || !serverEnabledRef.current) {
      setConnectionStatus("Server stopped");
      return;
    }

    scheduleServerRestart(reason);
  };

  const prepareServerStart = async () => {
    try {
      await invoke("prepare_server_start");
    } catch (err) {
      console.warn("prepare_server_start failed:", err);
    }
  };

  const forceStopServer = async () => {
    try {
      await invoke("force_stop_server");
    } catch (err) {
      console.warn("force_stop_server failed:", err);
    }
  };

  // Start sidecar function
  const startServer = async () => {
    if (isStartingRef.current) {
      return;
    }

    isStartingRef.current = true;
    isStoppingRef.current = false;
    clearRestartTimer();

    try {
      console.log("Attempting to spawn sidecar...");
      const port = await chooseServerPort();
      setConnectionStatus(`Starting server on ${port}...`);

      await prepareServerStart();

      const command = Command.sidecar("velocity-backend", [], {
        env: { VELOCITY_PORT: String(port) },
      });
      commandRef.current = command;
      command.stdout.on("data", (line: string) => {
        console.debug("[velocity-backend]", line);
      });
      command.stderr.on("data", (line: string) => {
        console.warn("[velocity-backend]", line);
      });
      command.on("error", (error: string) => {
        console.error("Backend process error:", error);
        handleBackendExit("Backend error. Restarting...");
      });
      command.on("close", ({ code, signal }: { code: number | null; signal: number | null }) => {
        console.warn("Backend process closed:", { code, signal });
        handleBackendExit("Backend stopped. Restarting...");
      });

      const child = await command.spawn();
      childRef.current = child;
      console.log("Sidecar spawned with PID:", child.pid);
      setConnectionStatus("Connecting...");
      setServerEnabled(true);
    } catch (err: unknown) {
      clearCommandListeners();
      console.error("Failed to spawn sidecar:", err);
      const errorMsg = err instanceof Error ? err.message : String(err);
      setConnectionStatus("Spawn Error: " + errorMsg.substring(0, 30));
      setServerEnabled(false);
    } finally {
      isStartingRef.current = false;
    }
  };

  // Stop sidecar function
  const stopServer = async () => {
    console.log("Stopping server...");
    isStoppingRef.current = true;
    clearRestartTimer();

    // 1. Try graceful shutdown via API
    if (serverStatus?.token) {
      try {
        await fetch(buildLocalServerUrl(`/shutdown?token=${serverStatus.token}`), { method: "POST" });
        console.log("Sent shutdown signal to backend");
      } catch (e) {
        console.log("Backend already unreachable");
      }
    }

    try {
      // 2. Kill by process ref first
      if (childRef.current) {
        try {
          await childRef.current.kill();
        } catch (e) {
          console.log("child.kill() failed, trying force stop...", e);
        }
        childRef.current = null;
      }

      await forceStopServer();

      setServerEnabled(false);
      setConnectionStatus("Server stopped");
      setServerStatus(null);
      clearCommandListeners();
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

  // Spawn Sidecar on Mount and cleanup on close
  useEffect(() => {
    startServer();

    // Listen for window close to cleanup server
    // Removed setupCloseHandler to keep server running when window is hidden
    return () => {
      clearRestartTimer();
      clearCommandListeners();
    };
  }, []);

  // Poll History & Status
  useEffect(() => {
    // Don't poll if server is disabled
    if (!serverEnabled) {
      return;
    }

    const fetchData = async () => {
      try {
        const statusRes = await fetch(buildLocalServerUrl("/status"));
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (statusData.port && statusData.port !== serverPortRef.current) {
            serverPortRef.current = statusData.port;
            setServerPort(statusData.port);
          }
          setServerStatus(statusData);
          setConnectionStatus("Connected");

          // Fetch history with token from status
          if (statusData.token) {
            const historyRes = await fetch(buildLocalServerUrl(`/history?limit=50&token=${statusData.token}`));
            if (historyRes.ok) {
              const data = await historyRes.json();
              setHistory(data.items || []);
            }
          }
        } else {
          setServerStatus(null);
          setConnectionStatus("Reconnecting...");
        }
      } catch (e) {
        console.error("Fetch error:", e);
        setServerStatus(null);
        setConnectionStatus("Reconnecting...");
      }
    };

    // Smart polling: faster when viewing history (1.5s), slower otherwise (3s)
    const pollInterval = activeTab === "history" ? 1500 : 3000;
    const interval = setInterval(fetchData, pollInterval);
    fetchData();
    return () => clearInterval(interval);
  }, [serverEnabled, activeTab]); // Re-run when serverEnabled or tab changes

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Open file with the system default app
  const openFile = async (path: string) => {
    try {
      await openPath(path);
    } catch (err) {
      console.error("Failed to open file:", err);
    }
  };

  // Clear all history (with server-side deletion)
  const clearHistory = async () => {
    if (!serverStatus?.token) return;

    try {
      const response = await fetch(buildLocalServerUrl(`/history?token=${serverStatus.token}`), {
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

  // Check for updates using Tauri v2 plugin
  const checkForUpdates = async () => {
    if (isChecking) return;
    setIsChecking(true);
    setUpdateStatus(""); // Clear previous status

    try {
      console.log("Checking for updates...");
      const update = await check();
      if (update && update.available) {
        console.log("Update available:", update.version);
        setUpdateInfo({
          available: true,
          latestVersion: update.version,
          currentVersion: serverStatus?.version || "3.0.4",
          updaterHandle: update
        });
        showStatus("Update available!");
      } else {
        console.log("No updates available");
        setUpdateInfo({
          available: false,
          latestVersion: "",
          currentVersion: serverStatus?.version || "3.0.4"
        });
        showStatus("You're up to date");
      }
    } catch (err) {
      console.error("Failed to check for updates:", err);
      showStatus("Update check failed");
    } finally {
      setIsChecking(false);
    }
  };

  // Temporary status message (toast)
  const showStatus = (msg: string) => {
    setStatusMessage(msg);
    setTimeout(() => setStatusMessage(null), 3000);
  };

  // Perform the update and restart
  const startUpdate = async () => {
    if (!updateInfo?.updaterHandle) return;

    setIsDownloading(true);
    setUpdateStatus("Downloading update...");

    try {
      let downloadedLength = 0;
      let contentLength = 0;

      await updateInfo.updaterHandle.downloadAndInstall((event: any) => {
        switch (event.event) {
          case 'Started':
            contentLength = event.data.contentLength || 0;
            break;
          case 'Progress':
            downloadedLength += event.data.chunkLength;
            if (contentLength > 0) {
              setDownloadProgress(Math.round((downloadedLength / contentLength) * 100));
            }
            break;
          case 'Finished':
            setUpdateStatus("Restarting...");
            break;
        }
      });

      // Kill the sidecar and relaunch
      await stopServer();
      await relaunch();
    } catch (err) {
      console.error("Update failed:", err);
      setIsDownloading(false);
      setUpdateStatus("Update failed.");
      setTimeout(() => setUpdateStatus(""), 3000);
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

  // Load settings including notifications and start_minimized from backend
  useEffect(() => {
    if (serverStatus?.version) {
      const lastCheck = sessionStorage.getItem("lastUpdateCheck");
      if (!lastCheck) {
        checkForUpdates();
        sessionStorage.setItem("lastUpdateCheck", "true");
      }
      checkAutostart();
      // Load backend settings
      fetch(buildLocalServerUrl("/settings"))
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data) {
            setNotificationsEnabled(data.notifications_enabled ?? true);
            setStartMinimized(data.start_minimized ?? false);
            if (data.manual_address && !manualAddress) {
              setManualAddress(data.manual_address);
            }
          }
        })
        .catch(() => { });
    }
  }, [serverStatus?.version]);

  // Check if autostart is enabled
  const checkAutostart = async () => {
    try {
      const state = await isEnabled();
      setAutostart(state);
    } catch (err) {
      console.error("Failed to check autostart state:", err);
      setAutostart(false);
    }
  };

  // Toggle autostart
  const toggleAutostart = async () => {
    if (isTogglingAutostart) return;
    setIsTogglingAutostart(true);

    try {
      if (autostart) {
        await disable();
        setAutostart(false);
        showStatus("Autostart disabled");
      } else {
        await enable();
        setAutostart(true);
        showStatus("Autostart enabled");
      }
    } catch (err) {
      console.error("Failed to toggle autostart:", err);
      showStatus("Autostart toggle failed");
    } finally {
      setIsTogglingAutostart(false);
    }
  };

  // Toggle desktop notifications
  const toggleNotifications = async () => {
    if (isTogglingNotifications) return;
    setIsTogglingNotifications(true);
    const next = !notificationsEnabled;
    try {
      const res = await fetch(buildLocalServerUrl("/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notifications_enabled: next }),
      });
      if (res.ok) {
        setNotificationsEnabled(next);
        showStatus(next ? "Notifications enabled" : "Notifications disabled");
      }
    } catch {
      showStatus("Failed to update notification setting");
    } finally {
      setIsTogglingNotifications(false);
    }
  };

  // Toggle start minimized
  const toggleStartMinimized = async () => {
    if (isTogglingStartMinimized) return;
    setIsTogglingStartMinimized(true);
    const next = !startMinimized;
    try {
      const res = await fetch(buildLocalServerUrl("/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_minimized: next }),
      });
      if (res.ok) {
        setStartMinimized(next);
        showStatus(next ? "Will start minimized" : "Will show on startup");
      }
    } catch {
      showStatus("Failed to update start minimized setting");
    } finally {
      setIsTogglingStartMinimized(false);
    }
  };

  const isConnected = connectionStatus === "Connected";
  const displayedAddress = serverStatus
    ? `http://${serverStatus.hostname || serverStatus.ip}:${serverStatus.port || serverPort}`
    : `http://...:${serverPort}`;
  const effectiveAddress = useManualConnection && manualAddress ? manualAddress : displayedAddress;
  const onboardingAddress = useManualConnection && manualAddress ? manualAddress : displayedAddress;
  const onboardingToken = useManualConnection && manualToken ? manualToken : (serverStatus?.token || "...");

  const applyManualToken = async () => {
    const token = manualToken.trim();
    if (!token) return;
    setIsSettingToken(true);
    try {
      const res = await fetch(buildLocalServerUrl("/set_token"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (res.ok) {
        showStatus("Token updated");
      } else {
        showStatus("Failed to set token");
      }
    } catch (err) {
      console.error("Failed to set token:", err);
      showStatus("Failed to set token");
    } finally {
      setIsSettingToken(false);
    }
  };

  const applyManualAddress = async () => {
    const address = manualAddress.trim();
    if (!address) return;
    setIsSettingAddress(true);
    try {
      const res = await fetch(buildLocalServerUrl("/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ manual_address: address }),
      });
      if (res.ok) {
        showStatus("Address saved");
      } else {
        showStatus("Failed to save address");
      }
    } catch (err) {
      console.error("Failed to save address:", err);
      showStatus("Failed to save address");
    } finally {
      setIsSettingAddress(false);
    }
  };

  // Regenerate security token
  const regenerateToken = async () => {
    if (!serverStatus?.token) return;
    if (!confirm("Regenerate token?\n\nYou will need to update your iOS shortcuts with the new token.")) return;
    try {
      const response = await fetch(buildLocalServerUrl(`/regenerate_token?token=${serverStatus.token}`), { method: "POST" });
      if (response.ok) {
        const data = await response.json();
        console.log("Token regenerated:", data.token);
        // The new token will be picked up on next status poll
      } else {
        console.error("Failed to regenerate token");
        alert("Failed to regenerate token");
      }
    } catch (err) {
      console.error("Error regenerating token:", err);
      alert("Error regenerating token");
    }
  };

  // Show onboarding if first time user
  return (
    <div className="app-main-wrapper">
      <AnimatePresence>
        {isFlashActive && (
          <motion.div
            key="global-flash"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="flashbang-overlay"
            style={{ zIndex: 9999999 }}
          />
        )}
      </AnimatePresence>

      {showOnboarding === true ? (
        <Onboarding
          onComplete={handleOnboardingComplete}
          connectionAddress={onboardingAddress}
          connectionToken={onboardingToken}
          useManualConnection={useManualConnection}
          manualAddress={manualAddress}
          manualToken={manualToken}
          onToggleManual={setUseManualConnection}
          onManualAddressChange={setManualAddress}
          onManualTokenChange={setManualToken}
          onApplyManualToken={applyManualToken}
          onApplyManualAddress={applyManualAddress}
          isSettingToken={isSettingToken}
          isSettingAddress={isSettingAddress}
          shortcutIosToLinuxUrl={SHORTCUT_IOS_TO_LINUX_URL}
          shortcutBidirectionalUrl={SHORTCUT_BIDIRECTIONAL_URL}
        />
      ) : showOnboarding === false ? (
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
                style={{ border: '2px solid #007AFF', borderRadius: '8px', position: 'relative' }}
              >
                <Smartphone size={20} />
                <span>iOS Setup</span>
                <span style={{ position: 'absolute', top: '-6px', right: '-6px', background: '#007AFF', color: 'white', fontSize: '9px', fontWeight: '700', padding: '2px 6px', borderRadius: '8px' }}>NEW</span>
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
            {/* Status Toast */}
            {statusMessage && (
              <div style={{
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                background: '#1e1e1e',
                color: 'white',
                padding: '12px 20px',
                borderRadius: '12px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
                zIndex: 1000,
                fontSize: '14px',
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                animation: 'slideIn 0.3s ease-out'
              }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#007AFF' }}></div>
                {statusMessage}
              </div>
            )}

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
                  <strong>Update available!</strong> Version {updateInfo.latestVersion} is now available.
                </span>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>

                  {/* AppImage: Native Updater */}
                  {updateInfo.installType === "appimage" && updateInfo.updaterHandle && (
                    <button
                      onClick={async () => {
                        if (confirm(`Install update v${updateInfo.latestVersion} and restart?`)) {
                          await updateInfo.updaterHandle.downloadAndInstall();
                          // App will restart automatically
                        }
                      }}
                      style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: 'white', color: '#667eea', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
                    >
                      Running AppImage: Install & Restart
                    </button>
                  )}

                  {/* AppImage Fallback (GitHub) */}
                  {updateInfo.installType === "appimage" && !updateInfo.updaterHandle && (
                    <button
                      onClick={() => openUrl(`https://github.com/Trex099/Velocity-Bridge/releases/tag/v${updateInfo.latestVersion}`)}
                      style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: 'white', color: '#667eea', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
                    >
                      Download New AppImage
                    </button>
                  )}

                  {/* AUR Instruction */}
                  {updateInfo.installType === "aur" && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(0,0,0,0.2)', padding: '4px 8px', borderRadius: '4px', fontFamily: 'monospace' }}>
                      <span>yay -S velocity-bridge</span>
                      <button onClick={() => copyToClipboard('yay -S velocity-bridge')} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}>Copy</button>
                    </div>
                  )}

                  {/* DNF Instruction */}
                  {updateInfo.installType === "dnf" && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(0,0,0,0.2)', padding: '4px 8px', borderRadius: '4px', fontFamily: 'monospace' }}>
                      <span>sudo dnf update velocity-bridge</span>
                      <button onClick={() => copyToClipboard('sudo dnf update velocity-bridge')} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}>Copy</button>
                    </div>
                  )}

                  {/* APT Instruction */}
                  {updateInfo.installType === "apt" && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(0,0,0,0.2)', padding: '4px 8px', borderRadius: '4px', fontFamily: 'monospace' }}>
                      <span>sudo apt update && sudo apt install velocity-bridge</span>
                      <button onClick={() => copyToClipboard('sudo apt update && sudo apt install velocity-bridge')} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}>Copy</button>
                    </div>
                  )}

                  {/* Native Fallback */}
                  {updateInfo.installType === "native" && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '12px', background: 'rgba(255,255,255,0.2)', padding: '6px 10px', borderRadius: '4px' }}>
                        Update via your System Software Center or Terminal
                      </span>
                      <button
                        onClick={() => openUrl(`https://github.com/Trex099/Velocity-Bridge/releases/tag/v${updateInfo.latestVersion}`)}
                        style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.5)', background: 'transparent', color: 'white', cursor: 'pointer', fontSize: '13px' }}
                      >
                        View Release
                      </button>
                    </div>
                  )}

                  {/* Manual Fallback */}
                  {(updateInfo.installType === "manual" || !updateInfo.installType) && (
                    <button
                      onClick={() => openUrl("https://github.com/Trex099/Velocity-Bridge/releases/latest")}
                      style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: 'white', color: '#667eea', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
                    >
                      Download Update
                    </button>
                  )}

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
                    <label>Manual Override</label>
                    <div className="field-row" style={{ justifyContent: 'flex-start', gap: '10px' }}>
                      <input
                        type="checkbox"
                        checked={useManualConnection}
                        onChange={(e) => setUseManualConnection(e.target.checked)}
                      />
                      <span style={{ fontSize: '13px', color: '#666' }}>Use custom address and token</span>
                    </div>
                  </div>

                  <div className="connection-field">
                    <label>Network Address (use hostname.local or IP)</label>
                    <div className="field-row">
                      <input
                        type="text"
                        readOnly={!useManualConnection}
                        value={useManualConnection ? manualAddress : displayedAddress}
                        placeholder={useManualConnection ? displayedAddress : undefined}
                        onChange={(e) => setManualAddress(e.target.value)}
                        className="dark-input"
                      />
                      <button
                        className="field-btn"
                        onClick={() => navigator.clipboard.writeText(effectiveAddress)}
                      >
                        Copy
                      </button>
                      {useManualConnection && (
                        <button
                          className="field-btn"
                          onClick={applyManualAddress}
                          disabled={isSettingAddress || !manualAddress.trim()}
                        >
                          {isSettingAddress ? "Saving..." : "Save"}
                        </button>
                      )}
                    </div>
                  </div>


                  <div className="connection-field">
                    <label>Access Token</label>
                    <div className="field-row">
                      <input
                        type={showToken ? "text" : "password"}
                        readOnly={!useManualConnection}
                        value={useManualConnection ? manualToken : (serverStatus?.token || "Not Configured")}
                        onChange={(e) => setManualToken(e.target.value)}
                        className="dark-input"
                      />
                      <button
                        className="field-btn"
                        onClick={() => setShowToken(!showToken)}
                      >
                        {showToken ? "Hide" : "Show"}
                      </button>
                      {useManualConnection ? (
                        <button
                          className="field-btn"
                          onClick={applyManualToken}
                          disabled={isSettingToken || !manualToken.trim()}
                          title="Set backend token to this value"
                        >
                          {isSettingToken ? "Setting..." : "Set"}
                        </button>
                      ) : (
                        <button
                          className="field-btn"
                          onClick={regenerateToken}
                          title="Generate a new security token"
                        >
                          New
                        </button>
                      )}
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
                              {isImage ? "IMAGE" : isUrl ? "URL" : "TEXT"}
                            </span>
                            <span className="item-time">
                              {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className="item-content">
                            {isImage ? (
                              <span style={{ color: '#666', fontSize: '13px' }}>
                                {item.preview?.replace(/^IMAGE\\s*/i, '') || 'Image saved'}
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
                  <h1 style={{ fontSize: '28px', fontWeight: '700', marginBottom: '8px' }}>iOS Setup</h1>
                  <p style={{ color: '#666', marginBottom: '40px', fontSize: '15px' }}>
                    Scan these QR codes with your iPhone Camera to install the Shortcuts
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'row', gap: '32px', marginBottom: '24px', flexWrap: 'wrap', justifyContent: 'center' }}>
                    <div style={{ background: '#f8f9fa', borderRadius: '16px', padding: '24px 32px', display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                      <span style={{ position: 'absolute', top: '8px', right: '8px', background: '#007AFF', color: 'white', fontSize: '10px', fontWeight: '700', padding: '3px 8px', borderRadius: '10px' }}>NEW</span>
                      <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '16px', color: '#333' }}>iOS to Windows</h4>
                      <QRCodeSVG
                        value={SHORTCUT_IOS_TO_LINUX_URL}
                        size={120}
                        level="M"
                      />
                      <span style={{ fontSize: '11px', color: '#888', marginTop: '12px' }}>Text, URL & Images</span>
                    </div>
                    <div style={{ background: '#f8f9fa', borderRadius: '16px', padding: '24px 32px', display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                      <span style={{ position: 'absolute', top: '8px', right: '8px', background: '#007AFF', color: 'white', fontSize: '10px', fontWeight: '700', padding: '3px 8px', borderRadius: '10px' }}>NEW</span>
                      <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '16px', color: '#333' }}>Bidirectional</h4>
                      <QRCodeSVG
                        value={SHORTCUT_BIDIRECTIONAL_URL}
                        size={120}
                        level="M"
                      />
                      <span style={{ fontSize: '11px', color: '#888', marginTop: '12px' }}>Windows to iPhone</span>
                    </div>
                  </div>

                  <div style={{ background: '#f5f5f7', borderRadius: '12px', padding: '24px 32px', maxWidth: '480px', textAlign: 'left' }}>
                    <h3 style={{ margin: '0 0 16px 0', fontSize: '15px', fontWeight: '600' }}>Setup Instructions</h3>
                    <ol style={{ margin: 0, paddingLeft: '20px', color: '#555', lineHeight: '2', fontSize: '14px' }}>
                      <li>Scan a QR code with your iPhone Camera</li>
                      <li>Tap the notification to open in Shortcuts</li>
                      <li>Tap "Add Shortcut"</li>
                      <li>Enter your Server IP and Token</li>
                      <li>Use Back Tap to send content!</li>
                    </ol>

                    <div style={{ marginTop: '20px', padding: '12px 16px', background: '#e8f4fd', borderRadius: '8px', fontSize: '13px' }}>
                      <strong>Pro Tip:</strong> Set up <strong>Back Tap</strong> for instant access!
                      <div style={{ marginTop: '8px', color: '#555' }}>
                        Settings / Accessibility / Touch / Back Tap
                        <br />
                        - <strong>Double Tap</strong> to iOS to Windows shortcut
                        <br />
                        - <strong>Triple Tap</strong> to Bidirectional shortcut
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
                        disabled={isTogglingAutostart}
                      />
                    </div>
                    <div className="setting-item">
                      <div>
                        <label>Start Minimized to Tray</label>
                        <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#888' }}>App starts hidden; click tray icon to show</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={startMinimized}
                        onChange={toggleStartMinimized}
                        disabled={isTogglingStartMinimized}
                      />
                    </div>
                    <div className="setting-item">
                      <div>
                        <label>Desktop Notifications</label>
                        <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#888' }}>Show notification when clipboard is received</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={notificationsEnabled}
                        onChange={toggleNotifications}
                        disabled={isTogglingNotifications}
                      />
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
                        <button onClick={regenerateToken}>
                          Regenerate
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="settings-section">
                    <h2>Network Access</h2>
                    {firewallNeedsRule === null ? (
                      <p style={{ fontSize: '13px', color: '#888' }}>Checking Windows Firewall rules...</p>
                    ) : firewallNeedsRule ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <p style={{ fontSize: '13px', color: '#666', margin: 0 }}>
                          Windows Firewall appears to be blocking inbound access to Velocity Bridge on port {firewallPort}.
                        </p>
                        <div style={{ background: '#f7f7f7', border: '1px solid #e5e5e5', borderRadius: '8px', padding: '12px' }}>
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '12px' }}>
                            {firewallCommand}
                          </pre>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <button
                            className="primary-btn"
                            style={{ padding: '8px 16px', borderRadius: '8px', border: 'none', background: '#007AFF', color: 'white', cursor: 'pointer', fontSize: '13px' }}
                            onClick={() => copyToClipboard(firewallCommand)}
                          >
                            Copy Admin Command
                          </button>
                          <span style={{ fontSize: '12px', color: '#888' }}>Run in Admin PowerShell</span>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#22c55e', fontSize: '13px' }}>
                        <CheckCircle2 size={16} />
                        <span>Firewall rules are present.</span>
                      </div>
                    )}
                  </div>

                  <div className="settings-section">
                    <h2>Updates</h2>
                    <div className="setting-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                        <label>Application Version</label>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ fontFamily: 'monospace', background: '#f0f0f0', padding: '4px 8px', borderRadius: '4px', fontSize: '13px' }}>
                            v{serverStatus?.version || "3.0.4"}
                          </span>
                          {updateInfo?.available && !isDownloading && (
                            <span className="update-badge" style={{ background: '#007AFF', color: 'white', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 'bold' }}>
                              UPDATE AVAILABLE
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="update-controls" style={{ width: '100%', marginTop: '4px' }}>
                        {!isDownloading ? (
                          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                            <button
                              onClick={updateInfo?.available ? startUpdate : checkForUpdates}
                              className="primary-btn"
                              style={{
                                padding: '8px 20px',
                                borderRadius: '8px',
                                border: 'none',
                                background: updateInfo?.available ? '#22c55e' : '#007AFF',
                                color: 'white',
                                cursor: 'pointer',
                                fontSize: '14px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                transition: 'all 0.2s'
                              }}
                            >
                              {isChecking ? (
                                <><RotateCcw size={16} className="spin" /> Checking...</>
                              ) : updateInfo?.available ? (
                                <><Download size={16} /> Download & Install v{updateInfo.latestVersion}</>
      ) : (
                                <><RotateCcw size={16} /> Check for Updates</>
                              )}
                            </button>

                            {updateInfo && !updateInfo.available && !isChecking && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#22c55e', fontSize: '13px' }}>
                                <CheckCircle2 size={16} />
                                <span>You're up to date!</span>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="download-progress-container" style={{ width: '100%' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                              <span style={{ color: '#007AFF', fontWeight: '500' }}>{updateStatus}</span>
                              <span>{downloadProgress}%</span>
                            </div>
                            <div className="progress-bar-bg" style={{ height: '8px', background: '#ccc', borderRadius: '4px', overflow: 'hidden' }}>
                              <div
                                className="progress-bar-fill"
                                style={{
                                  height: '100%',
                                  width: `${downloadProgress}%`,
                                  background: '#007AFF',
                                  transition: 'width 0.3s ease'
                                }}
                              />
                            </div>
                          </div>
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
                        <h4>iOS to Windows</h4>
                        <QRCodeSVG
                          value={SHORTCUT_IOS_TO_LINUX_URL}
                          size={120}
                          level="M"
                        />
                        <span className="qr-label">Text, URL & Images</span>
                      </div>
                      <div className="qr-item">
                        <h4>Bidirectional</h4>
                        <QRCodeSVG
                          value={SHORTCUT_BIDIRECTIONAL_URL}
                          size={120}
                          level="M"
                        />
                        <span className="qr-label">Windows to iPhone</span>
                      </div>
                    </div>

                    <div style={{ background: '#f5f5f7', borderRadius: '8px', padding: '12px', marginTop: '16px' }}>
                      <p style={{ fontSize: '12px', color: '#666', margin: 0 }}>
                        <strong>Setup:</strong> 1. Scan QR to 2. Add Shortcut to 3. Enter IP & Token
                      </p>
                    </div>
                  </div>

                </div>
              )
            }

          </main >
        </div >
      ) : null}
    </div>
  );
}

export default App;















