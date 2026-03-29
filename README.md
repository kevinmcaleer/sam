# MicroPython SAM

A MicroPython port of **SAM (Software Automatic Mouth)**, the classic text-to-speech engine originally created for the Commodore 64 in 1982.

SAM runs on a Raspberry Pi Pico with just a speaker and an optional resistor. It uses PIO-driven PWM with DMA for jitter-free audio output at 22050 Hz.

```
GPIO pin --[1K resistor]--> Speaker(+) --> GND
```

## Quick Start

```python
from sam import SAM

sam = SAM(pin=0)
sam.say("Hello World")
```

## Voice Presets

```python
sam = SAM(pin=0, voice='robot')
sam.say("I am a robot")

sam.set_voice('elf')
sam.say("hello tiny world")

sam.set_voice('giant')
sam.say("fee fi fo fum")

# See all presets
sam.list_voices()
```

Built-in voices: `sam`, `robot`, `elf`, `old_man`, `whisper`, `alien`, `giant`, `child`, `stuffy`.

Add your own:

```python
from sam import VOICES
VOICES['squeaky'] = (60, 120, 100, 180)  # (speed, pitch, mouth, throat)
```

## Long Text

Large text is automatically chunked to avoid memory errors:

```python
sam.say("I can speak long passages of text. It breaks them into small "
        "chunks at punctuation boundaries, renders each chunk, and plays "
        "them in sequence.")
```

## Singing

```python
N = {'C3':96, 'D3':86, 'E3':76, 'F3':72, 'G3':64, 'A3':57, 'B3':51,
     'C4':48, 'D4':43, 'E4':38, 'F4':36, 'G4':32, 'R':0}

# Each tuple: (pitch, phonemes, beats)
melody = [
    (N['G3'], 'DEY4', 1.5),
    (N['E3'], 'ZIY',  1.5),
    (N['C3'], 'DEY4', 1.5),
    (N['C3'], 'ZIY',  1.5),
]

sam.sing(melody, bpm=80)
```

## Fixing Pronunciation

Words the rules get wrong can be added to the exception dictionary in `sam/reciter.py`:

```python
EXCEPTIONS = {
    'ROBOT': 'ROW4BAHT',
    'YOURWORD': 'YOHR4WERD',
}
```

Or bypass the reciter entirely:

```python
sam.say_phonetic("/HEH4LOW WERLD")
```

## Diagnostics

```python
>>> sam.info()
SAM Speech Synthesizer v1.0.0
  sample rate: 22050 Hz
  native C renderer: active
  audio driver: PIOAudio
  PIO available: True
  pin: 0
  speed: 72  pitch: 64  mouth: 128  throat: 128
```

## Installation

```bash
# Copy SAM to the Pico
mpremote cp -r sam :sam

# Optional: install native C module for ~100x faster rendering
mpremote cp natmod/sam_render_rp2.mpy :lib/sam_render.mpy
```

## Hardware

- **Raspberry Pi Pico** (RP2040) -- PIO audio with DMA, native C module included
- **ESP32** -- PWM fallback, native C module requires Xtensa build
- **Desktop Python** -- WAV file generation for testing

For louder output, add a PAM8403 amplifier module (~$1).

## Troubleshooting

**`NotImplementedError: native method too big`** — The `sam_render.mpy` file on your board was compiled for a different MicroPython version. Either remove it (SAM will fall back to the Python renderer) or recompile it against your MicroPython version's headers:

```bash
# Remove the incompatible module
mpremote rm :lib/sam_render.mpy

# Or recompile (see docs/native_module.rst)
cd natmod && make ARCH=armv6m
mpremote cp sam_render.mpy :lib/sam_render.mpy
```

**`MemoryError: memory allocation failed`** — Text is too long for a single render. Lower the `chunk_words` parameter:

```python
sam.say("long text here...", chunk_words=2)
```

## Documentation

Full documentation is in the [`docs/`](docs/) folder:

- [Quick Start](docs/quickstart.rst) -- setup, installation, basic usage
- [API Reference](docs/api.rst) -- all classes, methods, and parameters
- [Phoneme Reference](docs/phonemes.rst) -- the 81 SAM phoneme codes
- [Hardware Setup](docs/hardware.rst) -- circuits, pin selection, audio quality
- [Native Module](docs/native_module.rst) -- building and using the C accelerator
- [Architecture](docs/architecture.rst) -- how the pipeline works internally

## Credits

- Original SAM by Mark Barton (1982)
- C reverse-engineering by Sebastian Macke
- JavaScript port by [discordier/sam](https://github.com/discordier/sam)
- MicroPython reference by [jacklinquan/micropython-samtts](https://github.com/jacklinquan/micropython-samtts)
