import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { ThemeProvider } from "./components/ThemeProvider";
import { WorkModeProvider } from "./contexts/WorkModeContext";
import "./i18n"; // Initialize i18n

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="speekium-theme">
      <WorkModeProvider>
        <App />
      </WorkModeProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
