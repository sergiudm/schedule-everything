import {
  CalendarPlus,
  Check,
  Plus,
  RefreshCw,
  Trash2,
  WandSparkles,
} from "lucide";
import type { BridgeClient, Snapshot, SyncProposal } from "./types";

type SvgAttrs = Record<string, string | number>;
type SvgNode = readonly [tag: string, attrs: SvgAttrs, children?: readonly SvgNode[]];

const refreshIcon = renderIcon(RefreshCw, { width: 16, height: 16 });
const plusIcon = renderIcon(Plus, { width: 16, height: 16 });
const trashIcon = renderIcon(Trash2, { width: 16, height: 16 });
const calendarIcon = renderIcon(CalendarPlus, { width: 16, height: 16 });
const checkIcon = renderIcon(Check, { width: 16, height: 16 });
const sparkIcon = renderIcon(WandSparkles, { width: 16, height: 16 });

type AppState = {
  syncProposal: SyncProposal | null;
  syncFeedback: string[];
};

export async function renderApp(
  root: HTMLElement,
  client: BridgeClient
): Promise<void> {
  const state: AppState = {
    syncProposal: null,
    syncFeedback: [],
  };
  root.innerHTML = `<section class="shell"><p class="muted">Loading...</p></section>`;

  async function load(): Promise<void> {
    try {
      const snapshot = await client.send<Snapshot>("status_snapshot", {});
      renderSnapshot(root, client, snapshot, load, state);
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
  reload: () => Promise<void>,
  state: AppState
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
        ${renderQuickAdd(state)}
      </section>
    </section>
  `;

  root
    .querySelector<HTMLButtonElement>("[data-testid='refresh']")
    ?.addEventListener("click", () => {
      runAction(root, reload);
    });

  root
    .querySelector<HTMLButtonElement>("[data-testid='task-add']")
    ?.addEventListener("click", () => {
      runAction(root, () => addTask(root, client, reload));
    });

  root
    .querySelectorAll<HTMLButtonElement>("[data-testid='task-delete']")
    .forEach((button) => {
      button.addEventListener("click", () => {
        runAction(root, () => deleteTask(button, client, reload));
      });
    });

  root
    .querySelector<HTMLButtonElement>("[data-testid='deadline-add']")
    ?.addEventListener("click", () => {
      runAction(root, () => addDeadline(root, client, reload));
    });

  root
    .querySelectorAll<HTMLButtonElement>("[data-testid='deadline-delete']")
    .forEach((button) => {
      button.addEventListener("click", () => {
        runAction(root, () => deleteDeadline(button, client, reload));
      });
    });

  root
    .querySelectorAll<HTMLInputElement>("[data-testid='habit-check']")
    .forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        runAction(root, () => markHabits(root, client, reload));
      });
    });

  root
    .querySelector<HTMLButtonElement>("[data-testid='sync-generate']")
    ?.addEventListener("click", () => {
      runAction(root, () => generateSync(root, client, snapshot, reload, state));
    });

  root
    .querySelector<HTMLButtonElement>("[data-testid='sync-accept']")
    ?.addEventListener("click", () => {
      runAction(root, () => acceptSync(client, reload, state));
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
          <span class="block-dot ${cssClass(event.block)}"></span>
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
          <button class="icon-button subtle" type="button" data-testid="task-delete" data-description="${escapeHtml(task.description)}" aria-label="Delete task ${escapeHtml(task.description)}" title="Delete task">${trashIcon}</button>
        </li>
      `
    )
    .join("");
  const deadlines = snapshot.deadlines
    .slice(0, 4)
    .map(
      (deadline) => `
        <li class="queue-row deadline ${cssClass(deadline.status)}">
          <span>${escapeHtml(deadline.event)}</span>
          <strong>${deadline.daysLeft === null ? "Invalid" : `${deadline.daysLeft}d`}</strong>
          <button class="icon-button subtle" type="button" data-testid="deadline-delete" data-event="${escapeHtml(deadline.event)}" aria-label="Delete deadline ${escapeHtml(deadline.event)}" title="Delete deadline">${trashIcon}</button>
        </li>
      `
    )
    .join("");
  const habits = snapshot.habits
    .map(
      (habit) => `
        <label class="habit-row">
          <input data-testid="habit-check" data-habit-id="${escapeHtml(habit.id)}" type="checkbox" ${habit.completed ? "checked" : ""} />
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

function renderQuickAdd(state: AppState): string {
  return `
    <article class="panel quick-panel">
      <p class="eyebrow">Quick Add</p>
      <div class="form-row">
        <input data-testid="task-description" type="text" autocomplete="off" placeholder="New task" />
        <input data-testid="task-priority" type="number" min="1" max="10" value="5" aria-label="Task priority" />
        <button data-testid="task-add" class="primary-button" type="button">${plusIcon}<span>Add</span></button>
      </div>
      <div class="deadline-form">
        <input data-testid="deadline-event" type="text" autocomplete="off" placeholder="Deadline" />
        <input data-testid="deadline-date" type="text" autocomplete="off" placeholder="YYYY-MM-DD" />
        <button data-testid="deadline-add" class="secondary-button" type="button">${calendarIcon}<span>Add</span></button>
      </div>
      <div class="sync-box">
        <textarea data-testid="sync-feedback" rows="3" placeholder="Sync adjustment"></textarea>
        <div class="sync-actions">
          <button data-testid="sync-generate" class="primary-button sync-button" type="button">${sparkIcon}<span>${state.syncProposal ? "Regenerate" : "Sync Today"}</span></button>
          ${
            state.syncProposal
              ? `<button data-testid="sync-accept" class="primary-button accept-button" type="button">${checkIcon}<span>Accept</span></button>`
              : ""
          }
        </div>
        ${state.syncProposal ? renderSyncProposal(state.syncProposal) : ""}
      </div>
    </article>
  `;
}

function renderSyncProposal(proposal: SyncProposal): string {
  const rows = proposal.preview
    .slice(0, 10)
    .map(
      (event) => `
        <li class="sync-preview-row">
          <time>${escapeHtml(event.time)}</time>
          <span class="block-dot ${cssClass(event.block)}"></span>
          <span>${escapeHtml(event.label)}</span>
        </li>
      `
    )
    .join("");

  return `
    <div class="sync-preview" data-testid="sync-preview">
      ${proposal.summary ? `<p>${escapeHtml(proposal.summary)}</p>` : ""}
      <ol>${rows}</ol>
    </div>
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

async function deleteTask(
  button: HTMLButtonElement,
  client: BridgeClient,
  reload: () => Promise<void>
): Promise<void> {
  const description = button.dataset.description ?? "";
  await client.send("task_delete", { description });
  await reload();
}

async function addDeadline(
  root: HTMLElement,
  client: BridgeClient,
  reload: () => Promise<void>
): Promise<void> {
  const event =
    root.querySelector<HTMLInputElement>("[data-testid='deadline-event']")?.value.trim() ??
    "";
  const date =
    root.querySelector<HTMLInputElement>("[data-testid='deadline-date']")?.value.trim() ??
    "";
  await client.send("deadline_add", { event, date });
  await reload();
}

async function deleteDeadline(
  button: HTMLButtonElement,
  client: BridgeClient,
  reload: () => Promise<void>
): Promise<void> {
  const event = button.dataset.event ?? "";
  await client.send("deadline_delete", { event });
  await reload();
}

async function markHabits(
  root: HTMLElement,
  client: BridgeClient,
  reload: () => Promise<void>
): Promise<void> {
  const habitIds = Array.from(
    root.querySelectorAll<HTMLInputElement>("[data-testid='habit-check']:checked")
  ).map((checkbox) => checkbox.dataset.habitId ?? "");
  await client.send("habit_mark", { habitIds });
  await reload();
}

async function generateSync(
  root: HTMLElement,
  client: BridgeClient,
  snapshot: Snapshot,
  reload: () => Promise<void>,
  state: AppState
): Promise<void> {
  const feedback =
    root.querySelector<HTMLTextAreaElement>("[data-testid='sync-feedback']")?.value.trim() ??
    "";
  state.syncFeedback = feedback ? [feedback] : [];
  state.syncProposal = await client.send<SyncProposal>("sync_generate", {
    feedback: state.syncFeedback,
  });
  renderSnapshot(root, client, snapshot, reload, state);
}

async function acceptSync(
  client: BridgeClient,
  reload: () => Promise<void>,
  state: AppState
): Promise<void> {
  if (!state.syncProposal) {
    return;
  }
  await client.send("sync_accept", { plan: state.syncProposal.plan });
  state.syncProposal = null;
  state.syncFeedback = [];
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

function cssClass(value: string | null): string {
  return (value ?? "plain").replaceAll(/[^a-zA-Z0-9_-]/g, "-") || "plain";
}

function renderIcon(
  node: SvgNode,
  overrides: SvgAttrs = {},
  isRoot = true
): string {
  const [tag, attrs, children = []] = node;
  const mergedAttrs: SvgAttrs = {
    ...attrs,
    ...overrides,
    ...(isRoot
      ? {
          "aria-hidden": "true",
          focusable: "false",
          class: "lucide-icon",
        }
      : {}),
  };
  const attrText = Object.entries(mergedAttrs)
    .map(([name, value]) => `${name}="${escapeHtml(String(value))}"`)
    .join(" ");
  const childText = children.map((child) => renderIcon(child, {}, false)).join("");
  return `<${tag} ${attrText}>${childText}</${tag}>`;
}

function runAction(root: HTMLElement, action: () => Promise<void>): void {
  action().catch((error: unknown) => {
    renderError(root, error);
  });
}
