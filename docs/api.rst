API Reference
=============

SAM Class
---------

.. module:: sam

.. data:: VOICES

   Dictionary of voice presets. Each entry maps a name to a tuple of
   ``(speed, pitch, mouth, throat)``. Add custom presets at runtime:

   .. code-block:: python

      from sam import VOICES
      VOICES['deep'] = (80, 40, 180, 110)

.. class:: SAM(pin=0, speed=72, pitch=64, mouth=128, throat=128, voice=None)

   Main public API for the SAM speech synthesizer.

   :param int pin: GPIO pin number for audio output.
   :param int speed: Speech speed (1-255, default 72). Higher values produce slower speech.
   :param int pitch: Voice pitch (1-255, default 64). Higher values produce a higher-pitched voice.
   :param int mouth: Mouth shape parameter (1-255, default 128). Affects formant balance.
   :param int throat: Throat shape parameter (1-255, default 128). Affects formant balance.
   :param str voice: Optional voice preset name (overrides other parameters).

   .. method:: say(text, chunk_words=3)

      Speak English text. Automatically splits long text into small chunks
      at punctuation and word boundaries to avoid memory errors.

      :param str text: English text to speak.
      :param int chunk_words: Maximum words per chunk (default 3). Lower = less RAM.

      .. code-block:: python

         sam.say("Hello World")
         sam.say("A very long passage of text that will be chunked automatically.")

   .. method:: say_phonetic(phoneme_str)

      Speak from a SAM phoneme string directly, bypassing the reciter.

      :param str phoneme_str: SAM phoneme string (e.g. ``"/HEH4LOW WERLD"``).

      .. code-block:: python

         sam.say_phonetic("/HEH4LOW WERLD")

   .. method:: sing(melody, bpm=80)

      Sing a melody with precise beat timing. Each syllable is rendered to
      exact duration and played as continuous phrases.

      :param list melody: List of ``(pitch, phonemes, beats)`` tuples.
         ``pitch`` is the SAM pitch value (lower = higher note, 0 = rest).
         ``phonemes`` is a SAM phoneme string for the syllable.
         ``beats`` is the duration as a float (1.0 = quarter note).
      :param int bpm: Tempo in beats per minute (default 80).

      .. code-block:: python

         melody = [
             (64, 'DEY4', 1.5),
             (76, 'ZIY',  1.5),
             (96, 'DEY4', 1.5),
         ]
         sam.sing(melody, bpm=80)

   .. method:: generate(text)

      Generate audio buffer from English text without playing it.

      :param str text: English text to speak.
      :returns: 8-bit unsigned PCM audio data at 22050 Hz.
      :rtype: bytearray

   .. method:: generate_phonetic(phoneme_str)

      Generate audio buffer from a phoneme string without playing.

      :param str phoneme_str: SAM phoneme string.
      :returns: 8-bit unsigned PCM audio data at 22050 Hz.
      :rtype: bytearray

   .. method:: text_to_phonemes(text)

      Convert English text to a SAM phoneme string. Useful for debugging
      and tuning pronunciation.

      :param str text: English text.
      :returns: Phoneme string.
      :rtype: str

      .. code-block:: python

         >>> sam.text_to_phonemes("Hello")
         '/HEHLOW'

   .. method:: set_voice(name)

      Apply a voice preset by name.

      :param str name: Preset name (e.g. ``'robot'``, ``'elf'``).
      :raises ValueError: If the preset name is not found.

   .. staticmethod:: list_voices()

      Print all available voice presets with their parameters.

   .. method:: set_speed(speed)

      Set speech speed.

      :param int speed: Speed value 1-255 (default 72). Higher = slower.

   .. method:: set_pitch(pitch)

      Set voice pitch.

      :param int pitch: Pitch value 1-255 (default 64). Higher = higher pitch.

   .. method:: set_mouth(mouth)

      Set mouth shape parameter. Affects first formant (F1) balance.

      :param int mouth: Mouth value 1-255 (default 128).

   .. method:: set_throat(throat)

      Set throat shape parameter. Affects second formant (F2) balance.

      :param int throat: Throat value 1-255 (default 128).

   .. method:: info()

      Print diagnostic information: sample rate, native module status,
      audio driver type, PIO availability, and current voice parameters.

   .. method:: save_wav(text, filename)

      Render text to speech and save as a WAV file.

      :param str text: English text to speak.
      :param str filename: Output WAV file path.
      :returns: The filename.
      :rtype: str

   .. method:: stop()

      Stop any current playback and release hardware resources.


Audio Output
------------

.. module:: sam.audio

.. data:: SAMPLE_RATE
   :value: 22050

   The audio sample rate in Hz.

.. class:: PIOAudio(pin=0, sample_rate=22050, sm_id=0)

   PIO-driven PWM audio output for RP2040. Uses a PIO state machine to
   generate an 8-bit PWM waveform with cycle-accurate timing, and DMA to
   feed samples from the buffer. Falls back to manual FIFO feeding if
   DMA is unavailable.

   This is the default audio driver on RP2040.

   :param int pin: GPIO pin number.
   :param int sample_rate: Playback sample rate in Hz.
   :param int sm_id: PIO state machine ID (0-7).

   .. method:: play(buffer)

      Play an audio buffer. Sets up the PIO state machine and DMA,
      then blocks until playback completes.

      :param buffer: 8-bit unsigned PCM samples.
      :type buffer: bytearray or bytes

   .. method:: stop()

      Stop playback and release PIO/DMA resources.

   .. attribute:: is_playing
      :type: bool

      ``True`` if audio is currently playing.

.. class:: PWMAudio(pin=0, sample_rate=22050)

   Fallback PWM audio output using hardware PWM and timer interrupts.
   Used on ESP32 and other non-RP2040 platforms.

   :param int pin: GPIO pin number.
   :param int sample_rate: Playback sample rate in Hz.

   .. method:: play(buffer)

      Play an audio buffer through PWM. Uses a timer interrupt for sample
      timing, with a tight-loop fallback.

      :param buffer: 8-bit unsigned PCM samples.
      :type buffer: bytearray or bytes

   .. method:: stop()

      Stop playback and release PWM hardware.

   .. attribute:: is_playing
      :type: bool

      ``True`` if audio is currently playing.

.. class:: WavWriter(filename, sample_rate=22050)

   Write audio samples to a WAV file.

   :param str filename: Output file path.
   :param int sample_rate: Sample rate for the WAV header.

   .. method:: write(buffer)

      Write 8-bit unsigned PCM buffer as a WAV file.

      :param buffer: Audio sample data.
      :type buffer: bytearray or bytes


Renderer
--------

.. module:: sam.renderer

.. data:: SAMPLE_RATE
   :value: 22050

   The output sample rate in Hz (full rate, no downsampling).

.. function:: render(phoneme_index, phoneme_length, stress, speed=72, pitch=64, mouth=128, throat=128)

   Render processed phoneme data to an audio buffer. If the native C module
   ``sam_render`` is available (and up to date), uses it for ~100x faster rendering.

   :param list phoneme_index: Phoneme index array from ``process_phonemes()``.
   :param list phoneme_length: Duration array from ``process_phonemes()``.
   :param list stress: Stress array from ``process_phonemes()``.
   :param int speed: Synthesis speed (ticks per frame).
   :param int pitch: Base pitch value.
   :param int mouth: Mouth shape parameter.
   :param int throat: Throat shape parameter.
   :returns: 8-bit unsigned PCM audio data at 22050 Hz.
   :rtype: bytearray


Phoneme Processor
-----------------

.. module:: sam.phonemes

.. function:: process_phonemes(input_str, speed=72)

   Full phoneme processing pipeline. Converts a phoneme string into
   arrays ready for rendering.

   Stages:

   1. Parse phoneme codes to internal indices
   2. Apply transformation rules (diphthongs, affricates, consonant clusters)
   3. Propagate stress markers
   4. Assign phoneme durations
   5. Apply context-dependent length adjustments
   6. Insert breath pauses

   :param str input_str: SAM phoneme string (e.g. ``"HEH4LOW WERLD"``).
   :param int speed: Speech speed (kept for API compatibility).
   :returns: Tuple of ``(phoneme_index, phoneme_length, stress)``.
   :rtype: tuple


Reciter
-------

.. module:: sam.reciter

.. data:: EXCEPTIONS

   Dictionary mapping uppercase words to SAM phoneme strings. Checked before
   the rule-based reciter. Add entries for words that SAM mispronounces:

   .. code-block:: python

      from sam.reciter import EXCEPTIONS
      EXCEPTIONS['YOURWORD'] = 'YOHR4WERD'

.. function:: text_to_phonemes(text)

   Convert English text to a SAM phoneme string. Checks the exception
   dictionary first, then applies rule-based pronunciation using 200+
   context-sensitive rules organized by starting letter.

   :param str text: English text.
   :returns: SAM phoneme string with stress markers.
   :rtype: str

   .. code-block:: python

      >>> text_to_phonemes("Hello World")
      '/HEHLOW WERLD'
      >>> text_to_phonemes("Robot")
      'ROW4BAHT'
