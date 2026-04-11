import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import "highlight.js/styles/tokyo-night-dark.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
