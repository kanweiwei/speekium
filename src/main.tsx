import React from "react";
import ReactDOM from "react-dom/client";

// Dev tool: react-grab - press Cmd/Ctrl+C to grab component context for AI coding
// Note: "Broken pipe" error may appear in Tauri due to unavailable stdin, but it's harmless
if (import.meta.env.DEV) {
  import("react-grab").catch(() => {});
}

import "./index.css";
import App from "./App";
import { ThemeProvider } from "./components/ThemeProvider";
import { WorkModeProvider } from "./contexts/WorkModeContext";
import { SettingsProvider } from "./contexts/SettingsContext";
import { ErrorProvider } from "./contexts/ErrorContext";
import "./i18n"; // Initialize i18n

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="speekium-theme">
      <ErrorProvider>
        <SettingsProvider>
          <WorkModeProvider>
            <App />
          </WorkModeProvider>
        </SettingsProvider>
      </ErrorProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
