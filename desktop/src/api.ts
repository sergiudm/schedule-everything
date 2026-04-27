import { invoke } from "@tauri-apps/api/core";
import type { BridgeClient, BridgeResponse } from "./types";

export class DesktopBridgeError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.name = "DesktopBridgeError";
    this.code = code;
    this.details = details;
  }
}

export const desktopBridge: BridgeClient = {
  async send<T>(command: string, payload: Record<string, unknown>): Promise<T> {
    const response = await invoke<BridgeResponse<T>>("bridge_command", {
      command,
      payload
    });

    if (!response.ok) {
      throw new DesktopBridgeError(
        response.error.code,
        response.error.message,
        response.error.details
      );
    }

    return response.data;
  }
};
