use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::{
    atomic::{AtomicBool, AtomicU16, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager, RunEvent, WindowEvent};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const EMERGENCY_SHORTCUT: &str = "CommandOrControl+Alt+Escape";

struct SidecarState {
    port: Arc<AtomicU16>,
    token: String,
    stabilization_active: Arc<AtomicBool>,
    minimize_to_tray: Arc<AtomicBool>,
    current_shortcut: Mutex<String>,
    status_item: Mutex<Option<MenuItem<tauri::Wry>>>,
    child: Mutex<Option<CommandChild>>,
}

impl SidecarState {
    fn terminate(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(child) = guard.take() {
                let _ = child.kill();
            }
        }
    }
}

fn generate_local_token() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let mut h1 = RandomState::new().build_hasher();
    h1.write_u128(nanos);
    h1.write_u32(std::process::id());
    let mut h2 = RandomState::new().build_hasher();
    h2.write_u64(h1.finish());
    h2.write_u128(nanos ^ 0x9E37_79B9_7F4A_7C15);
    format!("{:016x}{:016x}", h1.finish(), h2.finish())
}

#[tauri::command]
fn get_backend_port(state: tauri::State<'_, SidecarState>) -> u16 {
    state.port.load(Ordering::SeqCst)
}

#[tauri::command]
fn get_backend_token(state: tauri::State<'_, SidecarState>) -> String {
    state.token.clone()
}

#[tauri::command]
fn sync_tray_state(
    state: tauri::State<'_, SidecarState>,
    active: bool,
    status_text: Option<String>,
    minimize_to_tray: Option<bool>,
) {
    state.stabilization_active.store(active, Ordering::SeqCst);
    if let Some(min_tray) = minimize_to_tray {
        state.minimize_to_tray.store(min_tray, Ordering::SeqCst);
    }
    if let Ok(guard) = state.status_item.lock() {
        if let Some(item) = guard.as_ref() {
            let label = status_text.unwrap_or_else(|| {
                if active {
                    "Status: Stabilization Active".to_string()
                } else {
                    "Status: Stabilization Paused".to_string()
                }
            });
            let _ = item.set_text(label);
        }
    }
}

#[tauri::command]
fn update_global_shortcut(app: tauri::AppHandle, shortcut: String) -> Result<bool, String> {
    let trimmed = shortcut.trim().to_string();
    if trimmed.is_empty() {
        return Err("Shortcut cannot be empty".to_string());
    }
    let state = app.state::<SidecarState>();
    let previous = state
        .current_shortcut
        .lock()
        .map(|g| g.clone())
        .unwrap_or_else(|_| "CommandOrControl+Shift+S".to_string());

    if previous == trimmed {
        return Ok(true);
    }

    let _ = app.global_shortcut().unregister(previous.as_str());
    app.global_shortcut()
        .on_shortcut(trimmed.as_str(), move |app_handle, _shortcut, event| {
            if event.state == ShortcutState::Pressed {
                trigger_stabilization_toggle(app_handle);
            }
        })
        .map_err(|e| format!("Failed to register shortcut '{}': {}", trimmed, e))?;

    if let Ok(mut guard) = state.current_shortcut.lock() {
        *guard = trimmed;
    }
    Ok(true)
}

#[tauri::command]
fn open_permission_settings(target: String) -> bool {
    let key = target.trim().to_ascii_lowercase();
    #[cfg(target_os = "macos")]
    {
        let uri = match key.as_str() {
            "input_monitoring" => {
                "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
            }
            "camera" => "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
            _ => "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        };
        return std::process::Command::new("open").arg(uri).spawn().is_ok();
    }
    #[cfg(target_os = "windows")]
    {
        let uri = match key.as_str() {
            "camera" => "ms-settings:privacy-webcam",
            _ => "ms-settings:easeofaccess-mouse",
        };
        return std::process::Command::new("cmd")
            .args(["/c", "start", "", uri])
            .spawn()
            .is_ok();
    }
    #[allow(unreachable_code)]
    false
}

fn check_health(port: u16) -> bool {
    let addr: SocketAddr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(250)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(300)));
    let req = format!(
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        port
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 512];
    match stream.read(&mut buf) {
        Ok(n) if n > 0 => {
            let head = String::from_utf8_lossy(&buf[..n]);
            head.starts_with("HTTP/1.1 200") || head.starts_with("HTTP/1.0 200")
        }
        _ => false,
    }
}

fn post_json_to_sidecar(port: u16, token: &str, path: &str, body: &str) -> bool {
    let addr: SocketAddr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(400)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let token_header = if token.is_empty() {
        String::new()
    } else {
        format!("X-ClearCursor-Token: {}\r\n", token)
    };
    let req = format!(
        "POST {} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\n{}Content-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        path,
        port,
        token_header,
        body.len(),
        body
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 512];
    match stream.read(&mut buf) {
        Ok(n) if n > 0 => {
            let head = String::from_utf8_lossy(&buf[..n]);
            head.starts_with("HTTP/1.1 200") || head.starts_with("HTTP/1.0 200")
        }
        _ => false,
    }
}

fn set_tray_status_label(app: &tauri::AppHandle, label: &str) {
    let state = app.state::<SidecarState>();
    if let Ok(guard) = state.status_item.lock() {
        if let Some(item) = guard.as_ref() {
            let _ = item.set_text(label);
        }
    }
}

fn trigger_stabilization_toggle(app: &tauri::AppHandle) {
    let state = app.state::<SidecarState>();
    let port = state.port.load(Ordering::SeqCst);
    let token = state.token.clone();
    let current = state.stabilization_active.load(Ordering::SeqCst);
    let next = !current;
    state.stabilization_active.store(next, Ordering::SeqCst);

    let label = if next {
        "Status: Stabilization Active"
    } else {
        "Status: Stabilization Paused"
    };
    set_tray_status_label(app, label);

    let handle = app.clone();
    std::thread::spawn(move || {
        if port > 0 {
            let body = format!(
                "{{\"steady_hand\":{},\"assistance_enabled\":true}}",
                if next { "true" } else { "false" }
            );
            let _ = post_json_to_sidecar(port, &token, "/api/engine/toggle", &body);
        }
        let _ = handle.emit("stabilization-toggled", next);
    });
}

fn trigger_preset_switch(app: &tauri::AppHandle, preset: &str) {
    let state = app.state::<SidecarState>();
    let port = state.port.load(Ordering::SeqCst);
    let token = state.token.clone();
    state.stabilization_active.store(true, Ordering::SeqCst);
    set_tray_status_label(app, &format!("Status: Active ({})", preset));

    let preset_owned = preset.to_string();
    let handle = app.clone();
    std::thread::spawn(move || {
        if port > 0 {
            let body = match preset_owned.as_str() {
                "mild" => "{\"profile\":\"mild\",\"assistance_enabled\":true,\"steady_hand\":true,\"gaze_control\":false,\"tremor_strength\":65,\"one_euro_min_cutoff\":0.95,\"one_euro_beta\":0.008,\"click_freeze_ms\":140,\"gravity_strength\":25}",
                "high" => "{\"profile\":\"high\",\"assistance_enabled\":true,\"steady_hand\":true,\"gaze_control\":false,\"tremor_strength\":145,\"one_euro_min_cutoff\":0.35,\"one_euro_beta\":0.002,\"click_freeze_ms\":240,\"gravity_strength\":55}",
                _ => "{\"profile\":\"moderate\",\"assistance_enabled\":true,\"steady_hand\":true,\"gaze_control\":false,\"tremor_strength\":100,\"one_euro_min_cutoff\":0.6,\"one_euro_beta\":0.004,\"click_freeze_ms\":180,\"gravity_strength\":38}",
            };
            let _ = post_json_to_sidecar(port, &token, "/api/settings", body);
        }
        let _ = handle.emit("preset-switched", preset_owned);
    });
}

fn trigger_emergency_stop_all(app: &tauri::AppHandle) {
    let state = app.state::<SidecarState>();
    let port = state.port.load(Ordering::SeqCst);
    let token = state.token.clone();
    state.stabilization_active.store(false, Ordering::SeqCst);
    set_tray_status_label(app, "Status: Emergency Stopped");

    let handle = app.clone();
    std::thread::spawn(move || {
        if port > 0 {
            let _ = post_json_to_sidecar(port, &token, "/api/engine/emergency-stop", "{}");
        }
        let _ = handle.emit("emergency-stop-triggered", true);
    });
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn wait_for_health(port_ref: &Arc<AtomicU16>, timeout: Duration) {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        let port = port_ref.load(Ordering::SeqCst);
        if port > 0 && check_health(port) {
            return;
        }
        std::thread::sleep(Duration::from_millis(120));
    }
}

pub fn run() {
    let port = Arc::new(AtomicU16::new(8000));
    let token = generate_local_token();
    let stabilization_active = Arc::new(AtomicBool::new(true));
    let minimize_to_tray = Arc::new(AtomicBool::new(true));
    let state = SidecarState {
        port: Arc::clone(&port),
        token: token.clone(),
        stabilization_active: Arc::clone(&stabilization_active),
        minimize_to_tray: Arc::clone(&minimize_to_tray),
        current_shortcut: Mutex::new("CommandOrControl+Shift+S".to_string()),
        status_item: Mutex::new(None),
        child: Mutex::new(None),
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            get_backend_port,
            get_backend_token,
            sync_tray_state,
            update_global_shortcut,
            open_permission_settings
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            // 1. Spawn Python FastAPI sidecar when bundled binary is available.
            if let Ok(sidecar_cmd) = handle.shell().sidecar("clearcursor-backend") {
                let sidecar_cmd = sidecar_cmd.env("CLEARCURSOR_API_TOKEN", &handle.state::<SidecarState>().token);
                if let Ok((mut rx, child)) = sidecar_cmd.spawn() {
                    let st = handle.state::<SidecarState>();
                    st.port.store(0, Ordering::SeqCst);
                    if let Ok(mut guard) = st.child.lock() {
                        *guard = Some(child);
                    }

                    let port_ref = Arc::clone(&st.port);
                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = rx.recv().await {
                            if let CommandEvent::Stdout(line_bytes) = event {
                                let line = String::from_utf8_lossy(&line_bytes);
                                if let Some(raw_port) = line
                                    .trim()
                                    .strip_prefix("CLEARCURSOR_READY port=")
                                    .or_else(|| line.trim().strip_prefix("TRUECURSOR_READY port="))
                                {
                                    if let Ok(parsed) = raw_port.parse::<u16>() {
                                        port_ref.store(parsed, Ordering::SeqCst);
                                    }
                                }
                            }
                        }
                    });

                    let ready_port = Arc::clone(&st.port);
                    wait_for_health(&ready_port, Duration::from_secs(15));
                    if ready_port.load(Ordering::SeqCst) == 0 {
                        ready_port.store(8000, Ordering::SeqCst);
                    }
                }
            }

            // 2. Build native system tray / menu bar HUD.
            let status_item = MenuItem::with_id(
                app,
                "status",
                "Status: Stabilization Active",
                false,
                None::<&str>,
            )?;
            if let Ok(mut guard) = handle.state::<SidecarState>().status_item.lock() {
                *guard = Some(status_item.clone());
            }

            let toggle_item = MenuItem::with_id(
                app,
                "toggle_steady",
                "Toggle Stabilization (Cmd/Ctrl+Shift+S)",
                true,
                None::<&str>,
            )?;
            let preset_mild = MenuItem::with_id(app, "preset_mild", "Preset: Mild Tremor", true, None::<&str>)?;
            let preset_mod = MenuItem::with_id(app, "preset_moderate", "Preset: Moderate Tremor", true, None::<&str>)?;
            let preset_high = MenuItem::with_id(app, "preset_high", "Preset: High Tremor", true, None::<&str>)?;
            let stop_all = MenuItem::with_id(
                app,
                "emergency_stop",
                "Emergency Stop All (Cmd/Ctrl+Alt+Esc)",
                true,
                None::<&str>,
            )?;
            let show_item = MenuItem::with_id(app, "open_window", "Open ClearCursor", true, None::<&str>)?;
            let sep1 = PredefinedMenuItem::separator(app)?;
            let sep2 = PredefinedMenuItem::separator(app)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit ClearCursor", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[
                    &status_item,
                    &toggle_item,
                    &sep1,
                    &preset_mild,
                    &preset_mod,
                    &preset_high,
                    &sep2,
                    &stop_all,
                    &show_item,
                    &quit_item,
                ],
            )?;

            let mut tray_builder = TrayIconBuilder::with_id("clearcursor-tray")
                .menu(&menu)
                .tooltip("ClearCursor - Tremor Stabilization & Gaze Control")
                .on_menu_event(move |app_handle, event| match event.id().as_ref() {
                    "toggle_steady" => trigger_stabilization_toggle(app_handle),
                    "preset_mild" => trigger_preset_switch(app_handle, "mild"),
                    "preset_moderate" => trigger_preset_switch(app_handle, "moderate"),
                    "preset_high" => trigger_preset_switch(app_handle, "high"),
                    "emergency_stop" => trigger_emergency_stop_all(app_handle),
                    "open_window" => show_main_window(app_handle),
                    "quit" => {
                        app_handle.state::<SidecarState>().terminate();
                        app_handle.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main_window(tray.app_handle());
                    }
                });

            if let Some(icon) = app.default_window_icon().cloned() {
                tray_builder = tray_builder.icon(icon);
            }
            let _ = tray_builder.build(app);

            // 3. Register configurable toggle hotkey and dedicated emergency stop hotkey.
            if let Err(err) = app.global_shortcut().on_shortcut(
                "CommandOrControl+Shift+S",
                move |app_handle, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        trigger_stabilization_toggle(app_handle);
                    }
                },
            ) {
                eprintln!("[ClearCursor] Global shortcut registration skipped: {}", err);
            }
            if let Err(err) = app.global_shortcut().on_shortcut(
                EMERGENCY_SHORTCUT,
                move |app_handle, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        trigger_emergency_stop_all(app_handle);
                    }
                },
            ) {
                eprintln!("[ClearCursor] Emergency shortcut registration skipped: {}", err);
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let hide = window
                    .app_handle()
                    .state::<SidecarState>()
                    .minimize_to_tray
                    .load(Ordering::SeqCst);
                if hide {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Failed to initialize ClearCursor Tauri shell");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            app_handle.state::<SidecarState>().terminate();
        }
    });
}
