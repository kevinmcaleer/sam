Quick Start
===========

Requirements
------------

- Raspberry Pi Pico (RP2040) or ESP32 running MicroPython
- A speaker or piezo buzzer
- 1K resistor

Hardware Setup
--------------

.. code-block:: text

   GPIO pin --[1K resistor]--> Speaker(+) --> GND

Optionally add a 100nF capacitor across the speaker terminals for filtering.

Installation
------------

Copy the ``sam/`` folder to your MicroPython board's filesystem:

.. code-block:: bash

   mpremote cp -r sam :sam

For faster rendering, also install the native C module:

.. code-block:: bash

   # Raspberry Pi Pico
   mpremote cp natmod/sam_render_rp2.mpy :lib/sam_render.mpy

   # ESP32
   mpremote cp natmod/sam_render_esp32.mpy :lib/sam_render.mpy

.. important::

   The file must be named ``sam_render.mpy`` on the device. Place it in
   ``/`` or ``/lib/``.

Basic Usage
-----------

.. code-block:: python

   from sam import SAM

   # Create SAM on GPIO 0
   sam = SAM(pin=0)

   # Speak English text
   sam.say("Hello World")

   # Long text is automatically chunked to avoid memory errors
   sam.say("I can speak long passages of text without running out of memory.")

   # Check what's running under the hood
   sam.info()

   # Clean up when done
   sam.stop()

Voice Presets
-------------

SAM includes built-in voice presets:

.. code-block:: python

   from sam import SAM

   # Use a preset at creation
   sam = SAM(pin=0, voice='robot')
   sam.say("I am a robot")

   # Switch voices on the fly
   sam.set_voice('elf')
   sam.say("hello tiny world")

   # See all available presets
   sam.list_voices()

Available presets: ``sam``, ``robot``, ``elf``, ``old_man``, ``whisper``,
``alien``, ``giant``, ``child``, ``stuffy``.

Add custom presets at runtime:

.. code-block:: python

   from sam import VOICES
   VOICES['squeaky'] = (60, 120, 100, 180)  # (speed, pitch, mouth, throat)
   sam.set_voice('squeaky')

Voice Parameters
----------------

Fine-tune the voice manually:

.. code-block:: python

   sam.set_speed(72)     # Speech rate (1-255, default 72). Higher = slower.
   sam.set_pitch(64)     # Voice pitch (1-255, default 64). Higher = squeakier.
   sam.set_mouth(128)    # Mouth shape (1-255, default 128).
   sam.set_throat(128)   # Throat shape (1-255, default 128).

Speaking Phonemes Directly
--------------------------

Bypass the English-to-phoneme reciter for precise control:

.. code-block:: python

   sam.say_phonetic("/HEH4LOW WERLD")

Use ``text_to_phonemes()`` to see what the reciter generates:

.. code-block:: python

   phonemes = sam.text_to_phonemes("Hello World")
   print(phonemes)  # /HEHLOW WERLD

Fixing Pronunciation
--------------------

If a word sounds wrong, add it to the exception dictionary in
``sam/reciter.py``:

.. code-block:: python

   # In sam/reciter.py
   EXCEPTIONS = {
       'ROBOT': 'ROW4BAHT',
       'YOURWORD': 'phonemes here',
       ...
   }

The exception dictionary is checked before the rule-based reciter.

Singing
-------

SAM can sing melodies with precise beat timing:

.. code-block:: python

   from sam import SAM

   sam = SAM(pin=0)

   # Note-to-pitch mapping (lower value = higher note)
   N = {
       'C3':96, 'D3':86, 'E3':76, 'F3':72, 'G3':64, 'A3':57, 'B3':51,
       'C4':48, 'D4':43, 'E4':38, 'F4':36, 'G4':32, 'A4':28,
       'R':0,
   }

   # Each tuple: (pitch, phonemes, beats)
   melody = [
       (N['G3'], 'DEY4',  1.5),
       (N['E3'], 'ZIY',   1.5),
       (N['C3'], 'DEY4',  1.5),
       (N['C3'], 'ZIY',   1.5),
   ]

   sam.sing(melody, bpm=80)

See the ``example.py`` file for a full "Daisy Bell" rendition.

Saving to WAV
-------------

Generate WAV files for testing on desktop Python or saving to SD card:

.. code-block:: python

   sam.save_wav("Hello World", "hello.wav")

Desktop Testing
---------------

The library also works on standard desktop Python for testing:

.. code-block:: bash

   python test_desktop.py

This generates WAV files you can play to verify speech quality without hardware.
