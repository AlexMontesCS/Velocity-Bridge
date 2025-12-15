use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    menu::{Menu, MenuItem},
    Manager,
};


#[tauri::command]
fn get_install_type() -> String {
    if std::env::var("APPIMAGE").is_ok() {
        return "appimage".to_string();
    }
    
    if let Ok(exe_path) = std::env::current_exe() {
        let path_str = exe_path.to_string_lossy();
        if path_str.starts_with("/usr/") {
            // Check for distro specific files to identify package manager
            if std::path::Path::new("/etc/arch-release").exists() {
                return "aur".to_string();
            } else if std::path::Path::new("/etc/fedora-release").exists() {
                return "dnf".to_string();
            } else if std::path::Path::new("/etc/debian_version").exists() {
                return "apt".to_string();
            }
            return "native".to_string();
        }
    }
    
    "manual".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Fix for "Failed to create GBM buffer" on Linux (WebKitGTK)
    std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // If app is already running, show the existing window
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .invoke_handler(tauri::generate_handler![get_install_type, install_update])
        .setup(|app| {
            // Create tray menu
            let show = MenuItem::with_id(app, "show", "Show", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;

            // Create tray icon
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Velocity Bridge")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "show" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                        "quit" => {
                            // Force kill server backend before exiting
                            // We use std::process::Command to ensure it runs synchronously
                            let _ = std::process::Command::new("pkill").args(["-f", "server-x86_64"]).status();
                            let _ = std::process::Command::new("fuser").args(["-k", "8080/tcp"]).status();
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    // Show window on left click
                    if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                        if let Some(window) = tray.app_handle().get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            // Hide window on close instead of quitting
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                window.hide().unwrap();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
fn install_update(package_path: String) -> Result<(), String> {
    use std::process::Command;
    
    // 1. Make executable (just in case)
    let _ = Command::new("chmod")
        .args(["+x", &package_path])
        .status();
    
    // 2. Spawn the installer in DETACHED mode
    // Note: In Rust/Tauri 2, spawning a command and exiting *might* kill child?
    // But usually simple spawn() leaves it running if we don't wait.
    // However, to be safe, we should probably ensure it outlives us.
    // Linux 'nohup' or similar isn't strictly needed if we just exit.
    
    Command::new(package_path)
        .arg("--silent")
        .spawn()
        .map_err(|e| format!("Failed to launch updater: {}", e))?;
        
    // 3. Kill server and exit immediately
    let _ = Command::new("pkill").args(["-f", "server-x86_64"]).status();
    let _ = Command::new("fuser").args(["-k", "8080/tcp"]).status();
    std::process::exit(0);
}
