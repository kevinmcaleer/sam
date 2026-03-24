"""
SAM phoneme definitions and processing.
Ported from sam.c in the original SAM source.

Handles phoneme parsing (text phoneme codes -> internal indices),
stress assignment, phoneme rule transformations, length setting,
breath insertion, and output preparation.
"""

from . import tables

# Flag constants for phoneme classification
FLAG_VOWEL    = 0x80
FLAG_VOICED   = 0x40
FLAG_STOP     = 0x20
FLAG_FRICATIVE = 0x10
FLAG_NASAL    = 0x08
FLAG_LIQUID   = 0x04
FLAG_ALVEOLAR = 0x02
FLAG_PALATAL  = 0x01

FLAG2_DIPTHONG = 0x04
FLAG2_PLOSIVE  = 0x20
FLAG2_GLOTTAL  = 0x40

# Phoneme name pairs for parsing input
# Each phoneme has a 2-char code. Second char '*' means single-char match.
PHONEME_NAMES = [
    " *", ".*", "?*", ",*", "-*",
    "IY", "IH", "EH", "AE", "AA", "AH", "AO", "UH",
    "AX", "IX", "ER", "UX", "OH", "RX", "LX", "WX", "YX",
    "WH", "R*", "L*", "W*", "Y*",
    "M*", "N*", "NX", "DX", "Q*",
    "S*", "SH", "F*", "TH", "/H", "/X",
    "Z*", "ZH", "V*", "DH",
    "CH", "**", "J*", "**", "**", "**",
    "EY", "AY", "OY", "AW", "OW", "UW",
    "B*", "**", "**",
    "D*", "**", "**",
    "G*", "**", "**", "GX", "**", "**",
    "P*", "**", "**",
    "T*", "**", "**",
    "K*", "**", "**", "KX", "**", "**",
    "UL", "UM", "UN",
]


def parser1(input_str):
    """
    Parser1: Convert phoneme string to internal phoneme index list.
    Scans the input for 2-char and 1-char phoneme codes.
    Returns (phoneme_index[], stress[]).
    """
    phoneme_index = []
    stress_arr = []
    src = 0
    inp = input_str.upper()

    while src < len(inp):
        ch = inp[src]

        # Check for end marker
        if ch == '\x9b' or ch == '\x00':
            break

        # Skip spaces
        if ch == ' ':
            phoneme_index.append(0)  # space phoneme
            stress_arr.append(0)
            src += 1
            continue

        # Check for stress markers 1-8
        if ch in '12345678':
            # Apply stress to the last phoneme
            if len(stress_arr) > 0:
                stress_arr[-1] = ord(ch) - ord('0')
            src += 1
            continue

        # Try two-character match first
        found = False
        if src + 1 < len(inp):
            pair = ch + inp[src + 1]
            for idx in range(len(PHONEME_NAMES)):
                name = PHONEME_NAMES[idx]
                if name[1] != '*' and name == pair:
                    phoneme_index.append(idx)
                    stress_arr.append(0)
                    src += 2
                    found = True
                    break

        # Try single-character match (names with '*' as second char)
        if not found:
            for idx in range(len(PHONEME_NAMES)):
                name = PHONEME_NAMES[idx]
                if name[1] == '*' and name[0] == ch:
                    phoneme_index.append(idx)
                    stress_arr.append(0)
                    src += 1
                    found = True
                    break

        if not found:
            # Skip unrecognized character
            src += 1

    # End marker
    phoneme_index.append(255)
    stress_arr.append(0)
    return phoneme_index, stress_arr


def parser2(phoneme_index, stress):
    """
    Parser2: Apply phoneme transformation rules.
    Modifies phoneme list in-place for diphthongs, affricates,
    consonant clusters, etc.
    """
    pos = 0
    while pos < len(phoneme_index):
        idx = phoneme_index[pos]
        if idx == 255:
            break
        if idx == 0:
            pos += 1
            continue

        flags = tables.PHONEME_FLAGS[idx] if idx < len(tables.PHONEME_FLAGS) else 0
        flags2 = tables.PHONEME_FLAGS2[idx] if idx < len(tables.PHONEME_FLAGS2) else 0

        # Rule: Diphthong handling - insert WX or YX after diphthong vowels
        if flags2 & FLAG2_DIPTHONG:
            # Diphthongs 48-50 (EY,AY,OY) get YX appended
            # Diphthongs 51-53 (AW,OW,UW) get WX appended
            if idx >= 48 and idx <= 53:
                if idx <= 50:
                    insert_ph = 21  # YX
                else:
                    insert_ph = 20  # WX
                phoneme_index.insert(pos + 1, insert_ph)
                stress.insert(pos + 1, stress[pos])
                pos += 2
                continue

        # Rule: UL -> AX L
        if idx == 78:  # UL
            phoneme_index[pos] = 13  # AX
            phoneme_index.insert(pos + 1, 24)  # L
            stress.insert(pos + 1, stress[pos])
            pos += 2
            continue

        # Rule: UM -> AX M
        if idx == 79:  # UM
            phoneme_index[pos] = 13  # AX
            phoneme_index.insert(pos + 1, 27)  # M
            stress.insert(pos + 1, stress[pos])
            pos += 2
            continue

        # Rule: UN -> AX N
        if idx == 80:  # UN
            phoneme_index[pos] = 13  # AX
            phoneme_index.insert(pos + 1, 28)  # N
            stress.insert(pos + 1, stress[pos])
            pos += 2
            continue

        # Rule: CH -> CH CH' (affricate)
        if idx == 42:  # CH
            phoneme_index.insert(pos + 1, 43)  # CH second part
            stress.insert(pos + 1, stress[pos])
            pos += 2
            continue

        # Rule: J -> J J' (affricate)
        if idx == 44:  # J
            phoneme_index.insert(pos + 1, 45)  # J second part
            stress.insert(pos + 1, stress[pos])
            pos += 2
            continue

        # Rule: Voiced stop/fricative softening after S
        # SP->SB, ST->SD, SK->SG, SKX->SGX
        if idx == 32:  # S
            nxt = phoneme_index[pos + 1] if pos + 1 < len(phoneme_index) else 255
            if nxt == 66:    # P -> B
                phoneme_index[pos + 1] = 54  # B
            elif nxt == 69:  # T -> D
                phoneme_index[pos + 1] = 57  # D
            elif nxt == 72:  # K -> G
                phoneme_index[pos + 1] = 60  # G
            elif nxt == 75:  # KX -> GX
                phoneme_index[pos + 1] = 63  # GX

        # Rule: T+R -> CH+R, D+R -> J+R
        if idx == 69:  # T
            nxt = phoneme_index[pos + 1] if pos + 1 < len(phoneme_index) else 255
            if nxt == 23:  # R
                phoneme_index[pos] = 42  # CH
                pos += 1
                continue
        if idx == 57:  # D
            nxt = phoneme_index[pos + 1] if pos + 1 < len(phoneme_index) else 255
            if nxt == 23:  # R
                phoneme_index[pos] = 44  # J
                pos += 1
                continue

        # Rule: Vowel + R -> Vowel + RX
        if flags & FLAG_VOWEL:
            nxt = phoneme_index[pos + 1] if pos + 1 < len(phoneme_index) else 255
            if nxt == 23:  # R
                phoneme_index[pos + 1] = 18  # RX

            # Rule: Vowel + L -> Vowel + LX
            elif nxt == 24:  # L
                phoneme_index[pos + 1] = 19  # LX

        # Rule: Consonant clusters - G before certain vowels -> GX
        if idx == 60:  # G
            nxt = phoneme_index[pos + 1] if pos + 1 < len(phoneme_index) else 255
            if nxt < len(tables.PHONEME_FLAGS):
                nflags = tables.PHONEME_FLAGS[nxt]
                if nflags & FLAG_VOWEL:
                    # Check if front vowel (IY, IH, EH, AE)
                    if nxt in (5, 6, 7, 8):
                        phoneme_index[pos] = 63  # GX

        # Same for K -> KX before front vowels
        if idx == 72:  # K
            nxt = phoneme_index[pos + 1] if pos + 1 < len(phoneme_index) else 255
            if nxt < len(tables.PHONEME_FLAGS):
                if nxt in (5, 6, 7, 8):
                    phoneme_index[pos] = 75  # KX

        pos += 1

    return phoneme_index, stress


def copy_stress(phoneme_index, stress):
    """
    Propagate stress from vowels to preceding consonants.
    """
    for i in range(len(phoneme_index) - 1):
        idx = phoneme_index[i]
        if idx == 255:
            break
        if idx >= len(tables.PHONEME_FLAGS):
            continue
        flags = tables.PHONEME_FLAGS[idx]
        # If current is not a vowel and next has stress
        if not (flags & FLAG_VOWEL) and (flags & FLAG_VOICED):
            nxt = phoneme_index[i + 1] if i + 1 < len(phoneme_index) else 255
            if nxt != 255 and nxt < len(tables.PHONEME_FLAGS):
                if tables.PHONEME_FLAGS[nxt] & FLAG_VOWEL:
                    if stress[i + 1] > 0:
                        stress[i] = stress[i + 1] + 1


def set_phoneme_length(phoneme_index, stress):
    """
    Assign duration to each phoneme based on stress level.
    Returns phoneme_length array.
    """
    lengths = []
    for i in range(len(phoneme_index)):
        idx = phoneme_index[i]
        if idx == 255:
            lengths.append(0)
            break
        if idx >= len(tables.PHONEME_LENGTH):
            lengths.append(6)
            continue
        if stress[i] > 0 and idx < len(tables.PHONEME_STRESSED_LENGTH):
            lengths.append(tables.PHONEME_STRESSED_LENGTH[idx])
        else:
            lengths.append(tables.PHONEME_LENGTH[idx])
    return lengths


def adjust_lengths(phoneme_index, phoneme_length, stress):
    """
    Apply SAM's 7 duration adjustment rules.
    Modifies phoneme_length in-place.
    """
    for i in range(len(phoneme_index)):
        idx = phoneme_index[i]
        if idx == 255:
            break

        # Get next phoneme
        nxt_i = i + 1
        nxt = phoneme_index[nxt_i] if nxt_i < len(phoneme_index) else 255

        if idx >= len(tables.PHONEME_FLAGS) or nxt == 255:
            continue
        flags = tables.PHONEME_FLAGS[idx]
        nxt_flags = tables.PHONEME_FLAGS[nxt] if nxt < len(tables.PHONEME_FLAGS) else 0

        # Rule 1: Lengthen before punctuation
        if nxt in (1, 2, 3):  # . ? ,
            if flags & (FLAG_VOICED | FLAG_FRICATIVE):
                phoneme_length[i] = (phoneme_length[i] * 3) // 2 + 1

        # Rule 2: Vowel before consonant - shorten if RX or LX follows
        if flags & FLAG_VOWEL:
            if nxt in (18, 19):  # RX, LX
                if nxt_i + 1 < len(phoneme_index):
                    nn = phoneme_index[nxt_i + 1]
                    if nn != 255 and nn < len(tables.PHONEME_FLAGS):
                        if not (tables.PHONEME_FLAGS[nn] & FLAG_VOWEL):
                            phoneme_length[i] = max(1, phoneme_length[i] - 1)

        # Rule 3: Vowel + unvoiced plosive -> shorten vowel
        if flags & FLAG_VOWEL:
            if nxt_flags & FLAG_STOP:
                if not (nxt_flags & FLAG_VOICED):
                    phoneme_length[i] = phoneme_length[i] - (phoneme_length[i] >> 3)

        # Rule 4: Vowel + voiced consonant -> lengthen vowel
        if flags & FLAG_VOWEL:
            if (nxt_flags & FLAG_VOICED) and not (nxt_flags & FLAG_VOWEL):
                phoneme_length[i] = (phoneme_length[i] * 5) // 4 + 1

        # Rule 5: Nasal + stop -> set specific lengths
        if flags & FLAG_NASAL:
            if nxt_flags & FLAG_STOP:
                phoneme_length[i] = 5
                if nxt_i < len(phoneme_length):
                    phoneme_length[nxt_i] = 6

        # Rule 6: Stop + stop -> shorten both
        if flags & FLAG_STOP:
            if nxt_flags & FLAG_STOP:
                phoneme_length[i] = (phoneme_length[i] >> 1) + 1

        # Rule 7: Liquid/glide + diphthong -> shorten liquid
        if flags & FLAG_LIQUID:
            if nxt >= 48 and nxt <= 53:  # diphthongs
                phoneme_length[i] = max(1, phoneme_length[i] - 2)


def insert_breath(phoneme_index, phoneme_length, stress):
    """
    Insert breath pauses (Q*) and phrase boundaries.
    """
    total = 0
    i = 0
    while i < len(phoneme_index):
        idx = phoneme_index[i]
        if idx == 255:
            break

        total += phoneme_length[i] if i < len(phoneme_length) else 0

        # Insert breath at phrase boundaries or when duration exceeds threshold
        if total > 232:
            # Insert Q* (phoneme 31) before current position
            phoneme_index.insert(i, 31)
            phoneme_length.insert(i, 5)
            stress.insert(i, 0)
            total = 0
            i += 1

        # Also insert at punctuation
        if idx in (1, 2, 3):  # . ? ,
            total = 0

        i += 1


def process_phonemes(input_str, speed=72):
    """
    Full phoneme processing pipeline.
    Takes a phoneme string like '/HEH4LOW WERLD'
    Returns (phoneme_index, phoneme_length, stress) ready for rendering.
    """
    # Stage 1: Parse phoneme codes
    phoneme_index, stress_arr = parser1(input_str)

    # Stage 2: Apply transformation rules
    phoneme_index, stress_arr = parser2(phoneme_index, stress_arr)

    # Propagate stress
    copy_stress(phoneme_index, stress_arr)

    # Set lengths
    phoneme_length = set_phoneme_length(phoneme_index, stress_arr)

    # Adjust lengths based on context
    adjust_lengths(phoneme_index, phoneme_length, stress_arr)

    # Insert breaths
    insert_breath(phoneme_index, phoneme_length, stress_arr)

    # Apply speed
    if speed != 72:
        for i in range(len(phoneme_length)):
            phoneme_length[i] = max(1, (phoneme_length[i] * speed) // 72)

    return phoneme_index, phoneme_length, stress_arr
