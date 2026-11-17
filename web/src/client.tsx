/** @jsxImportSource react */
import { createRoot } from "react-dom/client";
import { MyAssistant } from "./components/MyAssistant";

const container = document.getElementById("assistant-ui-root");
if (container) {
  createRoot(container).render(<MyAssistant />);
}
