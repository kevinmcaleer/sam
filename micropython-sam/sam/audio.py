"""
SAM Audio Output: PWM-based audio driver for MicroPython.

Streams 8-bit unsigned PCM samples to a GPIO pin via PWM by rapidly
updating the duty cycle at the sample rate (~22,050 Hz).

Hardware setup:
    GPIO pin --> 1K resistor --> speaker --> GND
    Optionally add 100nF capacitor across the speaker for filtering.

Supports two output strategies:
1. Timer-interrupt driven (preferred for steady playback)
2. Tight-loop driven (simpler, blocks until done)

Platform support:
- Raspberry Pi Pico (RP2040): PWM freq up to 125 MHz / 256 = ~488 kHz
- ESP32: PWM freq up to ~312 kHz via LEDC

The PWM frequency is set high (62.5 kHz on Pico, 40 kHz on ESP32) so
the carrier is well above audible range. The duty cycle (0-255 mapped
to 0-65535) encodes the audio sample value.
"""

# Default sample rate
SAMPLE_RATE = 22050

# Platform-specific PWM frequency targets
PWM_FREQ_PICO = 62500    # 125 MHz / 2000 = 62.5 kHz, gives ~10-bit resolution
PWM_FREQ_ESP32 = 40000   # Conservative for ESP32 LEDC


class PWMAudio:
    """
    PWM audio output driver for MicroPython.

    Usage:
        audio = PWMAudio(pin=0)
        audio.play(sample_buffer)  # bytearray of 8-bit unsigned PCM
        audio.stop()
    """

    def __init__(self, pin=0, sample_rate=SAMPLE_RATE):
        """
        Initialize PWM audio output.

        Args:
            pin: GPIO pin number for PWM output
            sample_rate: Audio sample rate in Hz (default 22050)
        """
        self.pin_num = pin
        self.sample_rate = sample_rate
        self._pwm = None
        self._timer = None
        self._buffer = None
        self._buf_pos = 0
        self._playing = False
        self._duty_max = 65535  # 16-bit PWM duty cycle
        self._use_timer = True

        # Detect platform and configure
        self._platform = self._detect_platform()

    def _detect_platform(self):
        """Detect the MicroPython platform."""
        try:
            import sys
            plat = sys.platform
            if 'rp2' in plat:
                return 'rp2'
            elif 'esp32' in plat:
                return 'esp32'
            elif 'esp8266' in plat:
                return 'esp8266'
            else:
                return plat
        except:
            return 'unknown'

    def _init_pwm(self):
        """Initialize the PWM peripheral."""
        from machine import Pin, PWM

        pin = Pin(self.pin_num, Pin.OUT)
        self._pwm = PWM(pin)

        # Set PWM frequency based on platform
        if self._platform == 'rp2':
            self._pwm.freq(PWM_FREQ_PICO)
        elif self._platform in ('esp32', 'esp8266'):
            self._pwm.freq(PWM_FREQ_ESP32)
            # ESP32 LEDC has 13-bit resolution at 40 kHz
            self._duty_max = 8191  # 13-bit
        else:
            self._pwm.freq(PWM_FREQ_PICO)

        # Start at midpoint (silence = 128 in unsigned 8-bit)
        self._set_duty(128)

    def _set_duty(self, sample_value):
        """
        Set PWM duty cycle from an 8-bit sample value (0-255).
        Maps 0-255 to the platform's duty cycle range.
        """
        if self._pwm is None:
            return
        # Scale 8-bit sample to duty cycle range
        duty = (sample_value * self._duty_max) >> 8
        try:
            self._pwm.duty_u16(duty << (16 - 16))  # RP2040 uses 16-bit
        except AttributeError:
            # ESP32 uses duty() with 10-bit or 13-bit range
            try:
                self._pwm.duty(duty >> (13 - 10) if self._duty_max > 1023 else duty)
            except:
                self._pwm.duty_u16(duty)

    def play(self, buffer):
        """
        Play an audio buffer through PWM.

        Args:
            buffer: bytearray or memoryview of 8-bit unsigned PCM samples
        """
        self._init_pwm()
        self._buffer = buffer
        self._buf_pos = 0
        self._playing = True

        if self._use_timer:
            self._play_timer()
        else:
            self._play_loop()

    def _play_timer(self):
        """Play using a hardware timer interrupt for sample timing."""
        try:
            from machine import Timer
            import micropython

            # Pre-compute duty values for faster ISR
            buf = self._buffer
            buf_len = len(buf)

            # Use a timer interrupt at the sample rate
            self._timer = Timer(-1)

            # The ISR must be as fast as possible
            @micropython.native
            def _timer_isr(t):
                pos = self._buf_pos
                if pos < buf_len:
                    self._set_duty(buf[pos])
                    self._buf_pos = pos + 1
                else:
                    t.deinit()
                    self._playing = False
                    self._set_duty(128)  # Return to silence

            self._timer.init(freq=self.sample_rate, mode=Timer.PERIODIC,
                           callback=_timer_isr)

            # Wait for playback to complete
            import time
            while self._playing:
                time.sleep_ms(10)

        except Exception as e:
            # Fall back to loop-based playback
            print("Timer playback failed, using loop:", e)
            self._play_loop()

    def _play_loop(self):
        """Play using a tight loop with time.sleep_us for timing."""
        try:
            import time
            period_us = 1000000 // self.sample_rate  # ~45 us for 22050 Hz
            buf = self._buffer
            buf_len = len(buf)
            set_duty = self._set_duty

            # Use ticks for more accurate timing
            ticks_us = time.ticks_us
            ticks_diff = time.ticks_diff
            sleep_us = time.sleep_us

            next_sample = ticks_us()

            for i in range(buf_len):
                set_duty(buf[i])

                # Wait until it's time for the next sample
                next_sample += period_us
                wait = ticks_diff(next_sample, ticks_us())
                if wait > 0:
                    sleep_us(wait)

            # Return to silence
            set_duty(128)
            self._playing = False

        except ImportError:
            # Absolute fallback - just blast samples as fast as possible
            # (will be too fast but at least produces output)
            buf = self._buffer
            for i in range(len(buf)):
                self._set_duty(buf[i])
            self._set_duty(128)
            self._playing = False

    def play_blocking(self, buffer):
        """
        Play audio buffer and block until complete.
        Uses the tight-loop method for simplest possible playback.
        """
        self._init_pwm()
        self._use_timer = False
        self._buffer = buffer
        self._play_loop()

    def stop(self):
        """Stop playback and release PWM."""
        self._playing = False
        if self._timer:
            try:
                self._timer.deinit()
            except:
                pass
            self._timer = None
        if self._pwm:
            self._set_duty(128)  # Silence
            try:
                self._pwm.deinit()
            except:
                pass
            self._pwm = None

    @property
    def is_playing(self):
        return self._playing


class WavWriter:
    """
    Write audio samples to a WAV file for testing/debugging.
    Works on any Python (not just MicroPython).
    """

    def __init__(self, filename, sample_rate=SAMPLE_RATE):
        self.filename = filename
        self.sample_rate = sample_rate

    def write(self, buffer):
        """Write 8-bit unsigned PCM buffer as a WAV file."""
        import struct

        num_samples = len(buffer)
        data_size = num_samples
        file_size = 36 + data_size

        with open(self.filename, 'wb') as f:
            # RIFF header
            f.write(b'RIFF')
            f.write(struct.pack('<I', file_size))
            f.write(b'WAVE')

            # fmt chunk
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))       # chunk size
            f.write(struct.pack('<H', 1))        # PCM format
            f.write(struct.pack('<H', 1))        # mono
            f.write(struct.pack('<I', self.sample_rate))
            f.write(struct.pack('<I', self.sample_rate))  # byte rate
            f.write(struct.pack('<H', 1))        # block align
            f.write(struct.pack('<H', 8))        # bits per sample

            # data chunk
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            f.write(bytes(buffer))

        return self.filename
