import { describe, expect, it, vi } from "vitest";
import { renderApp } from "./render";
import type { BridgeClient, Snapshot } from "./types";

const snapshot: Snapshot = {
  config: {
    rootDir: "/tmp/config",
    activeId: 0,
    activeConfigDir: "/tmp/config/user_config_0",
    tasksPath: "/tmp/config/tasks/tasks.json",
    deadlinesPath: "/tmp/config/user_config_0/ddl.json",
    habitsPath: "/tmp/config/user_config_0/habits.toml",
    recordsPath: "/tmp/config/tasks/record.json"
  },
  today: {
    date: "2026-04-28",
    weekday: "tuesday",
    parity: "even"
  },
  schedule: {
    isSkipped: false,
    current: "pomodoro: Draft proposal at 09:00",
    next: "short_break at 09:25",
    timeToNext: "7m",
    events: [
      {
        time: "09:00",
        label: "pomodoro: Draft proposal",
        block: "pomodoro",
        syncable: false
      },
      {
        time: "09:25",
        label: "short_break",
        block: "short_break",
        syncable: false
      }
    ],
    hasSyncedOverlay: true
  },
  tasks: [{ description: "Draft proposal", priority: 9 }],
  deadlines: [
    { event: "Submit paper", deadline: "2026-05-10", daysLeft: 12, status: "ok" }
  ],
  habits: [{ id: "1", description: "Read", completed: false }]
};

describe("renderApp", () => {
  it("renders the daily command center", async () => {
    const root = document.createElement("main");
    const client: BridgeClient = {
      send: vi.fn().mockResolvedValue(snapshot)
    };

    await renderApp(root, client);

    expect(root.textContent).toContain("Daily Command Center");
    expect(root.textContent).toContain("pomodoro: Draft proposal");
    expect(root.textContent).toContain("Draft proposal");
    expect(root.textContent).toContain("Submit paper");
    expect(root.textContent).toContain("Read");
    expect(root.querySelector(".grid")).not.toBeNull();
    expect(root.querySelector(".now-panel")).not.toBeNull();
    expect(root.querySelector(".timeline-panel")).not.toBeNull();
    expect(root.querySelector(".queue-panel")).not.toBeNull();
    expect(root.querySelector(".quick-panel")).not.toBeNull();
  });

  it("sends task add command and refreshes", async () => {
    const root = document.createElement("main");
    const client: BridgeClient = {
      send: vi.fn().mockResolvedValue(snapshot)
    };

    await renderApp(root, client);

    const input = root.querySelector<HTMLInputElement>(
      "[data-testid='task-description']"
    );
    const priority = root.querySelector<HTMLInputElement>(
      "[data-testid='task-priority']"
    );
    const button = root.querySelector<HTMLButtonElement>("[data-testid='task-add']");
    expect(input).not.toBeNull();
    expect(priority).not.toBeNull();
    expect(button).not.toBeNull();

    input!.value = "Review PR";
    priority!.value = "8";
    button!.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(client.send).toHaveBeenCalledWith("task_add", {
      description: "Review PR",
      priority: 8
    });
  });
});
