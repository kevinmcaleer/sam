"""
SAM (Software Automatic Mouth) - MicroPython Speech Synthesizer

A pure MicroPython port of the classic SAM text-to-speech engine,
originally created for the Commodore 64 in 1982.

Three-stage pipeline:
1. Reciter: English text -> phoneme string
2. Parser:  Phoneme string -> internal phoneme sequence with stress/timing
3. Renderer: Phoneme sequence -> 8-bit PCM audio via formant synthesis

Audio output via PIO-driven PWM on a GPIO pin at 22050 Hz sample rate.
Falls back to timer-based PWM on non-RP2040 platforms.

Usage:
    from sam import SAM
    sam = SAM(pin=0)
    sam.say("hello world")
    sam.say_phonetic("/HEH4LOW WERLD")

Hardware:
    GPIO pin --[1K resistor]--> speaker --> GND
    Optional: 100nF cap across speaker for LC filtering
"""

__version__ = '1.0.0'

from .reciter import text_to_phonemes
from .phonemes import process_phonemes
from .renderer import render, SAMPLE_RATE, _HAS_NATIVE, _NATIVE_STATUS


# Voice presets: (speed, pitch, mouth, throat)
VOICES = {
    'sam':       (72, 64, 128, 128),   # Default SAM voice
    'robot':     (72, 96, 128, 128),   # Robotic monotone
    'elf':       (72, 72, 110, 160),   # High, thin voice
    'old_man':   (82, 72, 145, 130),   # Slow, deep, gravelly
    'whisper':   (72, 64, 80, 160),    # Breathy whisper
    'alien':     (60, 64, 150, 200),   # Strange, otherworldly
    'giant':     (82, 40, 190, 110),   # Deep, booming
    'child':     (68, 96, 110, 140),   # High, small
    'stuffy':    (72, 64, 160, 100),   # Nasal, congested
}


class SAM:
    """
    SAM Speech Synthesizer - main public API.

    Args:
        pin: GPIO pin number for PWM audio output (default 0)
        speed: Speech speed (1-255, default 72). Lower = slower.
        pitch: Voice pitch (1-255, default 64). Higher = higher pitch.
        mouth: Mouth shape (1-255, default 128). Affects formant balance.
        throat: Throat shape (1-255, default 128). Affects formant balance.
        voice: Optional preset name (overrides speed/pitch/mouth/throat).
    """

    def __init__(self, pin=0, speed=72, pitch=64, mouth=128, throat=128, voice=None):
        self._pin = pin
        self._audio = None
        if voice:
            self.set_voice(voice)
        else:
            self.speed = speed
            self.pitch = pitch
            self.mouth = mouth
            self.throat = throat

    def _get_audio(self):
        """Lazy-initialize the audio driver. Prefers PIO on RP2040."""
        if self._audio is None:
            try:
                from .audio import PIOAudio, _HAS_PIO
                if _HAS_PIO:
                    self._audio = PIOAudio(pin=self._pin, sample_rate=SAMPLE_RATE)
                else:
                    raise ImportError
            except (ImportError, Exception):
                from .audio import PWMAudio
                self._audio = PWMAudio(pin=self._pin, sample_rate=SAMPLE_RATE)
        return self._audio

    def say(self, text, chunk_words=3):
        """
        Speak English text. Automatically chunks long text to avoid
        memory errors, rendering and playing a few words at a time.

        Args:
            text: English text string to speak
            chunk_words: Max words per chunk (default 3). Lower = less RAM.
        """
        import gc
        for chunk in self._chunk_text(text, chunk_words):
            phonemes = text_to_phonemes(chunk)
            if phonemes and phonemes.strip():
                self.say_phonetic(phonemes)
                gc.collect()

    def say_phonetic(self, phoneme_str):
        """
        Speak from a phoneme string directly (bypass the reciter).

        Phoneme format uses SAM phoneme codes:
            /HEH4LOW WERLD
        Stress markers 1-8 follow the stressed vowel.

        Args:
            phoneme_str: SAM phoneme string
        """
        # Strip leading '/' if present (common SAM convention)
        if phoneme_str.startswith('/'):
            phoneme_str = phoneme_str[1:]

        # Process phonemes through the parser pipeline
        phoneme_index, phoneme_length, stress = process_phonemes(
            phoneme_str, self.speed
        )

        # Render to audio samples
        buffer = render(
            phoneme_index, phoneme_length, stress,
            speed=self.speed, pitch=self.pitch,
            mouth=self.mouth, throat=self.throat
        )

        # Play through PWM
        audio = self._get_audio()
        audio.play(buffer)

    @staticmethod
    def _chunk_text(text, chunk_words):
        """Split text into chunks at punctuation, then by word count."""
        # Split on any punctuation that represents a pause
        clauses = []
        current = []
        for ch in text:
            current.append(ch)
            if ch in '.!?;,:':
                clauses.append(''.join(current).strip())
                current = []
        if current:
            trail = ''.join(current).strip()
            if trail:
                clauses.append(trail)

        # Further split long clauses into word groups
        for clause in clauses:
            words = clause.split()
            if not words:
                continue
            for i in range(0, len(words), chunk_words):
                chunk = ' '.join(words[i:i + chunk_words])
                if chunk.strip():
                    yield chunk

    def sing(self, melody, bpm=80):
        """
        Sing a melody with precise beat timing.

        Each entry in melody is (pitch, phonemes, beats):
            pitch:    SAM pitch value (lower = higher note), 0 = rest
            phonemes: SAM phoneme string for the syllable
            beats:    Duration in beats (float, e.g. 1.5 for dotted quarter)

        Renders syllables to exact durations and plays them as continuous
        phrases to eliminate gaps between notes.

        Args:
            melody: List of (pitch, phonemes, beats) tuples
            bpm: Tempo in beats per minute (default 80)
        """
        import gc

        samples_per_beat = (60 * SAMPLE_RATE) // bpm
        orig_pitch = self.pitch
        orig_speed = self.speed
        audio = self._get_audio()
        fade_len = SAMPLE_RATE // 20  # 50ms fade-out

        # Process melody in groups that fit in ~40KB
        i = 0
        while i < len(melody):
            # Find how many notes fit in this group
            group_samples = 0
            j = i
            while j < len(melody):
                _, _, beats = melody[j]
                n = int(samples_per_beat * beats)
                if group_samples + n > 40000 and j > i:
                    break
                group_samples += n
                j += 1

            # Build the phrase buffer (pre-filled with silence)
            buf = bytearray(b'\x80' * group_samples)
            pos = 0
            for k in range(i, j):
                pitch, phonemes, beats = melody[k]
                target = int(samples_per_beat * beats)
                if pitch > 0 and phonemes:
                    self.pitch = pitch
                    # Scale speed to beat duration: longer notes get more sustain
                    self.speed = max(40, min(200, int(100 * beats)))
                    raw = self.generate_phonetic(phonemes)
                    copy_len = min(len(raw), target)
                    buf[pos:pos + copy_len] = raw[:copy_len]
                    # Fade out to silence at the end of this note
                    fade = min(fade_len, copy_len)
                    fade_start = pos + copy_len - fade
                    for m in range(fade):
                        t = fade - m  # counts down from fade to 0
                        buf[fade_start + m] = 128 + ((buf[fade_start + m] - 128) * t) // fade
                    del raw
                pos += target

            audio.play(buf)
            del buf
            gc.collect()
            i = j

        self.pitch = orig_pitch
        self.speed = orig_speed

    def generate(self, text):
        """
        Generate audio buffer from text without playing it.
        Useful for saving to WAV or custom output.

        Args:
            text: English text string

        Returns:
            bytearray of 8-bit unsigned PCM at ~22,050 Hz
        """
        phonemes = text_to_phonemes(text)
        if not phonemes:
            return bytearray(0)
        return self.generate_phonetic(phonemes)

    def generate_phonetic(self, phoneme_str):
        """
        Generate audio buffer from phoneme string without playing.

        Args:
            phoneme_str: SAM phoneme string

        Returns:
            bytearray of 8-bit unsigned PCM at ~22,050 Hz
        """
        if phoneme_str.startswith('/'):
            phoneme_str = phoneme_str[1:]

        phoneme_index, phoneme_length, stress = process_phonemes(
            phoneme_str, self.speed
        )

        return render(
            phoneme_index, phoneme_length, stress,
            speed=self.speed, pitch=self.pitch,
            mouth=self.mouth, throat=self.throat
        )

    def text_to_phonemes(self, text):
        """
        Convert English text to SAM phoneme string (for debugging/tuning).

        Args:
            text: English text

        Returns:
            Phoneme string
        """
        return text_to_phonemes(text)

    def set_voice(self, name):
        """Apply a voice preset by name. Use list_voices() to see options."""
        name = name.lower()
        if name not in VOICES:
            raise ValueError('Unknown voice: ' + name + '. Use list_voices().')
        self.speed, self.pitch, self.mouth, self.throat = VOICES[name]

    @staticmethod
    def list_voices():
        """Print available voice presets."""
        for name, (spd, pit, mou, thr) in VOICES.items():
            print('  {:10s} speed={} pitch={} mouth={} throat={}'.format(
                name, spd, pit, mou, thr))

    def set_speed(self, speed):
        """Set speech speed (1-255, default 72). Lower = slower."""
        self.speed = max(1, min(255, speed))

    def set_pitch(self, pitch):
        """Set voice pitch (1-255, default 64). Higher = higher pitch."""
        self.pitch = max(1, min(255, pitch))

    def set_mouth(self, mouth):
        """Set mouth shape (1-255, default 128)."""
        self.mouth = max(1, min(255, mouth))

    def set_throat(self, throat):
        """Set throat shape (1-255, default 128)."""
        self.throat = max(1, min(255, throat))

    def save_wav(self, text, filename):
        """
        Render text to speech and save as a WAV file.
        Useful for testing on desktop Python or saving to SD card.

        Args:
            text: English text to speak
            filename: Output WAV file path
        """
        buffer = self.generate(text)
        from .audio import WavWriter
        writer = WavWriter(filename, sample_rate=SAMPLE_RATE)
        writer.write(buffer)
        return filename

    def info(self):
        """Print diagnostic info about the SAM configuration."""
        from .audio import _HAS_PIO
        audio = self._get_audio()
        audio_type = type(audio).__name__
        print('SAM Speech Synthesizer v' + __version__)
        print('  sample rate:', SAMPLE_RATE, 'Hz')
        print('  native C renderer:', _NATIVE_STATUS)
        print('  audio driver:', audio_type)
        print('  PIO available:', _HAS_PIO)
        print('  pin:', self._pin)
        print('  speed:', self.speed, ' pitch:', self.pitch,
              ' mouth:', self.mouth, ' throat:', self.throat)

    def stop(self):
        """Stop any current playback and release hardware."""
        if self._audio:
            self._audio.stop()
            self._audio = None
