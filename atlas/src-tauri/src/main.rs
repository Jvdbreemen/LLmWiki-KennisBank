// KennisBank Atlas - Tauri shell (TASK-27.12).
//
// Near-zero Rust per ADR-0004: it hosts the WebView2 frontend and owns the
// FastAPI sidecar lifecycle. On startup it picks a free loopback port, spawns
// the bundled (frozen) sidecar bound to 127.0.0.1 on that port, and injects the
// port into the webview (window.__ATLAS_PORT__) before the frontend loads so the
// data-client connects to the right sidecar. The sidecar child is killed with
// the app (tauri-plugin-shell manages the process; no orphan).
//
// NOTE: this is the standard Tauri v2 + sidecar pattern; it compiles/runs only
// with the Rust toolchain installed (see atlas/BUILD.md). It has not been built
// in this environment (no cargo); expect to smoke-test `cargo tauri dev` once.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("bind ephemeral port")
        .local_addr()
        .unwrap()
        .port()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let port = free_port();

            // Spawn the frozen sidecar (bundled as an external binary) on the
            // chosen loopback port. KENNISBANK_VAULT is inherited from the env.
            let (mut rx, _child) = app
                .shell()
                .sidecar("atlas-sidecar")
                .expect("atlas-sidecar binary is bundled")
                .args(["--host", "127.0.0.1", "--port", &port.to_string()])
                .spawn()
                .expect("spawn sidecar");

            // Drain sidecar stdout/stderr so it never blocks (and for debugging).
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stderr(line) = event {
                        eprintln!("[sidecar] {}", String::from_utf8_lossy(&line));
                    }
                }
            });

            // Inject the port before the frontend loads.
            let init = format!("window.__ATLAS_PORT__ = {};", port);
            WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("KennisBank Atlas")
                .inner_size(1400.0, 900.0)
                .initialization_script(&init)
                .build()?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("run KennisBank Atlas");
}
