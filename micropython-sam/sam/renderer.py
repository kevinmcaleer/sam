"""
SAM Renderer: Formant synthesis engine.
Ported from render.c in the original SAM source.

Converts processed phoneme sequences into 8-bit PCM audio samples
using a three-formant additive synthesis model:
  - F1: sine wave (first formant)
  - F2: sine wave (second formant)
  - F3: rectangular wave (third formant / nasal/fricative energy)

Glottal excitation is modeled by resetting oscillator phases at
pitch-period boundaries. Each frame corresponds to one glottal cycle
(pitch period), generating pitches[frame] samples.

Performance-critical inner loops use @micropython.viper decorators
where available, falling back to plain Python.
"""

from . import tables

# Try to use viper/native decorators for performance
try:
    import micropython
    _HAS_VIPER = True
except ImportError:
    _HAS_VIPER = False

# Sample rate (approximate - SAM's native rate)
SAMPLE_RATE = 22050


def create_frames(phoneme_index, phoneme_length, stress, pitch, mouth, throat):
    """
    Expand phonemes into per-frame synthesis parameters.
    Each phoneme occupies phoneme_length[i] frames.
    Each frame represents one glottal pitch period.

    Returns: (frequency1[], frequency2[], frequency3[],
              amplitude1[], amplitude2[], amplitude3[],
              pitches[], sampled_consonant_flag[], num_frames)
    """
    num_frames = 0
    for i in range(len(phoneme_index)):
        if phoneme_index[i] == 255:
            break
        num_frames += phoneme_length[i]

    # Pre-allocate frame arrays
    freq1 = bytearray(num_frames + 1)
    freq2 = bytearray(num_frames + 1)
    freq3 = bytearray(num_frames + 1)
    amp1 = bytearray(num_frames + 1)
    amp2 = bytearray(num_frames + 1)
    amp3 = bytearray(num_frames + 1)
    pitches = bytearray(num_frames + 1)
    samp_flags = bytearray(num_frames + 1)

    # Apply mouth/throat adjustments to formant tables
    adj_f1 = list(tables.FREQ1)
    adj_f2 = list(tables.FREQ2)

    if mouth != 128 or throat != 128:
        _set_mouth_throat(adj_f1, adj_f2, mouth, throat)

    # Fill frames
    frame = 0
    for i in range(len(phoneme_index)):
        idx = phoneme_index[i]
        if idx == 255:
            break
        length = phoneme_length[i]
        if idx >= len(tables.FREQ1):
            frame += length
            continue

        f1 = adj_f1[idx]
        f2 = adj_f2[idx]
        f3 = tables.FREQ3[idx] if idx < len(tables.FREQ3) else 0
        a1 = tables.AMPL1[idx] if idx < len(tables.AMPL1) else 0
        a2 = tables.AMPL2[idx] if idx < len(tables.AMPL2) else 0
        a3 = tables.AMPL3[idx] if idx < len(tables.AMPL3) else 0
        sf = tables.SAMPLED_CONSONANT_FLAGS[idx] if idx < len(tables.SAMPLED_CONSONANT_FLAGS) else 0

        # Compute pitch for this phoneme
        p = pitch
        if i < len(stress) and stress[i] > 0:
            p = min(255, pitch + (stress[i] * 2))

        for j in range(length):
            if frame + j < num_frames:
                freq1[frame + j] = f1
                freq2[frame + j] = f2
                freq3[frame + j] = f3
                amp1[frame + j] = a1
                amp2[frame + j] = a2
                amp3[frame + j] = a3
                pitches[frame + j] = p
                samp_flags[frame + j] = sf

        frame += length

    # Create transitions between phonemes
    _create_transitions(phoneme_index, phoneme_length, freq1, freq2, freq3,
                        amp1, amp2, amp3, pitches, adj_f1, adj_f2)

    # Pitch contour: subtract half of F1 from pitch for natural prosody
    for i in range(num_frames):
        p = pitches[i]
        f = freq1[i] >> 1
        pitches[i] = max(1, p - f) if p > f else max(1, p)

    return (freq1, freq2, freq3, amp1, amp2, amp3, pitches, samp_flags,
            num_frames)


def _set_mouth_throat(f1, f2, mouth, throat):
    """Apply mouth and throat parameters to formant frequencies."""
    for i in range(5, min(55, len(f1))):
        if i - 5 < len(tables.THROAT_FORMANT5_59):
            original = tables.THROAT_FORMANT5_59[i - 5]
            if original != 0xFF:
                f2[i] = (original * throat) >> 7
    for i in range(5, min(55, len(f1))):
        if i - 5 < len(tables.MOUTH_FORMANT5_59):
            original = tables.MOUTH_FORMANT5_59[i - 5]
            if original != 0:
                f1[i] = (original * mouth) >> 7
    for i in range(6):
        idx = 48 + i
        if idx < len(f1) and i < len(tables.MOUTH_FORMANT48_53):
            f1[idx] = (tables.MOUTH_FORMANT48_53[i] * mouth) >> 7
        if idx < len(f2) and i < len(tables.THROAT_FORMANT48_53):
            f2[idx] = (tables.THROAT_FORMANT48_53[i] * throat) >> 7


def _create_transitions(phoneme_index, phoneme_length, f1, f2, f3,
                         a1, a2, a3, pitches, adj_f1, adj_f2):
    """
    Smooth transitions between phonemes using blend rank system.
    """
    frame = 0
    for i in range(len(phoneme_index) - 1):
        idx = phoneme_index[i]
        if idx == 255:
            break
        nxt = phoneme_index[i + 1]
        if nxt == 255:
            break

        length = phoneme_length[i]
        nxt_length = phoneme_length[i + 1]

        if idx >= len(tables.BLEND_RANK) or nxt >= len(tables.BLEND_RANK):
            frame += length
            continue

        rank_cur = tables.BLEND_RANK[idx]
        rank_nxt = tables.BLEND_RANK[nxt]

        if rank_cur >= rank_nxt:
            out_len = tables.OUT_BLEND_LENGTH[idx] if idx < len(tables.OUT_BLEND_LENGTH) else 1
            in_len = tables.IN_BLEND_LENGTH[nxt] if nxt < len(tables.IN_BLEND_LENGTH) else 1
        else:
            out_len = tables.OUT_BLEND_LENGTH[nxt] if nxt < len(tables.OUT_BLEND_LENGTH) else 1
            in_len = tables.IN_BLEND_LENGTH[idx] if idx < len(tables.IN_BLEND_LENGTH) else 1

        out_len = min(out_len, length)
        in_len = min(in_len, nxt_length)
        blend_len = out_len + in_len

        if blend_len == 0:
            frame += length
            continue

        trans_start = frame + length - out_len

        if nxt < len(tables.FREQ1):
            nxt_f1 = adj_f1[nxt]
            nxt_f2 = adj_f2[nxt]
            nxt_f3 = tables.FREQ3[nxt] if nxt < len(tables.FREQ3) else 0
            nxt_a1 = tables.AMPL1[nxt] if nxt < len(tables.AMPL1) else 0
            nxt_a2 = tables.AMPL2[nxt] if nxt < len(tables.AMPL2) else 0
            nxt_a3 = tables.AMPL3[nxt] if nxt < len(tables.AMPL3) else 0
        else:
            frame += length
            continue

        for j in range(blend_len):
            fpos = trans_start + j
            if fpos < 0 or fpos >= len(f1):
                continue
            t = (j * 256) // blend_len

            f1[fpos] = (f1[fpos] * (256 - t) + nxt_f1 * t) >> 8
            f2[fpos] = (f2[fpos] * (256 - t) + nxt_f2 * t) >> 8
            f3[fpos] = (f3[fpos] * (256 - t) + nxt_f3 * t) >> 8
            a1[fpos] = (a1[fpos] * (256 - t) + nxt_a1 * t) >> 8
            a2[fpos] = (a2[fpos] * (256 - t) + nxt_a2 * t) >> 8
            a3[fpos] = (a3[fpos] * (256 - t) + nxt_a3 * t) >> 8

        frame += length


# ============================================================================
# Audio sample generation
# ============================================================================

def render(phoneme_index, phoneme_length, stress, pitch=64,
           mouth=128, throat=128):
    """
    Render phoneme data to an 8-bit unsigned PCM audio buffer.

    In SAM's model, each frame represents one glottal cycle.
    The number of audio samples per frame equals pitches[frame].
    Total samples = sum of pitches[frame] for all frames.

    Returns:
        bytearray of 8-bit unsigned PCM samples at ~22,050 Hz
    """
    result = create_frames(phoneme_index, phoneme_length, stress,
                           pitch, mouth, throat)
    freq1, freq2, freq3, amp1, amp2, amp3, pitches, samp_flags, num_frames = result

    # Calculate total output samples
    total_samples = 0
    for i in range(num_frames):
        total_samples += pitches[i] if pitches[i] > 0 else 1

    buffer = bytearray(total_samples + 256)  # small padding
    buf_pos = _render_frames_python(
        buffer, freq1, freq2, freq3, amp1, amp2, amp3,
        pitches, samp_flags, num_frames
    )

    return memoryview(buffer)[:buf_pos]


def _render_frames_python(buffer, freq1, freq2, freq3, amp1, amp2, amp3,
                           pitches, samp_flags, num_frames):
    """
    Render frames to audio samples.

    Each frame generates pitches[frame] samples (one glottal period).
    Oscillator phases run continuously; phase1 resets at each frame
    boundary (glottal pulse).
    """
    sinus = tables.SINUS
    rect = tables.RECTANGLE
    sample_tab = tables.SAMPLE_TABLE

    buf_pos = 0
    buf_len = len(buffer)
    phase1 = 0
    phase2 = 0
    phase3 = 0

    for frame in range(num_frames):
        f1 = freq1[frame]
        f2 = freq2[frame]
        f3 = freq3[frame]
        a1 = amp1[frame] & 0x0F
        a2 = amp2[frame] & 0x0F
        a3 = amp3[frame] & 0x0F
        p = pitches[frame]
        sf = samp_flags[frame]

        if p == 0:
            p = 1

        # Reset phase1 at start of each glottal cycle
        phase1 = 0

        # Generate p samples for this frame (one pitch period)
        for sample_num in range(p):
            if buf_pos >= buf_len:
                return buf_pos

            if sf != 0:
                # Sampled consonant (fricatives, plosive bursts)
                s = _get_sampled_consonant(sf, sample_num, sample_tab)
                buffer[buf_pos] = (s + 128) & 0xFF
            else:
                # Three-formant additive synthesis
                # F1: sine wave
                idx1 = phase1 & 0xFF
                sin1 = sinus[idx1]
                if sin1 > 127:
                    sin1 -= 256

                # F2: sine wave
                idx2 = phase2 & 0xFF
                sin2 = sinus[idx2]
                if sin2 > 127:
                    sin2 -= 256

                # F3: rectangular wave
                idx3 = phase3 & 0xFF
                rec3 = rect[idx3]
                if rec3 > 127:
                    rec3 -= 256

                # Mix formants with amplitude weighting
                output = (sin1 * a1 + sin2 * a2 + rec3 * a3) // 32 + 128

                # Clip to 8-bit unsigned
                if output > 255:
                    output = 255
                elif output < 0:
                    output = 0
                buffer[buf_pos] = output

            buf_pos += 1

            # Advance oscillator phases
            # Phase increment is proportional to formant frequency
            phase1 = (phase1 + ((f1 * 256) // p)) & 0xFFFF
            phase2 = (phase2 + ((f2 * 256) // p)) & 0xFFFF
            phase3 = (phase3 + ((f3 * 256) // p)) & 0xFFFF

    return buf_pos


def _get_sampled_consonant(flag, counter, sample_table):
    """
    Generate a sample for a sampled consonant (fricative or plosive burst).
    Uses bit-packed data from the sample table.
    """
    sample_idx = (flag & 0xF0) >> 4
    offset = sample_idx * 0x20

    byte_idx = (counter >> 3) & 0x1F
    bit_idx = counter & 0x07

    if offset + byte_idx < len(sample_table):
        byte_val = sample_table[offset + byte_idx]
    else:
        byte_val = 0

    if (byte_val >> (7 - bit_idx)) & 1:
        if flag & 0x04:
            return 24
        else:
            return 5
    else:
        if flag & 0x04:
            return 6
        else:
            idx = (flag >> 4) & 0x07
            if idx < len(tables.TAB48426):
                return tables.TAB48426[idx]
            return 0x18


# ============================================================================
# Viper-optimized version for MicroPython on RP2040/ESP32
# ============================================================================

if _HAS_VIPER:
    # Override the render function to use viper when available
    @micropython.native
    def _render_frames_native(buffer, freq1, freq2, freq3, amp1, amp2, amp3,
                               pitches, samp_flags, num_frames):
        """
        Native-decorated version for moderate speedup on MicroPython.
        Same algorithm as Python version but with native code emission.
        """
        sinus = tables.SINUS
        rect = tables.RECTANGLE
        sample_tab = tables.SAMPLE_TABLE

        buf_pos = 0
        buf_len = len(buffer)
        phase1 = 0
        phase2 = 0
        phase3 = 0

        for frame in range(num_frames):
            f1 = freq1[frame]
            f2 = freq2[frame]
            f3 = freq3[frame]
            a1 = amp1[frame] & 0x0F
            a2 = amp2[frame] & 0x0F
            a3 = amp3[frame] & 0x0F
            p = pitches[frame]
            sf = samp_flags[frame]

            if p == 0:
                p = 1

            phase1 = 0

            for sample_num in range(p):
                if buf_pos >= buf_len:
                    return buf_pos

                if sf != 0:
                    s_idx = (sf & 0xF0) >> 4
                    s_off = s_idx * 0x20
                    b_idx = (sample_num >> 3) & 0x1F
                    b_bit = sample_num & 0x07
                    if s_off + b_idx < len(sample_tab):
                        bv = sample_tab[s_off + b_idx]
                    else:
                        bv = 0
                    if (bv >> (7 - b_bit)) & 1:
                        buffer[buf_pos] = 128 + (24 if (sf & 0x04) else 5)
                    else:
                        buffer[buf_pos] = 128 + (6 if (sf & 0x04) else 0x18)
                else:
                    idx1 = phase1 & 0xFF
                    sin1 = sinus[idx1]
                    if sin1 > 127:
                        sin1 -= 256
                    idx2 = phase2 & 0xFF
                    sin2 = sinus[idx2]
                    if sin2 > 127:
                        sin2 -= 256
                    idx3 = phase3 & 0xFF
                    rec3 = rect[idx3]
                    if rec3 > 127:
                        rec3 -= 256

                    output = (sin1 * a1 + sin2 * a2 + rec3 * a3) // 32 + 128
                    if output > 255:
                        output = 255
                    elif output < 0:
                        output = 0
                    buffer[buf_pos] = output

                buf_pos += 1
                phase1 = (phase1 + ((f1 * 256) // p)) & 0xFFFF
                phase2 = (phase2 + ((f2 * 256) // p)) & 0xFFFF
                phase3 = (phase3 + ((f3 * 256) // p)) & 0xFFFF

        return buf_pos

    # Replace the Python render with the native version on MicroPython
    _render_frames_python = _render_frames_native
