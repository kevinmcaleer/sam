"""
SAM Speech Synthesizer - MicroPython Example

Hardware setup (Raspberry Pi Pico):
    GP0 --[1K resistor]--> Speaker(+) --> GND
    Optional: 100nF capacitor across speaker terminals

For ESP32, change pin number to a valid GPIO (e.g., 25 or 26 for DAC-capable pins,
though this uses PWM not DAC).
"""

from sam import SAM

# ============================================================================
# Basic usage
# ============================================================================

# Create SAM instance on GPIO 0
sam = SAM(pin=0)

# Speak English text
sam.say("hello world")

# Speak with phonemes directly (bypass reciter)
sam.say_phonetic("/HEH4LOW WERLD")

# ============================================================================
# Voice customization
# ============================================================================

# Adjust speech parameters
sam.set_speed(72)     # Default speed (lower = slower)
sam.set_pitch(64)     # Default pitch (higher = squeakier)
sam.set_mouth(128)    # Default mouth
sam.set_throat(128)   # Default throat

# Robot voice: low pitch, narrow mouth
sam.set_pitch(40)
sam.set_mouth(150)
sam.set_throat(90)
sam.say("i am a robot")

# High-pitched voice
sam.set_pitch(96)
sam.set_mouth(128)
sam.set_throat(128)
sam.say("hello there")

# Reset to defaults
sam.set_pitch(64)
sam.set_speed(72)
sam.set_mouth(128)
sam.set_throat(128)

# ============================================================================
# Phoneme debugging
# ============================================================================

# See what phonemes the reciter generates
phonemes = sam.text_to_phonemes("hello world")
print("Phonemes:", phonemes)

# ============================================================================
# Generate audio without playing (useful for WAV export or custom output)
# ============================================================================

buffer = sam.generate("testing one two three")
print("Generated", len(buffer), "audio samples")

# Save to WAV file (works on Pico with SD card, or desktop Python)
# sam.save_wav("hello world", "hello.wav")

# ============================================================================
# ESP32 example with different pin
# ============================================================================
# sam_esp = SAM(pin=25)
# sam_esp.say("hello from esp thirty two")

# ============================================================================
# SAM Phoneme Reference (common phonemes):
#
#   Vowels:          Consonants:
#   IY = ee (beat)   P  = p        S  = s
#   IH = i  (bit)    B  = b        Z  = z
#   EH = e  (bet)    T  = t        SH = sh
#   AE = a  (bat)    D  = d        ZH = zh (measure)
#   AA = a  (father) K  = k        F  = f
#   AH = u  (but)    G  = g        V  = v
#   AO = aw (bought) M  = m        TH = th (thin)
#   UH = oo (book)   N  = n        DH = dh (this)
#   AX = a  (about)  NX = ng       /H = h
#   IX = i  (roses)  L  = l        CH = ch
#   ER = er (bird)   R  = r        J  = j (judge)
#   UX = oo (boot)   W  = w        WH = wh
#   OH = o  (go)     Y  = y        Q  = glottal stop
#
#   Diphthongs:      Stress markers:
#   EY = ay (day)    1-8 after vowel (4 = primary stress)
#   AY = eye
#   OY = oy (boy)
#   AW = ow (how)
#   OW = oh (go)
#   UW = oo (too)
# ============================================================================

# Clean up
sam.stop()
