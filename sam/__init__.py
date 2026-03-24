"""
SAM (Software Automatic Mouth) - MicroPython Speech Synthesizer

A pure MicroPython port of the classic SAM text-to-speech engine,
originally created for the Commodore 64 in 1982.

Three-stage pipeline:
1. Reciter: English text -> phoneme string
2. Parser:  Phoneme string -> internal phoneme sequence with stress/timing
3. Renderer: Phoneme sequence -> 8-bit PCM audio via formant synthesis

Audio output via PWM on a GPIO pin at ~22 kHz sample rate.

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
from .renderer import render, SAMPLE_RATE


class SAM:
    """
    SAM Speech Synthesizer - main public API.

    Args:
        pin: GPIO pin number for PWM audio output (default 0)
        speed: Speech speed (1-255, default 72). Lower = slower.
        pitch: Voice pitch (1-255, default 64). Higher = higher pitch.
        mouth: Mouth shape (1-255, default 128). Affects formant balance.
        throat: Throat shape (1-255, default 128). Affects formant balance.
    """

    def __init__(self, pin=0, speed=72, pitch=64, mouth=128, throat=128):
        self.speed = speed
        self.pitch = pitch
        self.mouth = mouth
        self.throat = throat
        self._pin = pin
        self._audio = None

    def _get_audio(self):
        """Lazy-initialize the audio driver."""
        if self._audio is None:
            from .audio import PWMAudio
            self._audio = PWMAudio(pin=self._pin, sample_rate=SAMPLE_RATE)
        return self._audio

    def say(self, text):
        """
        Speak English text.

        Converts text to phonemes using the reciter, then synthesizes
        and plays the audio through PWM.

        Args:
            text: English text string to speak
        """
        phonemes = text_to_phonemes(text)
        if phonemes:
            self.say_phonetic(phonemes)

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
            pitch=self.pitch, mouth=self.mouth, throat=self.throat
        )

        # Play through PWM
        audio = self._get_audio()
        audio.play(buffer)

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
            pitch=self.pitch, mouth=self.mouth, throat=self.throat
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

    def stop(self):
        """Stop any current playback and release hardware."""
        if self._audio:
            self._audio.stop()
            self._audio = None
