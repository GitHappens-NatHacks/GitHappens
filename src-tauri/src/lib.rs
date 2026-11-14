use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::{
    atomic::{AtomicU16, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

struct SidecarState {
    port: Arc<AtomicU16>,
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
    let state = SidecarState {
        port: Arc::clone(&port),
        child: Mutex::new(None),
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(|app| {
            let handle = app.handle().clone();
            let sidecar_cmd = match handle.shell().sidecar("truecursor-backend") {
                Ok(cmd) => cmd,
                Err(_) => {
                    // During local dev when sidecar binary is not built yet, assume external uvicorn on 8000.
                    return Ok(());
                }
            };

            if let Ok((mut rx, child)) = sidecar_cmd.spawn() {
                let state = handle.state::<SidecarState>();
                state.port.store(0, Ordering::SeqCst);
                if let Ok(mut guard) = state.child.lock() {
                    *guard = Some(child);
                }

                let port_ref = Arc::clone(&state.port);
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

                let ready_port = Arc::clone(&state.port);
                wait_for_health(&ready_port, Duration::from_secs(15));
                if ready_port.load(Ordering::SeqCst) == 0 {
                    ready_port.store(8000, Ordering::SeqCst);
                }
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
