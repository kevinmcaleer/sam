"""
SAM Audio Output: PIO+DMA audio driver for RP2040, with PWM fallback.
"""

SAMPLE_RATE = 22050

PWM_FREQ_PICO = 62500
PWM_FREQ_ESP32 = 40000

# PIO PWM audio program for RP2040.
# Reads packed 8-bit samples from TX FIFO via autopull (4 samples per word).
# Each sample produces one PWM cycle with 8-bit duty resolution.
# Pin goes LOW at start, HIGH when counter matches duty value.
# Total: 770 PIO clocks per sample (2 setup + 256*3 loop).
try:
    import rp2

    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW,
                 out_shiftdir=rp2.PIO.SHIFT_RIGHT,
                 autopull=True, pull_thresh=32)
    def _audio_pwm_pio():
        wrap_target()
        out(x, 8)        .side(0)    # x = next 8-bit sample; pin LOW
        mov(y, isr)      .side(0)    # y = 255 (PWM period, preloaded)
        label("loop")
        jmp(x_not_y, "skip")         # if duty != counter, skip
        jmp("cont")      .side(1)    # match: pin goes HIGH
        label("skip")
        nop()                         # no match: pin unchanged
        label("cont")
        jmp(y_dec, "loop")            # y--, loop while y > 0
        wrap()

    _HAS_PIO = True
except (ImportError, Exception):
    _HAS_PIO = False


class PIOAudio:
    """Audio output using PIO-generated PWM with DMA sample feeding.

    Provides jitter-free sample output at the exact sample rate.
    Falls back to PIO with manual FIFO feeding if DMA is unavailable.
    """

    def __init__(self, pin=0, sample_rate=SAMPLE_RATE, sm_id=0):
        self.pin_num = pin
        self.sample_rate = sample_rate
        self.sm_id = sm_id
        self._sm = None
        self._dma = None
        self._playing = False

    def play(self, buffer):
        from machine import Pin

        # Pad buffer to multiple of 4 bytes for 32-bit FIFO words
        pad = (4 - len(buffer) % 4) % 4
        if pad:
            buffer = buffer + bytearray([128] * pad)

        pin = Pin(self.pin_num, Pin.OUT)

        # 770 PIO cycles per sample × sample_rate = PIO clock frequency
        pio_freq = self.sample_rate * 770

        sm = rp2.StateMachine(self.sm_id, _audio_pwm_pio,
                              freq=pio_freq, sideset_base=pin)

        # Preload ISR with 255 (PWM period = 256 steps)
        sm.put(255)
        sm.exec("pull()")
        sm.exec("mov(isr, osr)")

        self._sm = sm
        self._playing = True

        try:
            self._play_dma(buffer, sm)
        except Exception:
            self._play_manual(buffer, sm)

    def _play_dma(self, buffer, sm):
        import time, uctypes

        pio_num = self.sm_id // 4
        sm_num = self.sm_id % 4
        pio_base = 0x50200000 + pio_num * 0x100000
        txf_addr = pio_base + 0x10 + sm_num * 4
        dreq = pio_num * 8 + sm_num

        dma = rp2.DMA()
        self._dma = dma

        ctrl = dma.pack_ctrl(
            size=2,            # 32-bit word transfers
            inc_read=True,     # advance through buffer
            inc_write=False,   # always write to PIO FIFO
            treq_sel=dreq,     # pace with PIO TX FIFO requests
        )

        sm.active(1)

        dma.config(
            read=uctypes.addressof(buffer),
            write=txf_addr,
            count=len(buffer) // 4,
            ctrl=ctrl,
            trigger=True,
        )

        while dma.active():
            time.sleep_ms(10)

        # Allow PIO to drain remaining FIFO entries
        time.sleep_ms(5)
        self.stop()

    def _play_manual(self, buffer, sm):
        """Fallback: feed PIO TX FIFO from Python loop."""
        import time

        sm.active(1)

        for i in range(0, len(buffer) - 3, 4):
            word = (buffer[i] | (buffer[i+1] << 8) |
                    (buffer[i+2] << 16) | (buffer[i+3] << 24))
            sm.put(word)  # blocks when FIFO full — natural pacing

        time.sleep_ms(5)
        self.stop()

    def stop(self):
        self._playing = False
        if self._dma:
            try:
                self._dma.close()
            except Exception:
                pass
            self._dma = None
        if self._sm:
            try:
                self._sm.active(0)
            except Exception:
                pass
            self._sm = None

    @property
    def is_playing(self):
        return self._playing


class PWMAudio:
    """Fallback audio using hardware PWM + timer interrupt."""

    def __init__(self, pin=0, sample_rate=SAMPLE_RATE):
        self.pin_num = pin
        self.sample_rate = sample_rate
        self._pwm = None
        self._timer = None
        self._playing = False

    def _init_pwm(self):
        from machine import Pin, PWM
        pin = Pin(self.pin_num, Pin.OUT)
        self._pwm = PWM(pin)
        try:
            import sys
            if 'esp32' in sys.platform:
                self._pwm.freq(PWM_FREQ_ESP32)
            else:
                self._pwm.freq(PWM_FREQ_PICO)
        except:
            self._pwm.freq(PWM_FREQ_PICO)
        self._pwm.duty_u16(32768)

    def play(self, buffer):
        self._init_pwm()
        self._playing = True

        try:
            self._play_timer(buffer)
        except Exception as e:
            print("Timer failed, using loop:", e)
            self._play_loop(buffer)

    def _play_timer(self, buffer):
        from machine import Timer
        import micropython, time

        buf = buffer
        buf_len = len(buf)
        pwm = self._pwm
        self._buf_pos = 0

        timer = Timer(-1)
        self._timer = timer

        @micropython.native
        def _isr(t):
            pos = self._buf_pos
            if pos < buf_len:
                pwm.duty_u16(buf[pos] * 257)
                self._buf_pos = pos + 1
            else:
                t.deinit()
                pwm.duty_u16(32768)
                self._playing = False

        timer.init(freq=self.sample_rate, mode=Timer.PERIODIC, callback=_isr)

        while self._playing:
            time.sleep_ms(10)

    def _play_loop(self, buffer):
        import time
        period_us = 1000000 // self.sample_rate
        pwm = self._pwm
        buf = buffer
        buf_len = len(buf)
        ticks_us = time.ticks_us
        ticks_diff = time.ticks_diff
        sleep_us = time.sleep_us

        next_t = ticks_us()
        for i in range(buf_len):
            pwm.duty_u16(buf[i] * 257)
            next_t += period_us
            wait = ticks_diff(next_t, ticks_us())
            if wait > 0:
                sleep_us(wait)

        pwm.duty_u16(32768)
        self._playing = False

    def stop(self):
        self._playing = False
        if self._timer:
            try:
                self._timer.deinit()
            except:
                pass
            self._timer = None
        if self._pwm:
            self._pwm.duty_u16(32768)
            try:
                self._pwm.deinit()
            except:
                pass
            self._pwm = None

    @property
    def is_playing(self):
        return self._playing


class WavWriter:
    def __init__(self, filename, sample_rate=SAMPLE_RATE):
        self.filename = filename
        self.sample_rate = sample_rate

    def write(self, buffer):
        import struct
        num_samples = len(buffer)
        with open(self.filename, 'wb') as f:
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + num_samples))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<I', self.sample_rate))
            f.write(struct.pack('<I', self.sample_rate))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 8))
            f.write(b'data')
            f.write(struct.pack('<I', num_samples))
            f.write(bytes(buffer))
        return self.filename
