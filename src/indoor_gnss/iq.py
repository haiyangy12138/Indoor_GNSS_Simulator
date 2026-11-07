"""Chunked GPS L1 C/A complex-baseband waveform synthesis.

This is a channel/waveform research generator, not a complete GNSS simulator.
Default navigation symbols are +1: acquisition/tracking can be studied, but
there is NO valid LNAV message and hence NO standalone cold-start position fix.
External 50 bit/s symbols are accepted; their parity/ephemeris is not validated.

C/A register definitions/taps: IS-GPS-200N, section 3.3.2.3 / Table 3-Ia,
https://www.navcen.uscg.gov/sites/default/files/pdf/gps/IS-GPS-200N.pdf
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

C_MPS = 299_792_458.0
L1_HZ = 1_575_420_000.0
L1_WAVELENGTH_M = C_MPS / L1_HZ
CA_RATE_HZ = 1_023_000.0
CA_LENGTH = 1023

# One-based G2 phase-selection stages; PRN 1..32, IS-GPS-200N Table 3-Ia.
G2_TAPS = (
    (2, 6), (3, 7), (4, 8), (5, 9), (1, 9), (2, 10), (1, 8), (2, 9),
    (3, 10), (2, 3), (3, 4), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10),
    (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 9), (1, 3), (4, 6),
    (5, 7), (6, 8), (7, 9), (8, 10), (1, 6), (2, 7), (3, 8), (4, 9),
)


def ca_code(prn: int) -> np.ndarray:
    """Return one C/A period, with ICD binary 0 -> +1 and 1 -> -1."""
    if isinstance(prn, bool) or int(prn) != prn or not 1 <= int(prn) <= 32:
        raise ValueError("GPS L1 C/A implementation supports integer PRN 1..32")
    taps = G2_TAPS[int(prn) - 1]
    g1 = np.ones(10, dtype=np.uint8)
    g2 = np.ones(10, dtype=np.uint8)
    result = np.empty(CA_LENGTH, dtype=np.int8)
    for k in range(CA_LENGTH):
        bit = g1[9] ^ g2[taps[0] - 1] ^ g2[taps[1] - 1]
        result[k] = 1 - 2 * int(bit)
        feedback1 = g1[2] ^ g1[9]
        feedback2 = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
        g1[1:] = g1[:-1]
        g2[1:] = g2[:-1]
        g1[0] = feedback1
        g2[0] = feedback2
    return result


def _validate_series(series: dict[str, Any]) -> dict[str, np.ndarray]:
    s = {key: np.asarray(value) for key, value in series.items()}
    t = np.asarray(s["t_s"], dtype=float)
    p = np.asarray(s["prn"])
    if t.ndim != 1 or len(t) < 2 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("series.t_s must contain at least two increasing finite times")
    if p.ndim != 1 or len(p) == 0:
        raise ValueError("series.prn must be a non-empty one-dimensional path list")
    for prn in p:
        ca_code(prn)
    s["t_s"] = t
    s["prn"] = p.astype(int)
    for key in ("code_path_m", "carrier_path_m", "gain_linear", "phase_offset_rad"):
        a = np.asarray(s[key], dtype=float)
        if a.shape != (len(t), len(p)) or not np.all(np.isfinite(a)):
            raise ValueError(f"series.{key} must be finite with shape (times, paths)")
        s[key] = a
    if np.any(s["gain_linear"] < 0):
        raise ValueError("path voltage gains must be nonnegative")
    cn0 = np.asarray(s["cn0_dbhz"], dtype=float)
    if cn0.shape != (len(p),) or not np.all(np.isfinite(cn0)):
        raise ValueError("series.cn0_dbhz must have one finite value per path")
    s["cn0_dbhz"] = cn0
    return s


def _navigation_symbols(path: str | None, prns: np.ndarray) -> dict[int, tuple[float, np.ndarray]]:
    if not path:
        return {}
    with Path(path).open(encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    result = {}
    for prn in np.unique(prns):
        if str(prn) not in raw:
            raise ValueError(f"navigation_bits_file has no symbols for PRN {prn}")
        item = raw[str(prn)]
        bits = np.asarray(item["bits"])
        start = float(item["start_gps_sow"])
        if bits.ndim != 1 or len(bits) == 0 or not np.all(np.isin(bits, (0, 1))) or not np.isfinite(start):
            raise ValueError("navigation bits must be a nonempty array of 0/1 with finite start_gps_sow")
        result[int(prn)] = (start, (1 - 2 * bits.astype(np.int8)))
    return result


def render_iq(config: dict[str, Any], series: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Render a composite waveform and write IQ metadata; return the metadata.

    series columns are propagation paths, so repeated PRNs are allowed and sum
    coherently. code/carrier_path_m include all modeled clock and delay terms.
    gain_linear is a voltage multiplier (not a power multiplier). cn0_dbhz is
    the reference path C/N0 before gain_linear; do not apply path loss twice.

    With noise enabled N0=1, E|w[n]|²=fs and A²=10**(C/N0_dBHz/10), so the
    unfiltered complex white-noise bandwidth convention is explicitly fs Hz.
    No analog front-end bandlimiting, AGC dynamics, or antenna model is added.
    """
    cfg = config.get("iq", {})
    s = _validate_series(series)
    fs = float(cfg.get("sample_rate_hz", 4_000_000.0))
    duration = float(cfg.get("duration_s", 0.1))
    start = float(cfg.get("time_offset_s", cfg.get("start_s", 0.0)))
    digital_if = float(cfg.get("intermediate_frequency_hz", 0.0))
    sow = float(config["time"]["gps_sow"])
    chunk = int(cfg.get("chunk_samples", 65536))
    fmt = cfg.get("format", "ci16_le")
    headroom = float(cfg.get("adc_full_scale_sigma", 6.0))
    if not np.all(np.isfinite([fs, duration, start, digital_if, sow, headroom])):
        raise ValueError("I/Q numerical parameters must be finite")
    if fs < 2 * CA_RATE_HZ or duration <= 0 or chunk <= 0 or headroom <= 0:
        raise ValueError("I/Q needs fs >= 2.046 MHz, positive duration/chunk/headroom")
    # Rectangular chips have infinite sidelobes; this enforces main-lobe room.
    if abs(digital_if) + CA_RATE_HZ > fs / 2:
        raise ValueError("sample rate/IF leaves insufficient room for the C/A main lobe")
    if fmt not in ("ci16_le", "cf32_le"):
        raise ValueError("iq.format must be ci16_le or cf32_le")
    count = int(round(duration * fs))
    if count < 1:
        raise ValueError("I/Q duration is shorter than one sample")
    if start < s["t_s"][0] - 1e-12 or start + (count - 1) / fs > s["t_s"][-1] + 1e-12:
        raise ValueError("I/Q interval must be covered by propagation series; extrapolation is disabled")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = str(cfg.get("output_name", "signal.iq"))
    if Path(name).name != name or name in ("", ".", ".."):
        raise ValueError("iq.output_name must be a plain filename")
    if name.lower() in {'run_summary.json','run_error.json','iq_metadata.json','config.resolved.json',
        'provenance.json','scene.json','metrics.json','trajectory_truth.csv','observations.csv','receiver_solution.csv','channel_truth.npz','acquisition_check.json'}:
        raise ValueError('iq.output_name collides with a reserved experiment artifact')
    target = output_dir / name
    meta_path = output_dir / "iq_metadata.json"
    if target.exists() or meta_path.exists():
        raise FileExistsError("I/Q output or metadata already exists; use a new output directory")
    nav_file = cfg.get("navigation_bits_file")
    nav = _navigation_symbols(nav_file, s["prn"])
    for col, prn in enumerate(s["prn"]):
        if nav:
            bit_start, bits = nav[int(prn)]
            # Include knots in interval; piecewise-linear paths have no unseen extrema.
            knots = np.concatenate(([start], s["t_s"][(s["t_s"] > start) & (s["t_s"] < start + count / fs)], [start + (count - 1) / fs]))
            emitted = sow + knots - np.interp(knots, s["t_s"], s["code_path_m"][:, col]) / C_MPS
            if np.min(emitted) < bit_start or np.max(emitted) >= bit_start + len(bits) / 50:
                raise ValueError(f"navigation bits do not cover PRN {prn}'s emission times")
    powers = 10 ** (s["cn0_dbhz"] / 10.0)
    amplitudes = np.sqrt(powers)
    noise_enabled = bool(cfg.get("add_noise", cfg.get("noise_enabled", True)))
    # Fixed quantizer scale over the whole recording, no per-chunk normalization.
    variance_complex = (fs if noise_enabled else 0.0) + np.max(np.sum(s["gain_linear"] ** 2 * powers, axis=1))
    quant_scale = 32767 / (headroom * np.sqrt(max(variance_complex / 2, 1e-30)))
    rng = np.random.default_rng(np.random.SeedSequence([int(config.get("seed", 0)), 0x4951]))
    codes = {int(prn): ca_code(int(prn)) for prn in np.unique(s["prn"])}
    clipped = 0
    squared_sum = 0.0
    sha = hashlib.sha256()
    # Integer-sample indexing plus a common clock origin gives chunk invariance.
    with target.open("xb") as handle:
        for first in range(0, count, chunk):
            n = min(chunk, count - first)
            t = start + np.arange(first, first + n, dtype=np.float64) / fs
            signal = np.zeros(n, dtype=np.complex128)
            for col, prn_value in enumerate(s["prn"]):
                prn = int(prn_value)
                delay_m = np.interp(t, s["t_s"], s["code_path_m"][:, col])
                carrier_m = np.interp(t, s["t_s"], s["carrier_path_m"][:, col])
                gains = np.interp(t, s["t_s"], s["gain_linear"][:, col])
                phase0 = np.interp(t, s["t_s"], s["phase_offset_rad"][:, col])
                # Remove integer GPS seconds first: C/A repeats exactly each ms.
                chips = np.remainder((sow % 1.0 + t - delay_m / C_MPS) * CA_RATE_HZ, CA_LENGTH)
                indices = np.floor(chips).astype(np.int64) % CA_LENGTH
                code_samples = codes[prn][indices]
                if nav:
                    bit_start, bits = nav[prn]
                    emitted = sow + t - delay_m / C_MPS
                    bit_indices = np.floor((emitted - bit_start) * 50).astype(np.int64)
                    data = bits[bit_indices]
                else:
                    data = 1.0
                carrier_cycles = np.remainder(-carrier_m / L1_WAVELENGTH_M + digital_if * t + phase0 / (2 * np.pi), 1.0)
                signal += amplitudes[col] * gains * code_samples * data * np.exp(2j * np.pi * carrier_cycles)
            if noise_enabled:
                noise = rng.standard_normal((n, 2)) * np.sqrt(fs / 2)
                signal += noise[:, 0] + 1j * noise[:, 1]
            squared_sum += float(np.vdot(signal, signal).real)
            if fmt == "ci16_le":
                iq = np.column_stack((signal.real, signal.imag)) * quant_scale
                rounded = np.rint(iq)
                clipped += int(np.count_nonzero((rounded < -32768) | (rounded > 32767)))
                encoded = np.clip(rounded, -32768, 32767).astype("<i2").tobytes()
            else:
                encoded = signal.astype("<c8").tobytes()
            handle.write(encoded)
            sha.update(encoded)
    metadata = {
        "signal_file": name, "format": fmt, "iq_order": "IQIQ", "byte_order": "little",
        "sample_rate_hz": fs, "center_frequency_hz": L1_HZ,
        "intermediate_frequency_hz": digital_if, "sample_count": count,
        "duration_s": count / fs, "time_offset_s": start, "start_gps_sow": sow + start,
        "byte_count": target.stat().st_size, "sha256": sha.hexdigest(),
        "path_count": len(s["prn"]), "prns": sorted(codes),
        "noise_enabled": noise_enabled, "complex_noise_variance": fs if noise_enabled else 0,
        "noise_psd_convention": "complex N0=1; E|w|^2=fs; each quadrature variance=fs/2",
        "gain_convention": "gain_linear is voltage gain; cn0_dbhz is pre-gain reference C/N0",
        "quantizer_scale": quant_scale if fmt == "ci16_le" else 1.0,
        "clipped_components": clipped, "clipping_fraction": clipped / (2 * count),
        "mean_complex_power_before_quantization": squared_sum / count,
        "navigation_mode": "external_50bps_symbols_unverified" if nav else "constant_symbols_tracking_only",
        "navigation_bits_file": str(nav_file) if nav_file else None,
        "standalone_cold_fix_validated": False,
        "limitations": [
            "Default constant data symbols contain no valid LNAV/ephemeris/time message.",
            "External symbols require correct parity and ephemeris consistent with the simulated constellation; not checked here.",
            "No GNSS-SDR acquisition/tracking/navigation validation is implied by waveform generation.",
            "Rectangular-chip ideal complex baseband; no analog filtering, AGC dynamics or hardware impairments beyond configured paths.",
            "Finite sample rate truncates rectangular-chip spectrum; metadata main-lobe condition is not a strict anti-alias filter.",
        ],
        "ca_reference": "https://www.navcen.uscg.gov/sites/default/files/pdf/gps/IS-GPS-200N.pdf",
    }
    with meta_path.open("x", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    return metadata
