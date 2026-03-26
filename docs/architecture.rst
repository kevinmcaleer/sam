Architecture
============

SAM was originally created by Mark Barton for the Commodore 64 in 1982. This
port is based on Sebastian Macke's C reverse-engineering of the original 6502
assembly, with additional reference to the discordier/sam JavaScript port and
jacklinquan/micropython-samtts.

Pipeline Overview
-----------------

.. code-block:: text

   English text
        |
        v
   +-----------+     Exception dictionary (exact word match)
   |  Reciter  |     + 200+ context-sensitive rules
   |           |     "ROBOT" -> "ROW4BAHT"
   +-----------+
        |
        v
   +-----------+     Phoneme parsing, diphthong expansion,
   |  Phonemes |     stress propagation, duration assignment,
   |           |     consonant cluster rules, breath insertion
   +-----------+
        |
        v
   +-----------+     Frame expansion, formant transitions,
   |  Renderer |     3-formant additive synthesis,
   |           |     timetable output at 22050 Hz
   +-----------+
        |
        v
   +-----------+     PIO PWM + DMA on RP2040 (jitter-free)
   |   Audio   |     Timer PWM fallback on ESP32
   +-----------+
        |
        v
     Speaker

Reciter
-------

The reciter (``sam/reciter.py``) converts English text to SAM phoneme strings.

**Exception dictionary**: Common words that the rules mispronounce are handled
by a dictionary lookup before rules are applied. This includes words with
open-syllable O (robot, motor, program) and maker/embedded terms (GPIO, UART).

**Rule-based conversion**: Rules are grouped by starting letter and have the
form::

    prefix(match)suffix=phonemes

Wildcards in prefix and suffix patterns:

- ``#`` -- vowel (A E I O U Y)
- ``^`` -- consonant
- ``.`` -- voiced consonant
- ``+`` -- front vowel (E I Y)
- ``:`` -- zero or more consonants
- ``%`` -- common suffix (ER, ES, ED, ING, ELY, EFUL, ENESS)

**Text chunking**: The ``say()`` method automatically splits long text at
punctuation (``. ! ? ; , :``) and word boundaries, rendering and playing
a few words at a time to avoid memory errors on constrained devices.

Phoneme Processor
-----------------

The phoneme processor (``sam/phonemes.py``) applies linguistic transformations
in six stages:

1. **Parser 1** -- convert phoneme codes to internal indices (81 phonemes)
2. **Parser 2** -- diphthong expansion (EY->EY+YX), affricate splitting
   (CH->CH+CH'), consonant voicing (SP->SB after S), T+R->CH+R
3. **Stress propagation** -- copy stress from vowels to preceding voiced consonants
4. **Length assignment** -- base duration from tables (stressed vs unstressed)
5. **Length adjustment** -- seven context rules (lengthen before punctuation,
   shorten before unvoiced stops, etc.)
6. **Breath insertion** -- insert glottal stops at phrase boundaries

Renderer
--------

The renderer (``sam/renderer.py``) generates audio using three-formant additive
synthesis, matching the original C64 SAM algorithm. Output is at the full
22050 Hz sample rate (no downsampling).

Frame Creation
^^^^^^^^^^^^^^

Each phoneme is expanded into multiple frames. Each frame stores:

- F1, F2, F3 frequencies (formant positions)
- F1, F2, F3 amplitudes
- Pitch value (base pitch + stress offset)
- Sampled consonant flag

Transitions between phonemes are smoothed using a blend rank system with
linear interpolation.

Formant Synthesis
^^^^^^^^^^^^^^^^^

For voiced phonemes, each synthesis tick produces one output sample:

.. code-block:: text

   sample = mult_table[sinus[phase1] | amplitude1]   -- F1 (sine)
          + mult_table[sinus[phase2] | amplitude2]   -- F2 (sine)
          + mult_table[rectangle[phase3] | amplitude3] -- F3 (rectangle)

The ``mult_table`` combines a 4-bit quantized sine value (high nibble) with
a 4-bit amplitude (low nibble) in a single table lookup -- faster than
multiplication on the original 6502 and on MicroPython.

Glottal Pulse
^^^^^^^^^^^^^

The glottal pulse simulates vocal cord vibration:

- All three oscillator phases reset to zero at each glottal pulse boundary
- The pulse period is controlled by ``pitches[frame]``
- Phases advance only during the first 75% of each pulse period
- The remaining 25% is used for voiced sampled consonant interleaving

Timetable Output
^^^^^^^^^^^^^^^^

The output buffer uses a timetable for C64-accurate sample spacing at 22050 Hz.
Each tick writes 5 identical samples at a timetable-determined position.

Sampled Consonants
^^^^^^^^^^^^^^^^^^

Fricatives (S, SH, F, TH, /H, /X) and plosive bursts use bit-packed
sample data from a 1280-byte table, producing noise-like waveforms that
are output through the timetable system.

Audio Driver
------------

**PIO Audio (RP2040)**:

An 8-instruction PIO program generates PWM with 8-bit duty cycle resolution.
DMA feeds 8-bit samples from the audio buffer to the PIO FIFO as packed
32-bit words (4 samples per word). The PIO unpacks them via autopull and
``out x, 8``. The clock divider is tuned so each PWM cycle takes exactly
1/22050 seconds.

This provides zero-jitter sample output with no CPU involvement during
playback -- similar to the hardware-timed output the C64's SID chip provided.

**PWM Audio (fallback)**:

On non-RP2040 platforms, a timer interrupt updates the hardware PWM duty
cycle at the sample rate. A tight-loop fallback is used if timer interrupts
are unavailable.

Singing
-------

The ``sing()`` method renders syllables at different pitches and concatenates
them into continuous phrase buffers with precise beat timing:

1. Each note's ``speed`` is scaled proportional to its beat duration
2. Syllables are rendered via ``generate_phonetic()``
3. Buffers are trimmed or silence-padded to exact sample counts
4. A 50ms fade-out is applied at the end of each note
5. Notes are grouped into ~40KB phrases for memory-safe playback

Data Tables
-----------

All synthesis data is stored as ``bytes`` objects in ``sam/tables.py`` for
memory efficiency. Key tables:

.. list-table::
   :header-rows: 1
   :widths: 25 10 40

   * - Table
     - Size
     - Purpose
   * - FREQ1, FREQ2, FREQ3
     - 80 each
     - Formant frequencies per phoneme
   * - AMPL1, AMPL2, AMPL3
     - 80 each
     - Formant amplitudes per phoneme
   * - SINUS
     - 256
     - 4-bit quantized sine wave
   * - RECTANGLE
     - 256
     - Rectangle wave (F3)
   * - MULT_TABLE
     - 256
     - Combined sine*amplitude lookup
   * - SAMPLE_TABLE
     - 1280
     - Bit-packed consonant waveforms
   * - TIME_TABLE
     - 5x5
     - C64 timing emulation
   * - BLEND_RANK
     - 80
     - Transition priority per phoneme
   * - PHONEME_FLAGS
     - 81
     - Classification bits per phoneme

Memory Usage
------------

Approximate RAM usage on RP2040:

.. list-table::
   :header-rows: 1
   :widths: 30 20

   * - Component
     - Bytes
   * - Lookup tables
     - ~3.5 KB
   * - Reciter rules + exceptions
     - ~10 KB
   * - Audio buffer (3-word chunk)
     - ~15 KB
   * - Frame arrays (temp)
     - ~1 KB
   * - Native C module
     - ~3.5 KB
   * - **Total typical**
     - **~33 KB**
