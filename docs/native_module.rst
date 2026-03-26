Native C Module
===============

The SAM renderer is computationally intensive -- pure Python takes ~2 seconds
to render "Hello World" on the Pico. The native C module ``sam_render``
replaces the hot render loop with compiled ARM code, reducing this to ~17ms
(~100x faster).

Use ``sam.info()`` to check whether the native module is active:

.. code-block:: text

   >>> sam.info()
   SAM Speech Synthesizer v1.0.0
     sample rate: 22050 Hz
     native C renderer: active
     audio driver: PIOAudio
     ...

The ``native C renderer`` field shows:

- **active** -- native module loaded and in use
- **not found** -- no ``sam_render.mpy`` on the device (using Python fallback)
- **outdated (recompile for 22050 Hz)** -- old module detected, ignored until recompiled

Using the Pre-built Module
--------------------------

Pre-built modules are included in ``natmod/``:

.. list-table::
   :header-rows: 1
   :widths: 30 20 30

   * - File
     - Platform
     - Architecture
   * - ``sam_render_rp2.mpy``
     - Raspberry Pi Pico
     - armv6m (Cortex-M0+)
   * - ``sam_render_esp32.mpy``
     - ESP32
     - xtensawin

Copy the correct module for your platform:

.. code-block:: bash

   # Raspberry Pi Pico
   mpremote cp natmod/sam_render_rp2.mpy :lib/sam_render.mpy

   # ESP32
   mpremote cp natmod/sam_render_esp32.mpy :lib/sam_render.mpy

.. important::

   The file must be named ``sam_render.mpy`` on the device regardless of
   which platform build you copy. Place it in ``/`` or ``/lib/``.
   The renderer imports ``sam_render`` by name.

The renderer automatically detects and uses the native module when available.
No code changes are needed -- ``sam.say()`` just becomes faster.

Building From Source
--------------------

Prerequisites
^^^^^^^^^^^^^

**Python dependencies** (all platforms):

.. code-block:: bash

   pip install 'pyelftools>=0.25' ar

**MicroPython source tree** (for build headers):

.. code-block:: bash

   git clone --depth 1 https://github.com/micropython/micropython.git

**Cross-compilers** (platform-specific):

.. tabs-start::

RP2040 (Raspberry Pi Pico)
""""""""""""""""""""""""""

.. code-block:: bash

   # macOS
   brew install --cask gcc-arm-embedded

   # Linux (Debian/Ubuntu)
   sudo apt install gcc-arm-none-eabi

ESP32
"""""

The ESP32 uses the Xtensa architecture. Install the toolchain via ESP-IDF:

.. code-block:: bash

   # Clone ESP-IDF
   git clone --depth 1 --recursive --shallow-submodules \
       https://github.com/espressif/esp-idf.git ~/esp-idf

   # Install the ESP32 toolchain
   cd ~/esp-idf
   ./install.sh esp32

   # Add toolchain to PATH (run this before each build session)
   . ~/esp-idf/export.sh

This installs ``xtensa-esp32-elf-gcc`` to ``~/.espressif/tools/``.

.. tabs-end::

Building for RP2040
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   cd natmod/

   # Edit Makefile: set MPY_DIR to your MicroPython source path
   make ARCH=armv6m

   # Output: sam_render.mpy
   # Deploy:
   mpremote cp sam_render.mpy :lib/sam_render.mpy

Building for ESP32
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   cd natmod/

   # Source the ESP-IDF toolchain first
   . ~/esp-idf/export.sh

   # Build for ESP32
   make clean
   make ARCH=xtensawin

   # Output: sam_render.mpy
   # Deploy:
   mpremote cp sam_render.mpy :lib/sam_render.mpy

The Makefile
^^^^^^^^^^^^

.. code-block:: makefile

   MPY_DIR = /path/to/micropython
   MOD = sam_render
   SRC = sam_render.c
   ARCH = armv6m
   LINK_RUNTIME = 1
   include $(MPY_DIR)/py/dynruntime.mk

Override ``ARCH`` on the command line to build for different platforms:

.. list-table::
   :header-rows: 1
   :widths: 25 20 30

   * - Platform
     - ARCH
     - Cross-compiler
   * - Raspberry Pi Pico (RP2040)
     - ``armv6m``
     - ``arm-none-eabi-gcc``
   * - ESP32
     - ``xtensawin``
     - ``xtensa-esp32-elf-gcc``
   * - STM32 F4/F7
     - ``armv7m``
     - ``arm-none-eabi-gcc``

API
---

The native module exports a single function:

.. function:: sam_render.process_frames(freq1, freq2, freq3, amp1, amp2, amp3, pitches, samp_flags, num_frames, speed)

   Render phoneme frame data to an audio buffer using formant synthesis.

   All array arguments are ``bytearray`` objects produced by ``create_frames()``.

   :param bytearray freq1: First formant frequency per frame.
   :param bytearray freq2: Second formant frequency per frame.
   :param bytearray freq3: Third formant frequency per frame.
   :param bytearray amp1: First formant amplitude per frame.
   :param bytearray amp2: Second formant amplitude per frame.
   :param bytearray amp3: Third formant amplitude per frame.
   :param bytearray pitches: Pitch value per frame.
   :param bytearray samp_flags: Sampled consonant flags per frame.
   :param int num_frames: Total number of frames.
   :param int speed: Synthesis speed (ticks per frame, default 72).
   :returns: 8-bit unsigned PCM audio at 22050 Hz.
   :rtype: bytearray

.. data:: sam_render.SAMPLE_RATE
   :value: 22050

   Output sample rate in Hz.

How It Works
------------

The native module implements the same algorithm as the Python renderer:

1. **Formant synthesis** using ``mult_table`` lookups (4-bit quantized sine,
   rectangle wave, amplitude weighting)
2. **Timetable output** for C64-accurate sample spacing at 22050 Hz
3. **Glottal pulse** tracking with phase reset and 75% voiced region
4. **Sampled consonants** for fricatives and plosive bursts

The C code embeds all lookup tables (sinus, rectangle, mult_table,
sample_table, timetable) for zero-overhead access.

Performance
-----------

Rendering "Hello World" on Raspberry Pi Pico (RP2040 @ 125 MHz):

.. list-table::
   :header-rows: 1
   :widths: 30 20

   * - Method
     - Time
   * - Pure Python
     - ~1900 ms
   * - Python + ``@micropython.native``
     - ~1200 ms
   * - Native C module
     - ~17 ms
