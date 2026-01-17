// ============================================================================
// Audio Recording Module
// Using cpal for cross-platform audio capture
// Thread-safe design using channels for communication
// ============================================================================

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::sync::{Arc, Mutex, atomic::{AtomicBool, Ordering}};
use std::sync::mpsc::{channel, Sender, Receiver};
use std::thread::{self, JoinHandle};
use std::fs::File;
use std::io::Write;

// Audio recording constants
const SAMPLE_RATE: u32 = 16000;  // 16kHz for ASR
const CHANNELS: u16 = 1;  // Mono

/// Commands sent to the recording thread
enum RecordingCommand {
    Stop,
}

/// Thread-safe audio recorder
/// Uses a background thread for recording to avoid Send/Sync issues with cpal::Stream
pub struct AudioRecorder {
    /// Recording flag (shared with recording thread)
    is_recording: Arc<AtomicBool>,
    /// Audio buffer (shared with recording thread)
    buffer: Arc<Mutex<Vec<f32>>>,
    /// Channel to send commands to recording thread
    command_tx: Option<Sender<RecordingCommand>>,
    /// Recording thread handle
    thread_handle: Option<JoinHandle<()>>,
}

// Mark as Send + Sync since we only store thread-safe types
unsafe impl Send for AudioRecorder {}
unsafe impl Sync for AudioRecorder {}

impl AudioRecorder {
    /// Create a new AudioRecorder
    pub fn new() -> Result<Self, String> {
        Ok(AudioRecorder {
            is_recording: Arc::new(AtomicBool::new(false)),
            buffer: Arc::new(Mutex::new(Vec::new())),
            command_tx: None,
            thread_handle: None,
        })
    }

    /// Start recording audio in a background thread
    pub fn start_recording(&mut self) -> Result<(), String> {
        if self.is_recording.load(Ordering::SeqCst) {
            return Err("Already recording".to_string());
        }

        // Clear previous buffer
        {
            let mut buffer = self.buffer.lock().unwrap();
            buffer.clear();
        }

        // Create command channel
        let (tx, rx) = channel();
        self.command_tx = Some(tx);

        // Clone shared state for the thread
        let is_recording = self.is_recording.clone();
        let buffer = self.buffer.clone();

        // Set recording flag before spawning thread
        is_recording.store(true, Ordering::SeqCst);

        // Spawn recording thread
        let handle = thread::spawn(move || {
            if let Err(_e) = run_recording_thread(is_recording.clone(), buffer, rx) {
            }
            is_recording.store(false, Ordering::SeqCst);
        });

        self.thread_handle = Some(handle);

        Ok(())
    }

    /// Stop recording and save audio to a temporary WAV file
    pub fn stop_recording(&mut self) -> Result<AudioData, String> {
        if !self.is_recording.load(Ordering::SeqCst) {
            return Err("Not recording".to_string());
        }

        // Send stop command to recording thread
        if let Some(tx) = self.command_tx.take() {
            let _ = tx.send(RecordingCommand::Stop);
        }

        // Wait for recording thread to finish
        if let Some(handle) = self.thread_handle.take() {
            let _ = handle.join();
        }

        // Get recorded samples
        let samples = {
            let buffer = self.buffer.lock().unwrap();
            buffer.clone()
        };

        let duration_secs = samples.len() as f32 / SAMPLE_RATE as f32;

        if samples.is_empty() {
            return Err("No audio data recorded".to_string());
        }

        // Convert to WAV format
        let wav_data = samples_to_wav(&samples)?;

        // Save to temporary file
        let temp_path = create_temp_wav_path();
        let mut file = File::create(&temp_path)
            .map_err(|e| format!("Failed to create temp file: {}", e))?;
        file.write_all(&wav_data)
            .map_err(|e| format!("Failed to write WAV data: {}", e))?;


        Ok(AudioData {
            file_path: temp_path,
            sample_rate: SAMPLE_RATE,
            duration_secs,
            sample_count: samples.len(),
        })
    }

    /// Check if currently recording
    #[allow(dead_code)]
    pub fn is_recording(&self) -> bool {
        self.is_recording.load(Ordering::SeqCst)
    }
}

/// Audio data result
pub struct AudioData {
    /// Path to temporary WAV file
    pub file_path: String,
    /// Sample rate
    pub sample_rate: u32,
    /// Duration in seconds
    pub duration_secs: f32,
    /// Number of samples
    pub sample_count: usize,
}

/// Create a unique temporary file path for WAV audio
fn create_temp_wav_path() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();

    let temp_dir = std::env::temp_dir();
    let filename = format!("speekium_ptt_{}.wav", timestamp);
    temp_dir.join(filename).to_string_lossy().to_string()
}

/// Run the recording in a dedicated thread
fn run_recording_thread(
    is_recording: Arc<AtomicBool>,
    buffer: Arc<Mutex<Vec<f32>>>,
    rx: Receiver<RecordingCommand>,
) -> Result<(), String> {
    // Get default host and input device
    let host = cpal::default_host();
    let device = host.default_input_device()
        .ok_or_else(|| "No input device available".to_string())?;


    // Configure stream
    let config = find_suitable_config(&device)?;
    let actual_sample_rate = config.sample_rate();
    let actual_channels = config.channels();


    // Create error callback
    let err_fn = |_err| {
    };

    // Clone shared state for the callback
    let buffer_clone = buffer.clone();
    let is_recording_clone = is_recording.clone();

    // Create input stream based on sample format
    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => {
            device.build_input_stream(
                &config.into(),
                move |data: &[f32], _: &cpal::InputCallbackInfo| {
                    if is_recording_clone.load(Ordering::SeqCst) {
                        let processed = process_audio_data(data, actual_sample_rate, actual_channels);
                        if let Ok(mut buf) = buffer_clone.lock() {
                            buf.extend_from_slice(&processed);
                        }
                    }
                },
                err_fn,
                None,
            ).map_err(|e| format!("Failed to build input stream: {}", e))?
        }
        cpal::SampleFormat::I16 => {
            device.build_input_stream(
                &config.into(),
                move |data: &[i16], _: &cpal::InputCallbackInfo| {
                    if is_recording_clone.load(Ordering::SeqCst) {
                        // Convert i16 to f32
                        let float_data: Vec<f32> = data.iter()
                            .map(|&s| s as f32 / i16::MAX as f32)
                            .collect();
                        let processed = process_audio_data(&float_data, actual_sample_rate, actual_channels);
                        if let Ok(mut buf) = buffer_clone.lock() {
                            buf.extend_from_slice(&processed);
                        }
                    }
                },
                err_fn,
                None,
            ).map_err(|e| format!("Failed to build input stream: {}", e))?
        }
        cpal::SampleFormat::U16 => {
            device.build_input_stream(
                &config.into(),
                move |data: &[u16], _: &cpal::InputCallbackInfo| {
                    if is_recording_clone.load(Ordering::SeqCst) {
                        // Convert u16 to f32
                        let float_data: Vec<f32> = data.iter()
                            .map(|&s| (s as f32 / u16::MAX as f32) * 2.0 - 1.0)
                            .collect();
                        let processed = process_audio_data(&float_data, actual_sample_rate, actual_channels);
                        if let Ok(mut buf) = buffer_clone.lock() {
                            buf.extend_from_slice(&processed);
                        }
                    }
                },
                err_fn,
                None,
            ).map_err(|e| format!("Failed to build input stream: {}", e))?
        }
        format => {
            return Err(format!("Unsupported sample format: {:?}", format));
        }
    };

    // Start the stream
    stream.play().map_err(|e| format!("Failed to start stream: {}", e))?;


    // Wait for stop command (with timeout check)
    loop {
        // Check for stop command (non-blocking with timeout)
        match rx.recv_timeout(std::time::Duration::from_millis(100)) {
            Ok(RecordingCommand::Stop) => {
                break;
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                // Continue recording
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                break;
            }
        }

        // Also check recording flag
        if !is_recording.load(Ordering::SeqCst) {
            break;
        }
    }

    // Stream will be dropped here, releasing the audio device
    drop(stream);

    Ok(())
}

/// Find a suitable audio config, preferring 16kHz mono
fn find_suitable_config(device: &cpal::Device) -> Result<cpal::SupportedStreamConfig, String> {
    let supported_configs = device.supported_input_configs()
        .map_err(|e| format!("Failed to get supported configs: {}", e))?;

    let configs: Vec<_> = supported_configs.collect();

    // First, try to find exact 16kHz mono config
    for config in &configs {
        if config.channels() == CHANNELS
            && config.min_sample_rate() <= SAMPLE_RATE
            && config.max_sample_rate() >= SAMPLE_RATE
        {
            return Ok(config.clone().with_sample_rate(SAMPLE_RATE));
        }
    }

    // If no mono config, try any config that supports 16kHz
    for config in &configs {
        if config.min_sample_rate() <= SAMPLE_RATE
            && config.max_sample_rate() >= SAMPLE_RATE
        {
            return Ok(config.clone().with_sample_rate(SAMPLE_RATE));
        }
    }

    // Fallback to default config
    device.default_input_config()
        .map_err(|e| format!("Failed to get default config: {}", e))
}

/// Process audio data: resample to 16kHz and convert to mono if needed
fn process_audio_data(data: &[f32], src_rate: u32, channels: u16) -> Vec<f32> {
    // Convert to mono if stereo
    let mono_data: Vec<f32> = if channels > 1 {
        data.chunks(channels as usize)
            .map(|chunk| chunk.iter().sum::<f32>() / chunk.len() as f32)
            .collect()
    } else {
        data.to_vec()
    };

    // Resample if needed
    if src_rate != SAMPLE_RATE {
        let ratio = SAMPLE_RATE as f64 / src_rate as f64;
        let output_len = (mono_data.len() as f64 * ratio).ceil() as usize;
        let mut result = Vec::with_capacity(output_len);

        for i in 0..output_len {
            let src_idx = i as f64 / ratio;
            let idx = src_idx as usize;
            let frac = src_idx - idx as f64;

            let sample = if idx + 1 < mono_data.len() {
                // Linear interpolation
                mono_data[idx] * (1.0 - frac as f32) + mono_data[idx + 1] * frac as f32
            } else if idx < mono_data.len() {
                mono_data[idx]
            } else {
                0.0
            };

            result.push(sample);
        }
        result
    } else {
        mono_data
    }
}

/// Convert f32 samples to WAV format bytes
fn samples_to_wav(samples: &[f32]) -> Result<Vec<u8>, String> {
    let mut wav = Vec::new();

    // WAV header
    let data_size = (samples.len() * 2) as u32;  // 16-bit = 2 bytes per sample
    let file_size = data_size + 36;

    // RIFF header
    wav.extend_from_slice(b"RIFF");
    wav.extend_from_slice(&file_size.to_le_bytes());
    wav.extend_from_slice(b"WAVE");

    // fmt chunk
    wav.extend_from_slice(b"fmt ");
    wav.extend_from_slice(&16u32.to_le_bytes());  // Chunk size
    wav.extend_from_slice(&1u16.to_le_bytes());   // Audio format (PCM)
    wav.extend_from_slice(&CHANNELS.to_le_bytes());  // Channels
    wav.extend_from_slice(&SAMPLE_RATE.to_le_bytes());  // Sample rate
    let byte_rate = SAMPLE_RATE * CHANNELS as u32 * 2;  // 16-bit
    wav.extend_from_slice(&byte_rate.to_le_bytes());  // Byte rate
    let block_align = CHANNELS * 2;  // 16-bit
    wav.extend_from_slice(&block_align.to_le_bytes());  // Block align
    wav.extend_from_slice(&16u16.to_le_bytes());  // Bits per sample

    // data chunk
    wav.extend_from_slice(b"data");
    wav.extend_from_slice(&data_size.to_le_bytes());

    // Convert f32 samples to i16 and write
    for &sample in samples {
        let clamped = sample.max(-1.0).min(1.0);
        let int_sample = (clamped * i16::MAX as f32) as i16;
        wav.extend_from_slice(&int_sample.to_le_bytes());
    }

    Ok(wav)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_samples_to_wav() {
        let samples = vec![0.0f32; 16000];  // 1 second of silence
        let wav = samples_to_wav(&samples).unwrap();

        // Check RIFF header
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");

        // Check data size
        assert!(wav.len() > 44);  // Header + data
    }
}
