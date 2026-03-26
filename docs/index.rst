MicroPython SAM
===============

A pure MicroPython port of **SAM (Software Automatic Mouth)**, the classic
text-to-speech engine originally created for the Commodore 64 in 1982.

SAM converts English text to speech using a three-stage pipeline:

1. **Reciter** -- rule-based English text to phoneme conversion with exception dictionary
2. **Phoneme processor** -- phoneme parsing, stress assignment, and duration rules
3. **Renderer** -- three-formant additive synthesis at 22050 Hz

Audio output uses PIO-driven PWM with DMA on the RP2040 for jitter-free playback.
An optional native C module provides ~100x faster rendering.

.. code-block:: python

   from sam import SAM

   sam = SAM(pin=0)
   sam.say("Hello World")

   # Voice presets
   sam.set_voice('robot')
   sam.say("I am a robot")

   # Diagnostics
   sam.info()

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quickstart
   api
   phonemes
   hardware
   native_module
   architecture
