import "./styles.css";
import { desktopBridge } from "./api";
import { renderApp } from "./render";

const root = document.querySelector<HTMLDivElement>("#app");

if (!root) {
  throw new Error("Missing #app root element");
}

void renderApp(root, desktopBridge);
