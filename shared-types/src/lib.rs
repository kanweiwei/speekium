// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! # Shared Types Library
//!
//! This library provides type definitions shared between the frontend, Rust backend, and Python daemon.
//! It compiles to WebAssembly for the frontend and as a native Rust library for the backend.
//!
//! ## Benefits
//! 1. **Single Source of Truth**: Type definitions exist in one place
//! 2. **Automatic Synchronization**: Frontend and backend types are always in sync
//! 3. **Compile-time Checking**: Type errors are caught at build time

#![warn(missing_docs)]
#![warn(clippy::all)]

pub mod errors;
pub mod events;
pub mod models;

// Re-export commonly used types
pub use models::*;
pub use events::*;

// Result type alias
pub type Result<T, E = errors::SharedError> = std::result::Result<T, E>;
