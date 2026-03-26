"""
SAM Renderer - optimized for MicroPython.
Uses mult_table mixing, timetable output, all table lookups.
"""

from . import tables

try:
    import micropython
except ImportError:
    # Desktop Python - provide no-op decorator
    class micropython:
        @staticmethod
        def native(f):
            return f

# Render at 22050 Hz via timetable — output at full rate for best quality.
SAMPLE_RATE = 22050


def create_frames(phoneme_index, phoneme_length, stress, pitch, mouth, throat):
    num_frames = 0
    for i in range(len(phoneme_index)):
        if phoneme_index[i] == 255:
            break
        num_frames += phoneme_length[i]

    freq1 = bytearray(num_frames + 1)
    freq2 = bytearray(num_frames + 1)
    freq3 = bytearray(num_frames + 1)
    amp1 = bytearray(num_frames + 1)
    amp2 = bytearray(num_frames + 1)
    amp3 = bytearray(num_frames + 1)
    pitches = bytearray(num_frames + 1)
    samp_flags = bytearray(num_frames + 1)

    adj_f1 = list(tables.FREQ1)
    adj_f2 = list(tables.FREQ2)
    if mouth != 128 or throat != 128:
        for i in range(5, min(55, len(adj_f1))):
            if i - 5 < len(tables.THROAT_FORMANT5_59):
                o = tables.THROAT_FORMANT5_59[i - 5]
                if o != 0xFF:
                    adj_f2[i] = (o * throat) >> 7
        for i in range(5, min(55, len(adj_f1))):
            if i - 5 < len(tables.MOUTH_FORMANT5_59):
                o = tables.MOUTH_FORMANT5_59[i - 5]
                if o != 0:
                    adj_f1[i] = (o * mouth) >> 7
        for i in range(6):
            idx = 48 + i
            if idx < len(adj_f1) and i < len(tables.MOUTH_FORMANT48_53):
                adj_f1[idx] = (tables.MOUTH_FORMANT48_53[i] * mouth) >> 7
            if idx < len(adj_f2) and i < len(tables.THROAT_FORMANT48_53):
                adj_f2[idx] = (tables.THROAT_FORMANT48_53[i] * throat) >> 7

    frame = 0
    for i in range(len(phoneme_index)):
        idx = phoneme_index[i]
        if idx == 255:
            break
        length = phoneme_length[i]
        if idx >= len(tables.FREQ1):
            frame += length
            continue
        f1 = adj_f1[idx]; f2 = adj_f2[idx]
        f3 = tables.FREQ3[idx] if idx < len(tables.FREQ3) else 0
        a1 = tables.AMPL1[idx] if idx < len(tables.AMPL1) else 0
        a2 = tables.AMPL2[idx] if idx < len(tables.AMPL2) else 0
        a3 = tables.AMPL3[idx] if idx < len(tables.AMPL3) else 0
        sf = tables.SAMPLED_CONSONANT_FLAGS[idx] if idx < len(tables.SAMPLED_CONSONANT_FLAGS) else 0
        s = stress[i] if i < len(stress) else 0
        sp = tables.TAB47492[s] if s < len(tables.TAB47492) else 0
        p = (pitch + sp) & 0xFF
        for j in range(length):
            if frame + j < num_frames:
                freq1[frame+j]=f1; freq2[frame+j]=f2; freq3[frame+j]=f3
                amp1[frame+j]=a1; amp2[frame+j]=a2; amp3[frame+j]=a3
                pitches[frame+j]=p; samp_flags[frame+j]=sf
        frame += length

    # Transitions
    frame = 0
    for i in range(len(phoneme_index) - 1):
        idx = phoneme_index[i]
        if idx == 255: break
        nxt = phoneme_index[i + 1]
        if nxt == 255: break
        length = phoneme_length[i]; nxt_length = phoneme_length[i + 1]
        if idx >= len(tables.BLEND_RANK) or nxt >= len(tables.BLEND_RANK):
            frame += length; continue
        if tables.BLEND_RANK[idx] >= tables.BLEND_RANK[nxt]:
            ol = tables.OUT_BLEND_LENGTH[idx] if idx < len(tables.OUT_BLEND_LENGTH) else 1
            il = tables.IN_BLEND_LENGTH[nxt] if nxt < len(tables.IN_BLEND_LENGTH) else 1
        else:
            ol = tables.OUT_BLEND_LENGTH[nxt] if nxt < len(tables.OUT_BLEND_LENGTH) else 1
            il = tables.IN_BLEND_LENGTH[idx] if idx < len(tables.IN_BLEND_LENGTH) else 1
        ol = min(ol, length); il = min(il, nxt_length)
        bl = ol + il
        if bl == 0: frame += length; continue
        ts = frame + length - ol
        if nxt >= len(tables.FREQ1): frame += length; continue
        nf1=adj_f1[nxt]; nf2=adj_f2[nxt]
        nf3=tables.FREQ3[nxt] if nxt<len(tables.FREQ3) else 0
        na1=tables.AMPL1[nxt] if nxt<len(tables.AMPL1) else 0
        na2=tables.AMPL2[nxt] if nxt<len(tables.AMPL2) else 0
        na3=tables.AMPL3[nxt] if nxt<len(tables.AMPL3) else 0
        for j in range(bl):
            fp = ts + j
            if fp < 0 or fp >= len(freq1): continue
            t = (j * 256) // bl
            u = 256 - t
            freq1[fp]=(freq1[fp]*u+nf1*t)>>8; freq2[fp]=(freq2[fp]*u+nf2*t)>>8
            freq3[fp]=(freq3[fp]*u+nf3*t)>>8
            amp1[fp]=(amp1[fp]*u+na1*t)>>8; amp2[fp]=(amp2[fp]*u+na2*t)>>8
            amp3[fp]=(amp3[fp]*u+na3*t)>>8
        frame += length

    return (freq1, freq2, freq3, amp1, amp2, amp3, pitches, samp_flags, num_frames)


# Try to use the native C module for the render loop
try:
    import sam_render as _native
    _HAS_NATIVE = True
    # Check if native module outputs at full rate (recompile needed after upgrade)
    _native_rate = getattr(_native, 'SAMPLE_RATE', 7350)
    if _native_rate < SAMPLE_RATE:
        _HAS_NATIVE = False
        _NATIVE_STATUS = 'outdated (recompile for 22050 Hz)'
    else:
        _NATIVE_STATUS = 'active'
except ImportError:
    _HAS_NATIVE = False
    _NATIVE_STATUS = 'not found'


@micropython.native
def render(phoneme_index, phoneme_length, stress, speed=72, pitch=64,
           mouth=128, throat=128):
    result = create_frames(phoneme_index, phoneme_length, stress, pitch, mouth, throat)
    fr1, fr2, fr3, am1, am2, am3, pitches, samp_flags, num_frames = result
    if num_frames == 0:
        return bytearray(0)

    # Use native C module if available (~50-100x faster)
    if _HAS_NATIVE:
        return _native.process_frames(
            fr1, fr2, fr3, am1, am2, am3,
            pitches, samp_flags, num_frames, speed
        )

    bufsize = 4 * speed * num_frames + 4096
    buf = bytearray(bufsize)

    # Local refs - critical for MicroPython speed
    sin_t = tables.SINUS
    rec_t = tables.RECTANGLE
    mul_t = tables.MULT_TABLE
    sam_t = tables.SAMPLE_TABLE
    sam_t_len = len(sam_t)
    tt = tables.TIME_TABLE
    t48 = tables.TAB48426

    bufpos = 0
    old_ti = 0
    phase1 = 0; phase2 = 0; phase3 = 0
    m_off = 0  # voiced sample offset
    y = 0
    k = num_frames
    speedcounter = speed
    glottal_pulse = pitches[0]
    n = glottal_pulse - (glottal_pulse >> 2)

    while k:
        flags = samp_flags[y] if y < num_frames else 0

        if flags & 248:
            # Sampled consonant
            hibyte = ((flags & 7) - 1) & 0xFF
            hi = hibyte * 256
            pitchl = flags & 248

            if pitchl == 0:
                # Voiced
                pitchl = pitches[y] >> 4
                off = m_off & 0xFF
                vph = (pitchl ^ 255) & 0xFF
                while True:
                    sample = sam_t[hi + off] if hi + off < sam_t_len else 0
                    for _ in range(8):
                        if sample & 128:
                            bufpos += tt[old_ti][3]; old_ti = 3
                            p = bufpos // 50
                            if p + 4 < bufsize:
                                buf[p]=160;buf[p+1]=160;buf[p+2]=160;buf[p+3]=160;buf[p+4]=160
                        else:
                            bufpos += tt[old_ti][4]; old_ti = 4
                            p = bufpos // 50
                            if p + 4 < bufsize:
                                buf[p]=96;buf[p+1]=96;buf[p+2]=96;buf[p+3]=96;buf[p+4]=96
                        sample = (sample << 1) & 0xFF
                    off = (off + 1) & 0xFF
                    vph = (vph + 1) & 0xFF
                    if vph == 0: break
                m_off = off
            else:
                # Unvoiced
                off = (pitchl ^ 255) & 0xFF
                m_val = t48[hibyte] if hibyte < len(t48) else 0x18
                v0 = (m_val & 15) * 16
                while True:
                    sample = sam_t[hi + off] if hi + off < sam_t_len else 0
                    for _ in range(8):
                        if sample & 128:
                            bufpos += tt[old_ti][2]; old_ti = 2
                            p = bufpos // 50
                            if p + 4 < bufsize:
                                buf[p]=80;buf[p+1]=80;buf[p+2]=80;buf[p+3]=80;buf[p+4]=80
                        else:
                            bufpos += tt[old_ti][1]; old_ti = 1
                            p = bufpos // 50
                            if p + 4 < bufsize:
                                buf[p]=v0;buf[p+1]=v0;buf[p+2]=v0;buf[p+3]=v0;buf[p+4]=v0
                        sample = (sample << 1) & 0xFF
                    off = (off + 1) & 0xFF
                    if off == 0: break

            y = (y + 2) & 0xFF
            k = (k - 2) & 0xFF
            speedcounter = speed
        else:
            # Formant synthesis via mult_table
            tmp = mul_t[sin_t[phase1] | am1[y]]
            tmp += mul_t[sin_t[phase2] | am2[y]]
            if tmp > 255: tmp += 1
            tmp += mul_t[rec_t[phase3] | am3[y]]
            tmp = ((tmp + 136) >> 4) & 0x0F

            # Inline timetable output
            bufpos += tt[old_ti][0]; old_ti = 0
            p = bufpos // 50
            if p + 4 < bufsize:
                v = tmp * 16
                buf[p]=v;buf[p+1]=v;buf[p+2]=v;buf[p+3]=v;buf[p+4]=v

            speedcounter = (speedcounter - 1) & 0xFF
            if speedcounter == 0:
                y = (y + 1) & 0xFF
                k = (k - 1) & 0xFF
                if k == 0: break
                speedcounter = speed

            glottal_pulse = (glottal_pulse - 1) & 0xFF
            if glottal_pulse != 0:
                n = (n - 1) & 0xFF
                if (n != 0) or (flags == 0):
                    phase1 = (phase1 + fr1[y]) & 0xFF
                    phase2 = (phase2 + fr2[y]) & 0xFF
                    phase3 = (phase3 + fr3[y]) & 0xFF
                    continue

                # Voiced sample interleave
                hibyte = ((flags & 7) - 1) & 0xFF
                hi = hibyte * 256
                pitchl = pitches[y] >> 4
                off = m_off & 0xFF
                vph = (pitchl ^ 255) & 0xFF
                while True:
                    sample = sam_t[hi + off] if hi + off < sam_t_len else 0
                    for _ in range(8):
                        if sample & 128:
                            bufpos += tt[old_ti][3]; old_ti = 3
                            p = bufpos // 50
                            if p + 4 < bufsize:
                                buf[p]=160;buf[p+1]=160;buf[p+2]=160;buf[p+3]=160;buf[p+4]=160
                        else:
                            bufpos += tt[old_ti][4]; old_ti = 4
                            p = bufpos // 50
                            if p + 4 < bufsize:
                                buf[p]=96;buf[p+1]=96;buf[p+2]=96;buf[p+3]=96;buf[p+4]=96
                        sample = (sample << 1) & 0xFF
                    off = (off + 1) & 0xFF
                    vph = (vph + 1) & 0xFF
                    if vph == 0: break
                m_off = off

        glottal_pulse = pitches[y]
        n = glottal_pulse - (glottal_pulse >> 2)
        phase1 = 0; phase2 = 0; phase3 = 0

    end = bufpos // 50
    return buf[:end]
