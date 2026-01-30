import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { ThemeProvider } from "./components/ThemeProvider";
import { WorkModeProvider } from "./contexts/WorkModeContext";
import { SettingsProvider } from "./contexts/SettingsContext";
import { ConfigStoreProvider, configStore } from "./stores/ConfigStore";
import { listen } from "@tauri-apps/api/event";
import "./i18n"; // Initialize i18n

// ConfigStore 初始化组件
// 在应用启动时加载配置并监听 daemon 状态
function ConfigStoreInitializer({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    let mounted = true;

    // 监听 daemon-ready 事件后再加载配置
    const setupConfig = async () => {
      try {
        const unlisten = await listen<{ status: string }>('daemon-status', (event) => {
          if (event.payload.status === 'ready' && mounted) {
            console.log('[ConfigStore] Daemon ready, loading config...');
            configStore.loadConfig().catch(error => {
              console.error('[ConfigStore] Failed to load config:', error);
            });
          }
        });

        return unlisten;
      } catch (error) {
        console.error('[ConfigStore] Failed to listen for daemon-status:', error);
        return () => {};
      }
    };

    const cleanupPromise = setupConfig();

    return () => {
      mounted = false;
      cleanupPromise.then(unlisten => unlisten());
    };
  }, []);

  return <>{children}</>;
}

// ConfigStore Provider 包装器
function ConfigStoreProviderWrapper({ children }: { children: React.ReactNode }) {
  return (
    <ConfigStoreProvider>
      <ConfigStoreInitializer>
        {children}
      </ConfigStoreInitializer>
    </ConfigStoreProvider>
  );
}

// StrictMode 仅在开发环境启用，用于检测副作用问题
// 生产环境禁用以避免双重执行带来的性能开销
const rootElement = document.getElementById("root") as HTMLElement;

const AppWrapper = (
  <ThemeProvider defaultTheme="dark" storageKey="speekium-theme">
    <ConfigStoreProviderWrapper>
      <SettingsProvider>
        <WorkModeProvider>
          <App />
        </WorkModeProvider>
      </SettingsProvider>
    </ConfigStoreProviderWrapper>
  </ThemeProvider>
);

if (import.meta.env.DEV) {
  // 开发环境：使用 StrictMode 帮助发现潜在问题
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>{AppWrapper}</React.StrictMode>
  );
} else {
  // 生产环境：不使用 StrictMode
  ReactDOM.createRoot(rootElement).render(AppWrapper);
}
