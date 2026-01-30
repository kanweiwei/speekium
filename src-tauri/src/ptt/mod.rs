//! PTT (Push-to-Talk) Module
//!
//! This module handles PTT-related functionality including event reading
//! and state management.

pub mod reader;

pub use reader::{start_ptt_reader, handle_ptt_event};
