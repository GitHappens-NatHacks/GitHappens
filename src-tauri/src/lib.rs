use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::{
    atomic::{AtomicBool, AtomicU16, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant};

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

struct SidecarState {
    port: Arc<AtomicU16>,
    stabilization_active: Arc<AtomicBool>,
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

#[tauri::command]
fn get_backend_port(state: tauri::State<'_, SidecarState>) -> u16 {
    state.port.load(Ordering::SeqCst)
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

fn post_toggle_stabilization(port: u16, next_active: bool) -> bool {
    let addr: SocketAddr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(400)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let body = format!(
        "{{\"steady_hand\":{},\"assistance_enabled\":true}}",
        if next_active { "true" } else { "false" }
    );
    let req = format!(
        "POST /api/engine/toggle HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        port,
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

fn trigger_stabilization_toggle(app: &tauri::AppHandle, status_item: Option<&MenuItem<tauri::Wry>>) {
    let state = app.state::<SidecarState>();
    let port = state.port.load(Ordering::SeqCst);
    let current = state.stabilization_active.load(Ordering::SeqCst);
    let next = !current;
    state.stabilization_active.store(next, Ordering::SeqCst);

    if let Some(item) = status_item {
        let label = if next {
            "Status: Stabilization Active"
        } else {
            "Status: Stabilization Paused"
        };
        let _ = item.set_text(label);
    }

    let handle = app.clone();
    std::thread::spawn(move || {
        if port > 0 {
            let _ = post_toggle_stabilization(port, next);
        }
        let _ = handle.emit("stabilization-toggled", next);
    });
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
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
    let stabilization_active = Arc::new(AtomicBool::new(true));
    let state = SidecarState {
        port: Arc::clone(&port),
        stabilization_active: Arc::clone(&stabilization_active),
        child: Mutex::new(None),
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(state)
        .invoke_handler(tauri::generate_handler![get_backend_port, open_permission_settings])
        .setup(|app| {
            let handle = app.handle().clone();

            // 1. Spawn Python FastAPI sidecar when bundled binary is available.
            if let Ok(sidecar_cmd) = handle.shell().sidecar("truecursor-backend") {
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
                                if let Some(raw_port) = line.trim().strip_prefix("TRUECURSOR_READY port=") {
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
            let toggle_item = MenuItem::with_id(
                app,
                "toggle_steady",
                "Toggle Stabilization (Cmd/Ctrl+Shift+S)",
                true,
                None::<&str>,
            )?;
            let show_item = MenuItem::with_id(app, "open_window", "Open TrueCursor", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit TrueCursor", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[&status_item, &toggle_item, &show_item, &sep, &quit_item],
            )?;

            let status_for_menu = status_item.clone();
            let mut tray_builder = TrayIconBuilder::with_id("truecursor-tray")
                .menu(&menu)
                .tooltip("TrueCursor - Tremor Stabilization & Gaze Control")
                .on_menu_event(move |app_handle, event| match event.id().as_ref() {
                    "toggle_steady" => trigger_stabilization_toggle(app_handle, Some(&status_for_menu)),
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

            // 3. Register configurable global hotkey with conflict-safe fallback.
            let status_for_key = status_item.clone();
            if let Err(err) = app.global_shortcut().on_shortcut(
                "CommandOrControl+Shift+S",
                move |app_handle, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        trigger_stabilization_toggle(app_handle, Some(&status_for_key));
                    }
                },
            ) {
                eprintln!("[TrueCursor] Global shortcut registration skipped: {}", err);
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Failed to initialize TrueCursor Tauri shell");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            app_handle.state::<SidecarState>().terminate();
        }
    });
}
