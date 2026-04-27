import "./styles.css";

const root = document.querySelector<HTMLDivElement>("#app");

if (!root) {
  throw new Error("Missing #app root element");
}

root.innerHTML = `
  <section class="shell">
    <p class="eyebrow">Schedule Everything</p>
    <h1>Daily Command Center</h1>
    <p class="muted">Loading desktop bridge...</p>
  </section>
`;
