// src-tauri/src/platform/macos.rs
//
// macOS 文字输入实现

use tauri::command;

#[cfg(target_os = "macos")]
fn char_to_key_code(ch: char) -> Option<u16> {
    // macOS virtual key codes
    // Reference: https://cdecl.org/wiki/Virtual_Key_Codes
    match ch {
        // Letters (A-Z) - all map to same key code, shift determines case
        'a'..='z' | 'A'..='Z' => Some(0),  // kVK_ANSI_A

        // Numbers (0-9)
        '0' => Some(29),  // kVK_ANSI_0
        '1'..='9' => Some(((ch as u8) - (b'1') + 18) as u16),  // kVK_ANSI_1 through kVK_ANSI_9

        // Special characters
        ' ' => Some(49),   // kVK_Space
        '\n' | '\r' => Some(36),  // kVK_Return
        '\t' => Some(48),  // kVK_Tab
        '.' => Some(47),   // kVK_ANSI_Period
        ',' => Some(43),   // kVK_ANSI_Comma
        '?' => Some(44),   // kVK_ANSI_Slash (with shift)
        '!' => Some(18),   // kVK_ANSI_1 (with shift)
        '@' => Some(19),   // kVK_ANSI_2 (with shift)
        '#' => Some(20),   // kVK_ANSI_3 (with shift)
        '$' => Some(21),   // kVK_ANSI_4 (with shift)
        '%' => Some(23),   // kVK_ANSI_5 (with shift)
        '^' => Some(22),   // kVK_ANSI_6 (with shift)
        '&' => Some(26),   // kVK_ANSI_7 (with shift)
        '*' => Some(28),   // kVK_ANSI_8 (with shift)
        '(' => Some(25),   // kVK_ANSI_9 (with shift)
        ')' => Some(29),   // kVK_ANSI_0 (with shift)
        '-' => Some(27),   // kVK_ANSI_Minus
        '_' => Some(27),   // kVK_ANSI_Minus (with shift)
        '=' => Some(24),   // kVK_ANSI_Equal
        '+' => Some(24),   // kVK_ANSI_Equal (with shift)
        '[' => Some(33),   // kVK_ANSI_LeftBracket
        ']' => Some(30),   // kVK_ANSI_RightBracket
        '{' => Some(33),   // kVK_ANSI_LeftBracket (with shift)
        '}' => Some(30),   // kVK_ANSI_RightBracket (with shift)
        '\\' => Some(42),  // kVK_ANSI_Backslash
        '|' => Some(42),   // kVK_ANSI_Backslash (with shift)
        ';' => Some(41),   // kVK_ANSI_Semicolon
        ':' => Some(41),   // kVK_ANSI_Semicolon (with shift)
        '\'' => Some(39),  // kVK_ANSI_Quote
        '"' => Some(39),   // kVK_ANSI_Quote (with shift)
        '`' => Some(50),   // kVK_ANSI_Grave
        '~' => Some(50),   // kVK_ANSI_Grave (with shift)
        '/' => Some(44),   // kVK_ANSI_Slash
        '<' => Some(43),   // kVK_ANSI_Comma (with shift)
        '>' => Some(47),   // kVK_ANSI_Period (with shift)

        _ => None,  // Unsupported character
    }
}

#[cfg(target_os = "macos")]
pub fn type_text(text: &str) -> Result<(), String> {
    use cocoa::appkit::NSPasteboard;
    use cocoa::base::{id, nil};
    use cocoa::foundation::NSString as CFString;
    use core_graphics::event::{CGEvent, CGEventTapLocation, CGEventFlags};
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
    use objc::{msg_send, sel, sel_impl, class};

    println!("⌨️  使用剪贴板输入文字: {}", text);

    // 1. Save current clipboard content
    let pasteboard: id = unsafe { msg_send![class!(NSPasteboard), generalPasteboard] };
    let pasteboard_type = unsafe { CFString::alloc(nil).init_str("public.utf8-plain-text") };
    let old_content: id = unsafe { msg_send![pasteboard, stringForType: pasteboard_type] };

    println!("📋 已保存旧剪贴板内容");

    // Define clipboard restoration function
    let restore_clipboard = || -> Result<(), String> {
        if old_content != nil {
            unsafe {
                let _: () = msg_send![pasteboard, clearContents];
                let types: id = msg_send![class!(NSArray), arrayWithObject: pasteboard_type];
                let _: () = msg_send![pasteboard, declareTypes: types owner: nil];
                let success: bool = msg_send![pasteboard, setString: old_content forType: pasteboard_type];

                if !success {
                    eprintln!("⚠️  警告：剪贴板恢复失败，用户数据可能丢失");
                    return Err("Failed to restore clipboard".to_string());
                }
            }
            println!("🔄 已恢复原剪贴板内容");
        }
        Ok(())
    };

    // 2. Set new content to clipboard
    let ns_string = unsafe { CFString::alloc(nil).init_str(text) };

    unsafe {
        let _: () = msg_send![pasteboard, clearContents];
        let types: id = msg_send![class!(NSArray), arrayWithObject: pasteboard_type];
        let _: () = msg_send![pasteboard, declareTypes: types owner: nil];
        let success: bool = msg_send![pasteboard, setString: ns_string forType: pasteboard_type];

        if !success {
            println!("⚠️  剪贴板设置失败");
            let _ = restore_clipboard();
            return Err("Failed to set clipboard content".to_string());
        }
    }

    println!("✅ 已设置新剪贴板内容");

    // 3. Create event source
    let event_source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
        .map_err(|e| format!("Failed to create event source: {:?}", e))?;

    // 4. Simulate Cmd+V keypress
    let cmd_key_code: u16 = 55;
    let v_key_code: u16 = 9;

    // Press Cmd
    let cmd_down = CGEvent::new_keyboard_event(event_source.clone(), cmd_key_code, true)
        .map_err(|e| format!("Failed to create Cmd key down event: {:?}", e))?;
    cmd_down.set_flags(CGEventFlags::CGEventFlagCommand);
    cmd_down.post(CGEventTapLocation::Session);
    println!("⌨️  按下 Cmd");

    // Press V
    let v_down = CGEvent::new_keyboard_event(event_source.clone(), v_key_code, true)
        .map_err(|e| format!("Failed to create V key down event: {:?}", e))?;
    v_down.set_flags(CGEventFlags::CGEventFlagCommand);
    v_down.post(CGEventTapLocation::Session);
    println!("⌨️  按下 V");

    // Release V
    let v_up = CGEvent::new_keyboard_event(event_source.clone(), v_key_code, false)
        .map_err(|e| format!("Failed to create V key up event: {:?}", e))?;
    v_up.set_flags(CGEventFlags::CGEventFlagCommand);
    v_up.post(CGEventTapLocation::Session);
    println!("⌨️  释放 V");

    // Release Cmd
    let cmd_up = CGEvent::new_keyboard_event(event_source.clone(), cmd_key_code, false)
        .map_err(|e| format!("Failed to create Cmd key up event: {:?}", e))?;
    cmd_up.post(CGEventTapLocation::Session);
    println!("⌨️  释放 Cmd");

    // Wait for paste to complete
    std::thread::sleep(std::time::Duration::from_millis(50));

    // 5. Restore original clipboard content
    restore_clipboard()?;

    println!("⌨️  文字输入完成");
    Ok(())
}
