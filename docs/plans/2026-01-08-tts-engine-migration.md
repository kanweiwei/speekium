# TTS Engine Migration Summary

## Created Files

### 1. `tauri-prototype/src-python/tts_engine.py`
Complete TTS engine module with async support for Edge and Piper backends.

**Key Features:**
- **TTSEngine class**: Main TTS engine with async methods
- **Dual backend support**: Edge TTS (online, MP3) and Piper TTS (offline, WAV)
- **Language auto-detection**: Character-based detection for multi-language support
- **Voice caching**: Piper voices cached in memory for fast reuse
- **Base64 encoding**: Returns base64 encoded audio for web transmission
- **Async design**: All operations are async-friendly
- **Error handling**: Automatic fallback between backends

**Methods:**
- `generate_async()`: Main TTS generation (async)
- `_generate_edge()`: Edge TTS implementation (MP3)
- `_generate_piper()`: Piper TTS implementation (WAV)
- `_synthesize_piper()`: Synchronous Piper synthesis
- `play_audio_async()`: Play audio from base64 (platform-specific)
- `detect_text_language()`: Auto-detect language from text
- `load_piper_voice()`: Load and cache Piper models
- `shutdown()`: Cleanup resources

**Models:**
- `TTSRequest`: Request model with text, language, backend, voice, rate
- `TTSResult`: Result model with audio_base64, format, error

## Updated Files

### `tauri-prototype/backend.py`
Integrated TTSEngine into PyTauri backend.

**Changes:**
1. Added imports for tts_engine
2. Created `get_tts_engine_instance()` singleton function
3. Added `generate_tts` command for TTS generation
4. Added `play_tts` command for audio playback
5. Updated `ChatRequest` to include `generate_audio` parameter
6. Enhanced `chat_generator` to optionally generate TTS audio
7. Updated main() function to show TTS commands
8. Fixed `get_config` to handle None config

**New `generate_tts` Command:**
```python
@commands.command()
async def generate_tts(body: TTSRequest, app_handle: AppHandle) -> TTSResult:
    """
    Generate TTS audio using specified backend

    Args:
        body.text: Text to convert to speech
        body.language: Language code (e.g., 'zh', 'en', 'auto')
        body.backend: 'edge' (online, MP3) or 'piper' (offline, WAV)
        body.voice: Optional voice override
        body.rate: Speech rate for Edge TTS (e.g., '+0%', '+10%', '-10%')

    Returns:
        TTSResult with base64 encoded audio
    """
```

**New `play_tts` Command:**
```python
@commands.command()
async def play_tts(audio_base64: str, audio_format: str, app_handle: AppHandle) -> Dict[str, Any]:
    """
    Play audio from base64 encoded data

    Args:
        audio_base64: Base64 encoded audio data
        audio_format: Audio MIME type (e.g., 'audio/mp3', 'audio/wav')

    Returns:
        Success status
    """
```

### `tauri-prototype/src/useTauriAPI.ts`
Added TTS API functions for frontend integration.

**Changes:**
1. Added `TTSResult` interface for type safety
2. Updated `ChatChunk` interface to include `audioFormat` field
3. Added `chatGenerator()` parameter `generateAudio` for optional TTS
4. Updated `processChatChunks()` to handle audio playback
5. Added `generateTTS()` function for TTS generation
6. Added `playTTS()` function for TTS playback
7. Added `playBase64Audio()` function for frontend playback
8. Added `base64ToUint8Array()` helper function

**New TypeScript Functions:**
```typescript
// Generate TTS audio
export async function generateTTS(
  text: string,
  language: string = 'auto',
  backend: 'edge' | 'piper' = 'edge',
  voice?: string,
  rate: string = '+0%'
): Promise<TTSResult>

// Play TTS audio (backend)
export async function playTTS(
  audioBase64: string,
  audioFormat: string = 'audio/mp3'
): Promise<boolean>

// Play TTS audio (frontend implementation)
export async function playBase64Audio(
  audioBase64: string,
  audioFormat: string = 'audio/mp3'
): Promise<void>
```

## Architecture

```
React Frontend (useTauriAPI.ts)
    ↓ invoke('generate_tts', { body: {...} })
    ↓ invoke('chat_generator', { text, generateAudio: true })
PyTauri Commands (backend.py)
    ↓ get_tts_engine_instance()
TTSEngine (tts_engine.py)
    ↓ generate_async(TTSRequest)
    ↓ route to backend
    ↓ _generate_edge() or _generate_piper()
Edge TTS (online, MP3)
    ↓ edge_tts.Communicate.stream()
    ↓ async for chunk in communicate
    ↓ collect audio bytes
    ↓ base64 encoding
TTSResult { audio_base64, format }
    ↓ return to frontend
React Frontend
    ↓ processChatChunks() or playBase64Audio()
    ↓ base64ToUint8Array()
    ↓ new Blob([...], { type: format })
    ↓ new Audio(url).play()
    ↓ User hears TTS
```

## Configuration Constants

All TTS configuration is in `tts_engine.py`:
- `DEFAULT_LANGUAGE`: "zh" (default language)
- `EDGE_TTS_VOICES`: Voice mappings for Edge TTS (zh, en, ja, ko, yue)
- `PIPER_VOICES`: Voice mappings for Piper TTS (zh, en)
- `PIPER_DATA_DIR`: ~/.local/share/piper-voices (model storage)

Config can also be overridden at runtime via `config.json`:
- `tts_backend`: "edge" or "piper"
- `tts_rate`: Edge TTS rate (e.g., "+0%", "+10%", "-10%")

## Key Improvements from Original

1. **Async-first design**: All TTS operations are async-friendly
2. **Base64 encoding**: Direct base64 return instead of file paths
3. **Dual backend support**: Seamless Edge (online) and Piper (offline) switching
4. **Automatic fallback**: Piper fails → Edge, Edge fails → attempt fallback
5. **Voice caching**: Piper models loaded once and cached
6. **Language detection**: Auto-detect from text content
7. **Modular structure**: Separate TTS module for easy maintenance
8. **Type hints**: Full Pydantic models for validation
9. **Error handling**: Comprehensive logging and graceful degradation
10. **Frontend playback**: Both backend and frontend audio playback options

## Backend Comparison

| Feature | Edge TTS | Piper TTS |
|---------|-----------|-------------|
| **Quality** | High (online neural) | Medium (local ONNX) |
| **Speed** | Medium (network dependent) | Fast (local) |
| **Offline** | ❌ Requires internet | ✅ Fully offline |
| **Format** | MP3 | WAV |
| **Latency** | Higher (network) | Lower (local) |
| **Best For** | Normal use, high quality | Offline/Raspberry Pi |

## Testing

To test the new TTS functionality:

```bash
cd tauri-prototype
npm run tauri dev
```

### Test 1: Edge TTS Generation
```typescript
// In Tauri app console
const result = await invoke('generate_tts', {
  body: {
    text: '你好，这是一个测试',
    language: 'zh',
    backend: 'edge',
    rate: '+0%'
  }
});

console.log('Success:', result.success);
console.log('Format:', result.format);
console.log('Audio length:', result.audio_base64?.length);
```

### Test 2: Piper TTS Generation
```typescript
// In Tauri app console
const result = await invoke('generate_tts', {
  body: {
    text: '你好，这是一个测试',
    language: 'zh',
    backend: 'piper'
  }
});

console.log('Success:', result.success);
console.log('Format:', result.format);
```

### Test 3: Chat with TTS
```typescript
// In Tauri app
const chunks = await invoke('chat_generator', {
  text: '你好',
  language: 'auto',
  history: [],
  generateAudio: true
});

// Process chunks (will play audio)
for (const chunk of chunks) {
  if (chunk.type === 'complete' && chunk.audio) {
    console.log('Playing TTS audio...');
  }
}
```

### Test 4: Frontend Audio Playback
```typescript
// Using frontend playback
import { playBase64Audio } from './useTauriAPI';

const base64Audio = '...'; // Your base64 audio data
await playBase64Audio(base64Audio, 'audio/mp3');
```

## Usage Examples

### Example 1: Simple TTS Generation
```typescript
import { generateTTS } from './useTauriAPI';

const result = await generateTTS('你好世界', 'zh', 'edge');
if (result.success && result.audio_base64) {
  console.log('Audio generated:', result.format);
}
```

### Example 2: Chat with Automatic TTS
```typescript
import { chatGenerator } from './useTauriAPI';

const result = await chatGenerator(
  'What is the capital of France?',
  'en',
  [],
  true  // Enable TTS
);

for (const chunk of result.chunks) {
  if (chunk.type === 'complete' && chunk.content) {
    console.log('Assistant:', chunk.content);
    // TTS audio will be included and played automatically
  }
}
```

### Example 3: Custom Voice and Rate
```typescript
import { generateTTS } from './useTauriAPI';

// Faster speech with different voice
const result = await generateTTS(
  'This is a test',
  'en',
  'edge',
  'en-US-JennyNeural',  // Custom voice
  '+20%'  // 20% faster
);
```

## Next Steps

1. ✅ Create `tts_engine.py` module
2. ✅ Integrate with `backend.py`
3. ✅ Add TypeScript API functions
4. ⏳ Test TTS generation (Edge and Piper)
5. ⏳ Test chat with TTS integration
6. ⏳ Add system integration (tray, hotkeys)
7. ⏳ Create comprehensive settings UI
8. ⏳ Add streaming TTS with barge-in support

## Notes

- The TTS engine maintains all logic from `speekium.py` (generate_audio, Edge TTS, Piper TTS)
- Edge TTS uses native async API, no threading needed
- Piper TTS blocking synthesis runs in ThreadPoolExecutor
- Automatic fallback: Piper → Edge on failure, Edge → attempt Piper fallback
- Audio format: MP3 for Edge, WAV for Piper (automatically detected)
- Base64 encoding is done server-side for efficient web transmission
- Frontend can play audio using native HTML5 Audio or backend playback
- All configuration is loaded from `config.json` with sensible defaults
- Voice models for Piper need to be downloaded manually to `~/.local/share/piper-voices`

## Dependencies

Required Python packages:
- `edge-tts`: Edge TTS (online, async)
- `piper-tts`: Piper TTS (offline, requires model files)
- `pydantic`: Type validation for request/response models

Optional (for local development):
- `pip install edge-tts`
- `pip install piper-tts`

Piper voice models (download from Hugging Face):
- Chinese: https://huggingface.co/rhasspy/piper-voices/tree/main/zh/zh_CN/huayan/medium
- English: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/amy/medium
