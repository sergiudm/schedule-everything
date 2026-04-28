use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::process::Command;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Deserialize, Serialize)]
struct BridgeRequest {
    command: String,
    payload: Value,
}

struct BridgeProcessOutput {
    success: bool,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

#[tauri::command]
async fn bridge_command(
    app: AppHandle,
    command: String,
    payload: Value,
) -> Result<Value, String> {
    let request = BridgeRequest { command, payload };
    let request_json = serde_json::to_string(&request).map_err(|error| error.to_string())?;

    let output = if cfg!(debug_assertions) {
        let output = Command::new("uv")
            .args(["run", "schedule-gui-bridge", &request_json])
            .output()
            .map_err(|error| format!("failed to run development bridge: {error}"))?;
        BridgeProcessOutput {
            success: output.status.success(),
            stdout: output.stdout,
            stderr: output.stderr,
        }
    } else {
        let command = app
            .shell()
            .sidecar("schedule-gui-bridge")
            .map_err(|error| format!("failed to resolve bridge sidecar: {error}"))?
            .args([request_json]);
        let output = command
            .output()
            .await
            .map_err(|error| format!("failed to run bridge sidecar: {error}"))?;
        BridgeProcessOutput {
            success: output.status.success(),
            stdout: output.stdout,
            stderr: output.stderr,
        }
    };

    if !output.success {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    serde_json::from_slice(&output.stdout).map_err(|error| {
        format!(
            "bridge returned invalid JSON: {error}; stdout={}",
            String::from_utf8_lossy(&output.stdout)
        )
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![bridge_command])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_shadow(true);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Schedule Everything desktop app");
}
