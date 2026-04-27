export type BridgeError = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type BridgeResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: BridgeError };

export type ScheduleEvent = {
  time: string;
  label: string;
  block: string | null;
  syncable: boolean;
};

export type TaskItem = {
  description: string;
  priority: number;
};

export type DeadlineItem = {
  event: string;
  deadline: string;
  daysLeft: number | null;
  status: string;
};

export type HabitItem = {
  id: string;
  description: string;
  completed: boolean;
};

export type Snapshot = {
  config: {
    rootDir: string;
    activeId: number;
    activeConfigDir: string;
    tasksPath: string;
    deadlinesPath: string;
    habitsPath: string;
    recordsPath: string;
  };
  today: {
    date: string;
    weekday: string;
    parity: string;
  };
  schedule: {
    isSkipped: boolean;
    current: string | null;
    next: string | null;
    timeToNext: string | null;
    events: ScheduleEvent[];
    hasSyncedOverlay: boolean;
  };
  tasks: TaskItem[];
  deadlines: DeadlineItem[];
  habits: HabitItem[];
};

export type SyncProposal = {
  summary: string | null;
  plan: {
    target_date: string;
    parity: string;
    weekday: string;
    assignments: Record<string, { block: string; title: string }>;
  };
  preview: ScheduleEvent[];
};

export type BridgeClient = {
  send<T = unknown>(command: string, payload: Record<string, unknown>): Promise<T>;
};
