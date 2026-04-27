import { Plus, RefreshCw, Trash2 } from "lucide";
import type { BridgeClient, Snapshot } from "./types";

type SvgAttrs = Record<string, string | number>;
type SvgNode = readonly [tag: string, attrs: SvgAttrs, children?: readonly SvgNode[]];

const refreshIcon = renderIcon(RefreshCw, { width: 16, height: 16 });
const plusIcon = renderIcon(Plus, { width: 16, height: 16 });
const trashIcon = renderIcon(Trash2, { width: 16, height: 16 });

export async function renderApp(
  root: HTMLElement,
  client: BridgeClient
): Promise<void> {
  root.innerHTML = `<section class="shell"><p class="muted">Loading...</p></section>`;

  async function load(): Promise<void> {
    try {
      const snapshot = await client.send<Snapshot>("status_snapshot", {});
      renderSnapshot(root, client, snapshot, load);
    } catch (error) {
      renderError(root, error);
    }
  }

  await load();
}

function renderError(root: HTMLElement, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  root.innerHTML = `
    <section class="shell">
      <div class="panel error-panel">
        <p class="eyebrow">Desktop Bridge</p>
        <h1>Could not load schedule</h1>
        <p>${escapeHtml(message)}</p>
      </div>
    </section>
  `;
}

function renderSnapshot(
  root: HTMLElement,
  client: BridgeClient,
  snapshot: Snapshot,
  reload: () => Promise<void>
): void {
  root.innerHTML = `
    <section class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Schedule Everything</p>
          <h1>Daily Command Center</h1>
          <p class="muted">${snapshot.today.date} · ${snapshot.today.weekday} · ${snapshot.today.parity} week · config ${snapshot.config.activeId}</p>
        </div>
        <button class="icon-button" type="button" data-testid="refresh" aria-label="Refresh">${refreshIcon}</button>
      </header>
      <section class="grid">
        ${renderNowNext(snapshot)}
        ${renderTimeline(snapshot)}
        ${renderQueue(snapshot)}
        ${renderQuickAdd()}
      </section>
    </section>
  `;

  root
    .querySelector<HTMLButtonElement>("[data-testid='refresh']")
    ?.addEventListener("click", () => {
      void reload();
    });

  root
    .querySelector<HTMLButtonElement>("[data-testid='task-add']")
    ?.addEventListener("click", () => {
      void addTask(root, client, reload);
    });
}

function renderNowNext(snapshot: Snapshot): string {
  const current = snapshot.schedule.current ?? "Idle";
  const next = snapshot.schedule.next ?? "No upcoming events";
  const timeToNext = snapshot.schedule.timeToNext
    ? `in ${snapshot.schedule.timeToNext}`
    : "";
  return `
    <article class="panel now-panel">
      <p class="eyebrow">Now</p>
      <h2>${escapeHtml(current)}</h2>
      <div class="next-line">
        <span>Next</span>
        <strong>${escapeHtml(next)}</strong>
        <em>${escapeHtml(timeToNext)}</em>
      </div>
      <span class="sync-pill">${snapshot.schedule.hasSyncedOverlay ? "Synced" : "Base schedule"}</span>
    </article>
  `;
}

function renderTimeline(snapshot: Snapshot): string {
  const rows = snapshot.schedule.events
    .map(
      (event) => `
        <li class="timeline-row">
          <time>${escapeHtml(event.time)}</time>
          <span class="block-dot ${escapeHtml(event.block ?? "plain")}"></span>
          <span>${escapeHtml(event.label)}</span>
        </li>
      `
    )
    .join("");

  return `
    <article class="panel timeline-panel">
      <div class="panel-heading">
        <p class="eyebrow">Today Timeline</p>
      </div>
      <ol class="timeline">${rows}</ol>
    </article>
  `;
}

function renderQueue(snapshot: Snapshot): string {
  const tasks = snapshot.tasks
    .slice(0, 6)
    .map(
      (task) => `
        <li class="queue-row">
          <span>${escapeHtml(task.description)}</span>
          <strong>${task.priority}</strong>
          <button class="icon-button subtle" type="button" aria-label="Delete task ${escapeHtml(task.description)}">${trashIcon}</button>
        </li>
      `
    )
    .join("");
  const deadlines = snapshot.deadlines
    .slice(0, 4)
    .map(
      (deadline) => `
        <li class="queue-row deadline ${escapeHtml(deadline.status)}">
          <span>${escapeHtml(deadline.event)}</span>
          <strong>${deadline.daysLeft === null ? "Invalid" : `${deadline.daysLeft}d`}</strong>
        </li>
      `
    )
    .join("");
  const habits = snapshot.habits
    .map(
      (habit) => `
        <label class="habit-row">
          <input type="checkbox" ${habit.completed ? "checked" : ""} />
          <span>${escapeHtml(habit.description)}</span>
        </label>
      `
    )
    .join("");

  return `
    <article class="panel queue-panel">
      <p class="eyebrow">Work Queue</p>
      <h3>Tasks</h3>
      <ul class="queue-list">${tasks}</ul>
      <h3>Deadlines</h3>
      <ul class="queue-list">${deadlines}</ul>
      <h3>Habits</h3>
      <div class="habit-list">${habits}</div>
    </article>
  `;
}

function renderQuickAdd(): string {
  return `
    <article class="panel quick-panel">
      <p class="eyebrow">Quick Add</p>
      <div class="form-row">
        <input data-testid="task-description" type="text" autocomplete="off" placeholder="New task" />
        <input data-testid="task-priority" type="number" min="1" max="10" value="5" aria-label="Task priority" />
        <button data-testid="task-add" class="primary-button" type="button">${plusIcon}<span>Add</span></button>
      </div>
      <button class="primary-button sync-button" type="button"><span>Sync Today</span></button>
    </article>
  `;
}

async function addTask(
  root: HTMLElement,
  client: BridgeClient,
  reload: () => Promise<void>
): Promise<void> {
  const description =
    root
      .querySelector<HTMLInputElement>("[data-testid='task-description']")
      ?.value.trim() ?? "";
  const priorityValue =
    root.querySelector<HTMLInputElement>("[data-testid='task-priority']")?.value ?? "5";
  const priority = Number.parseInt(priorityValue, 10);
  await client.send("task_add", { description, priority });
  await reload();
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderIcon(node: SvgNode, overrides: SvgAttrs): string {
  const [tag, attrs, children = []] = node;
  const mergedAttrs: SvgAttrs = {
    ...attrs,
    ...overrides,
    "aria-hidden": "true",
    focusable: "false",
    class: "lucide-icon",
  };
  const attrText = Object.entries(mergedAttrs)
    .map(([name, value]) => `${name}="${escapeHtml(String(value))}"`)
    .join(" ");
  const childText = children.map((child) => renderIcon(child, {})).join("");
  return `<${tag} ${attrText}>${childText}</${tag}>`;
}
