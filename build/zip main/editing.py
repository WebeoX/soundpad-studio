"""
editing.py - Audio editing and effects (procedural, standard library only).

Every function takes an audio dict and RETURNS A NEW ONE, except mix_into()
which deliberately modifies the base audio (used by the mixer).

    audio = {"rate": 44100, "channels": [[...], [...]]}   floats in -1..1
"""
import math


# ------------------------------------------------------------------ basics
def make_audio(rate=44100, nch=2, seconds=0.0):
    """Create silent audio."""
    n = int(rate * seconds)
    return {"rate": rate, "channels": [[0.0] * n for _ in range(nch)]}


def length(audio):
    """Number of samples per channel."""
    return len(audio["channels"][0])


def duration(audio):
    """Length in seconds."""
    return length(audio) / audio["rate"]


def copy_audio(audio):
    return {"rate": audio["rate"], "channels": [list(c) for c in audio["channels"]]}


def get_peak(audio):
    return max((max(map(abs, c)) if c else 0.0) for c in audio["channels"])


def get_rms(audio):
    total, count = 0.0, 0
    for c in audio["channels"]:
        total += sum(s * s for s in c)
        count += len(c)
    return math.sqrt(total / count) if count else 0.0


def to_db(value):
    """Convert a linear level (0..1) to decibels."""
    return 20 * math.log10(value) if value > 0 else -120.0


def is_clipping(audio):
    return get_peak(audio) > 1.0


# --------------------------------------------------- channels and sample rate
def to_mono(audio):
    chans = audio["channels"]
    if len(chans) == 1:
        return copy_audio(audio)
    n = len(chans[0])
    mono = [sum(c[i] for c in chans) / len(chans) for i in range(n)]
    return {"rate": audio["rate"], "channels": [mono]}


def to_stereo(audio):
    chans = audio["channels"]
    if len(chans) == 2:
        return copy_audio(audio)
    if len(chans) == 1:
        return {"rate": audio["rate"], "channels": [list(chans[0]), list(chans[0])]}
    return {"rate": audio["rate"], "channels": [list(chans[0]), list(chans[1])]}


def match_channels(audio, nch):
    """Convert audio to mono (nch=1) or stereo (nch=2)."""
    if len(audio["channels"]) == nch:
        return copy_audio(audio)
    return to_mono(audio) if nch == 1 else to_stereo(audio)


def _stretch(ch, factor):
    """Linear-interpolation resampler. factor>1 = faster/shorter."""
    n = len(ch)
    if n == 0:
        return []
    out_len = int(n / factor)
    out = [0.0] * out_len
    for i in range(out_len):
        pos = i * factor
        i0 = int(pos)
        frac = pos - i0
        s0 = ch[i0]
        s1 = ch[i0 + 1] if i0 + 1 < n else s0
        out[i] = s0 + (s1 - s0) * frac
    return out


def resample(audio, new_rate):
    """Change the sample rate without changing the sound's speed."""
    if new_rate == audio["rate"]:
        return copy_audio(audio)
    factor = audio["rate"] / new_rate
    return {"rate": new_rate,
            "channels": [_stretch(c, factor) for c in audio["channels"]]}


# ------------------------------------------------------------ cut and join
def trim(audio, start_sec=0.0, end_sec=None):
    """Keep only the part between start_sec and end_sec."""
    rate = audio["rate"]
    n = length(audio)
    s = max(0, min(n, int(start_sec * rate)))
    e = n if end_sec is None else max(s, min(n, int(end_sec * rate)))
    return {"rate": rate, "channels": [c[s:e] for c in audio["channels"]]}


def cut_out(audio, start_sec, end_sec):
    """Delete the section between start_sec and end_sec."""
    first = trim(audio, 0, start_sec)
    last = trim(audio, end_sec, None)
    return merge(first, last)


def merge(a, b):
    """Join b after a (b is converted to match a's rate and channels)."""
    b = resample(b, a["rate"])
    b = match_channels(b, len(a["channels"]))
    return {"rate": a["rate"],
            "channels": [ca + cb for ca, cb in zip(a["channels"], b["channels"])]}


def merge_many(audio_list):
    """Join several audio clips end to end."""
    result = audio_list[0]
    for nxt in audio_list[1:]:
        result = merge(result, nxt)
    return result


def insert_silence(audio, at_sec, seconds):
    n = int(seconds * audio["rate"])
    pos = max(0, min(length(audio), int(at_sec * audio["rate"])))
    return {"rate": audio["rate"],
            "channels": [c[:pos] + [0.0] * n + c[pos:] for c in audio["channels"]]}


def loop_audio(audio, times):
    return {"rate": audio["rate"],
            "channels": [c * max(1, int(times)) for c in audio["channels"]]}


# ---------------------------------------------------------- volume and fades
def change_volume(audio, factor):
    return {"rate": audio["rate"],
            "channels": [[s * factor for s in c] for c in audio["channels"]]}


def fade_in(audio, seconds):
    out = copy_audio(audio)
    n = min(int(seconds * audio["rate"]), length(audio))
    for c in out["channels"]:
        for i in range(n):
            c[i] *= i / n
    return out


def fade_out(audio, seconds):
    out = copy_audio(audio)
    total = length(audio)
    n = min(int(seconds * audio["rate"]), total)
    for c in out["channels"]:
        for i in range(n):
            c[total - 1 - i] *= i / n
    return out


def normalize(audio, target_peak=0.95):
    """Scale so the loudest sample equals target_peak."""
    peak = get_peak(audio)
    if peak == 0:
        return copy_audio(audio)
    return change_volume(audio, target_peak / peak)


def apply_pan(audio, pan):
    """pan: -1.0 (full left) ... 0 (centre) ... +1.0 (full right). Returns stereo."""
    st = to_stereo(audio)
    left_gain = min(1.0, 1.0 - pan)
    right_gain = min(1.0, 1.0 + pan)
    st["channels"][0] = [s * left_gain for s in st["channels"][0]]
    st["channels"][1] = [s * right_gain for s in st["channels"][1]]
    return st


def limit(audio):
    """Hard-clamp every sample into -1..1 (prevents clipping distortion on save)."""
    return {"rate": audio["rate"],
            "channels": [[max(-1.0, min(1.0, s)) for s in c] for c in audio["channels"]]}


# ----------------------------------------------------------- time and pitch
def reverse(audio):
    return {"rate": audio["rate"], "channels": [c[::-1] for c in audio["channels"]]}


def change_speed(audio, factor):
    """factor 2.0 = twice as fast (and higher pitch); 0.5 = half speed."""
    if factor <= 0:
        raise ValueError("Speed factor must be positive.")
    return {"rate": audio["rate"],
            "channels": [_stretch(c, factor) for c in audio["channels"]]}


# ------------------------------------------------------------------ effects
def add_echo(audio, delay_sec=0.3, decay=0.5, repeats=3):
    """Add repeating, fading copies of the sound."""
    d = int(delay_sec * audio["rate"])
    extra = d * repeats
    out_channels = []
    for c in audio["channels"]:
        out = c + [0.0] * extra
        for r in range(1, repeats + 1):
            gain = decay ** r
            off = d * r
            for i in range(len(c)):
                out[i + off] += c[i] * gain
        out_channels.append(out)
    return {"rate": audio["rate"], "channels": out_channels}


def lowpass(audio, cutoff_hz):
    """Remove frequencies above cutoff_hz (simple one-pole filter)."""
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    dt = 1.0 / audio["rate"]
    alpha = dt / (rc + dt)
    out_channels = []
    for c in audio["channels"]:
        out, prev = [], 0.0
        for s in c:
            prev = prev + alpha * (s - prev)
            out.append(prev)
        out_channels.append(out)
    return {"rate": audio["rate"], "channels": out_channels}


def highpass(audio, cutoff_hz):
    """Remove frequencies below cutoff_hz."""
    low = lowpass(audio, cutoff_hz)
    return {"rate": audio["rate"],
            "channels": [[s - l for s, l in zip(c, lc)]
                         for c, lc in zip(audio["channels"], low["channels"])]}


def distortion(audio, amount=5.0):
    """Soft-clipping distortion. Higher amount = more crunch."""
    norm = math.tanh(amount)
    return {"rate": audio["rate"],
            "channels": [[math.tanh(s * amount) / norm for s in c]
                         for c in audio["channels"]]}


# -------------------------------------------------------------------- mixing
def mix_into(base, clip, start_sec=0.0, volume=1.0, pan=0.0):
    """Add `clip` into `base` starting at start_sec. MODIFIES base in place
    (extending it if needed). Used by the mixer to layer many tracks."""
    clip = resample(clip, base["rate"])
    clip = match_channels(clip, len(base["channels"]))
    if pan != 0 and len(base["channels"]) == 2:
        clip = apply_pan(clip, pan)

    start = int(start_sec * base["rate"])
    need = start + length(clip)
    for bc, cc in zip(base["channels"], clip["channels"]):
        if len(bc) < need:
            bc.extend([0.0] * (need - len(bc)))
        for i, s in enumerate(cc):
            bc[start + i] += s * volume
    return base


def mix_tracks(items, rate=44100, nch=2):
    """items = list of (audio, start_sec, volume, pan). Returns mixed audio."""
    base = make_audio(rate, nch, 0)
    for audio, start, vol, pan in items:
        mix_into(base, audio, start, vol, pan)
    return base


# --------------------------------------------------------------- quick demo
if __name__ == "__main__":
    # Builds a test tone, applies effects, and saves demo files, so you can
    # check the whole pipeline without needing any audio file of your own.
    from audio_io import save_wav, play_audio

    rate = 44100
    tone = make_audio(rate, 1, 1.0)
    tone["channels"][0] = [0.5 * math.sin(2 * math.pi * 440 * i / rate)
                           for i in range(rate)]

    edited = fade_out(fade_in(tone, 0.1), 0.3)
    edited = add_echo(edited, 0.25, 0.5, 3)
    edited = normalize(edited)

    save_wav("demo_tone.wav", edited)
    print("Saved demo_tone.wav  (%.2f sec, peak %.2f)" %
          (duration(edited), get_peak(edited)))
    play_audio(edited)