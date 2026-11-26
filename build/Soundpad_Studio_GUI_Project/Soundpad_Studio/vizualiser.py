"""
visualizer.py - Text-mode waveform display and frequency spectrum analyser.
The FFT (Fast Fourier Transform) is written from scratch, standard library only.
"""
import math
import cmath


def _mono(audio):
    ch = audio["channels"]
    if len(ch) == 1:
        return ch[0]
    return [(ch[0][i] + ch[1][i]) / 2 for i in range(len(ch[0]))]


# ----------------------------------------------------------------- waveform
def ascii_waveform(audio, width=72, height=11):
    """Return a multi-line string drawing the waveform's loudness over time."""
    data = _mono(audio)
    n = len(data)
    if n == 0:
        return "(empty audio)"
    if height % 2 == 0:
        height += 1
    half = height // 2

    peaks = []
    for c in range(width):
        s = c * n // width
        e = max(s + 1, (c + 1) * n // width)
        peaks.append(max(abs(v) for v in data[s:e]))

    lines = []
    for row in range(height):
        if row == half:
            lines.append("".join("#" if p > 0.005 else "-" for p in peaks))
        else:
            need = abs(half - row) / half - 0.5 / half
            lines.append("".join("#" if p >= need else " " for p in peaks))

    total = n / audio["rate"]
    end_label = "%.2fs" % total
    ruler = "0.00s" + " " * max(1, width - len("0.00s") - len(end_label)) + end_label
    return "\n".join(lines + [ruler])


# ----------------------------------------------------------------------- FFT
def fft(x):
    """Recursive radix-2 FFT. len(x) must be a power of two."""
    n = len(x)
    if n == 1:
        return list(x)
    even = fft(x[0::2])
    odd = fft(x[1::2])
    out = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * math.pi * k / n) * odd[k]
        out[k] = even[k] + t
        out[k + n // 2] = even[k] - t
    return out


def spectrum_bands(audio, bands=32, size=4096, start_sec=None,
                   f_low=40.0, f_high=16000.0):
    """Analyse `size` samples and return (band_levels_0_to_1, edges_in_hz).
    Bands are spaced logarithmically, like musical pitch."""
    data = _mono(audio)
    rate = audio["rate"]
    n = len(data)
    if start_sec is None:
        start = max(0, n // 2 - size // 2)            # middle of the audio
    else:
        start = max(0, min(n - 1, int(start_sec * rate)))
    window = data[start:start + size]
    window = window + [0.0] * (size - len(window))
    # Hann window reduces spectral "leakage"
    window = [v * (0.5 - 0.5 * math.cos(2 * math.pi * i / (size - 1)))
              for i, v in enumerate(window)]

    spec = fft(window)
    mags = [abs(spec[k]) for k in range(1, size // 2)]
    freqs = [k * rate / size for k in range(1, size // 2)]

    f_high = min(f_high, rate / 2)
    edges = [f_low * (f_high / f_low) ** (i / bands) for i in range(bands + 1)]
    levels = []
    for b in range(bands):
        vals = [m for m, f in zip(mags, freqs) if edges[b] <= f < edges[b + 1]]
        levels.append(max(vals) if vals else 0.0)

    peak = max(levels)
    if peak <= 0:
        return [0.0] * bands, edges
    out = []
    for v in levels:
        db = 20 * math.log10(v / peak) if v > 0 else -90
        out.append(max(0.0, (db + 60) / 60))          # show a 60 dB range
    return out, edges


def ascii_spectrum(audio, bands=32, height=12, start_sec=None):
    """Return a bar-chart string of the frequency content."""
    levels, edges = spectrum_bands(audio, bands, 4096, start_sec)
    if not any(levels):
        return "(silent - nothing to analyse)"
    lines = []
    for row in range(height, 0, -1):
        lines.append("".join(" # " if v >= row / height else "   " for v in levels))
    lines.append("---" * bands)

    def fmt(f):
        return "%.1fk" % (f / 1000) if f >= 1000 else "%d" % f
    left, mid, right = fmt(edges[0]), fmt(edges[bands // 2]), fmt(edges[-1])
    width = 3 * bands
    label = left + " " * ((width // 2) - len(left) - len(mid) // 2) + mid
    label += " " * max(1, width - len(label) - len(right)) + right
    lines.append(label + "  Hz")
    return "\n".join(lines)