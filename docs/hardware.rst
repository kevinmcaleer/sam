Hardware Setup
==============

Supported Platforms
-------------------

- **Raspberry Pi Pico** (RP2040) -- primary target, PIO audio + native C module
- **ESP32** -- compatible (PWM fallback, native C module requires Xtensa build)
- **Desktop Python** -- WAV file generation for testing

.. note::

   On RP2040, SAM uses PIO-driven PWM with DMA for jitter-free audio output.
   On other platforms, it falls back to timer-based PWM.
   Use ``sam.info()`` to see which audio driver is active.

Circuit
-------

Minimal setup requires just a GPIO pin, a resistor, and a speaker:

.. code-block:: text

       Pico                    Speaker
   +---------+              +----------+
   |         |   1K ohm     |          |
   |  GP0  --+---[====]-----+  (+)     |
   |         |              |          |
   |   GND --+--------------+  (-)     |
   |         |              |          |
   +---------+              +----------+

**Components:**

- **1K resistor** -- limits current to protect the GPIO pin
- **Speaker** -- 8 ohm or piezo buzzer
- **100nF capacitor** (optional) -- across speaker terminals for LC filtering

Pin Selection
-------------

**Raspberry Pi Pico:**

Any GPIO pin works. The default is GP0.

.. code-block:: python

   sam = SAM(pin=0)   # GP0
   sam = SAM(pin=15)  # GP15

**ESP32:**

Use any GPIO capable of PWM output. GPIO 25 and 26 are common choices.

.. code-block:: python

   sam = SAM(pin=25)

Audio Output Details
--------------------

**RP2040 (PIO Audio):**

.. list-table::
   :widths: 30 30

   * - Sample rate
     - 22050 Hz
   * - Bit depth
     - 8-bit unsigned PCM
   * - PWM method
     - PIO state machine (8-bit resolution, ~22 kHz carrier)
   * - Sample delivery
     - DMA (zero CPU involvement during playback)
   * - Jitter
     - None (cycle-accurate PIO timing)

**ESP32 / Fallback (Timer PWM):**

.. list-table::
   :widths: 30 30

   * - Sample rate
     - 22050 Hz
   * - PWM carrier
     - 40 kHz
   * - Sample delivery
     - Timer interrupt
   * - Jitter
     - Low (dependent on ISR latency)

Improving Audio Quality
-----------------------

For better sound quality:

1. **RC low-pass filter** -- Add a 10K resistor + 10nF capacitor between the
   GPIO and speaker to filter the PWM carrier.

2. **Audio amplifier** -- Use a PAM8403 or LM386 amplifier module for louder,
   cleaner output.

3. **Larger speaker** -- A 40mm or larger speaker produces clearer speech than
   a piezo buzzer.
