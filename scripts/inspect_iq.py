"""Offline GPS C/A FFT acquisition diagnostic for generated run directories.

This is NOT GNSS-SDR, a tracking loop, a navigation decoder, or an observable
generator. It searches code phase and carrier frequency in 1-ms coherent blocks
and accumulates block powers noncoherently. Expected values come from separately
saved channel truth, not from the acquisition search. Peak/median is diagnostic,
not a calibrated false-alarm probability or proof of a usable navigation fix.

Usage: python scripts/inspect_iq.py experiments/relay_demo
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from indoor_gnss.iq import CA_RATE_HZ, CA_LENGTH, C_MPS, L1_WAVELENGTH_M, ca_code  # noqa: E402


def circular_chip_difference(a: float, b: float) -> float:
    return float((a - b + CA_LENGTH / 2) % CA_LENGTH - CA_LENGTH / 2)


def expected_paths(truth: dict, prn: int, start_s: float, duration_s: float, sow: float) -> list[dict]:
    """Evaluate independently saved paths around the acquisition interval."""
    times = truth["t_s"]
    if start_s < times[0] or start_s + duration_s > times[-1] + 1e-9:
        raise ValueError("channel truth does not cover diagnostic interval")
    result = []
    for col in np.flatnonzero(truth["prn"] == prn):
        path0 = float(np.interp(start_s, times, truth["carrier_path_m"][:, col]))
        path1 = float(np.interp(start_s + duration_s, times, truth["carrier_path_m"][:, col]))
        phase0 = float(np.interp(start_s, times, truth["phase_offset_rad"][:, col]))
        phase1 = float(np.interp(start_s + duration_s, times, truth["phase_offset_rad"][:, col]))
        mean_doppler = -(path1 - path0) / duration_s / L1_WAVELENGTH_M + (phase1 - phase0) / duration_s / (2 * np.pi)
        code_path = float(np.interp(start_s, times, truth["code_path_m"][:, col]))
        code_phase = float(((sow % 1.0 + start_s - code_path / C_MPS) * CA_RATE_HZ) % CA_LENGTH)
        gains = np.interp(np.linspace(start_s, start_s + duration_s, 11), times, truth["gain_linear"][:, col])
        result.append({"channel_index": int(col), "expected_mean_doppler_hz": float(mean_doppler),
                       "expected_code_phase_chips_at_first_sample": code_phase,
                       "mean_voltage_gain": float(np.mean(gains)),
                       "reference_cn0_dbhz": float(truth["cn0_dbhz"][col]),
                       "relative_mean_power": float(np.mean(gains ** 2) * 10 ** (truth["cn0_dbhz"][col] / 10))})
    return result


def inspect(run_dir: str | Path, integrate_ms: int = 10, doppler_max_hz: float = 10000,
            doppler_step_hz: float = 250, prns: list[int] | None = None,
            output_name: str = "acquisition_check.json") -> dict:
    run_dir = Path(run_dir).resolve()
    meta = json.loads((run_dir / "iq_metadata.json").read_text(encoding="utf-8-sig"))
    with np.load(run_dir / "channel_truth.npz", allow_pickle=False) as raw:
        truth = {key: raw[key] for key in raw.files}
    fs = float(meta["sample_rate_hz"])
    per_ms = int(round(fs / 1000))
    if abs(fs / 1000 - per_ms) > 1e-8:
        raise ValueError("This diagnostic requires an integer sample count per 1-ms C/A period")
    if integrate_ms < 1 or doppler_max_hz < 0 or doppler_step_hz <= 0:
        raise ValueError("integration must be positive; max Doppler >= 0 and step > 0")
    signal_path = run_dir / str(meta["signal_file"])
    fmt = meta["format"]
    if fmt not in ("ci16_le", "cf32_le"):
        raise ValueError("Only ci16_le and cf32_le formats are supported")
    available = min(int(meta["sample_count"]), signal_path.stat().st_size // (4 if fmt == "ci16_le" else 8))
    block_count = min(integrate_ms, available // per_ms)
    if block_count == 0:
        raise ValueError("At least 1 ms of I/Q samples is needed")
    count = block_count * per_ms
    if fmt == "ci16_le":
        packed = np.fromfile(signal_path, dtype="<i2", count=count * 2).astype(float).reshape(-1, 2)
        samples = packed[:, 0] + 1j * packed[:, 1]
    else:
        samples = np.fromfile(signal_path, dtype="<c8", count=count).astype(np.complex128)
    samples = samples.reshape(block_count, per_ms)
    chosen = sorted(set(int(p) for p in (prns if prns is not None else meta["prns"])))
    for p in chosen:
        ca_code(p)
    if not chosen:
        raise ValueError("No PRNs requested")
    if not set(chosen).issubset(set(truth["prn"].tolist())):
        raise ValueError("Requested PRNs are absent from channel_truth.npz")
    local_chip = np.floor(np.arange(per_ms) * CA_RATE_HZ / fs).astype(int) % CA_LENGTH
    local_ffts = {p: np.conj(np.fft.fft(ca_code(p)[local_chip])) for p in chosen}
    bins = np.arange(-doppler_max_hz, doppler_max_hz + doppler_step_hz * 0.5, doppler_step_hz)
    digital_if = float(meta.get("intermediate_frequency_hz", 0))
    sample_times = np.arange(per_ms) / fs
    best = {p: {"peak_power": -1.0} for p in chosen}
    for doppler in bins:
        wipe = np.exp(-2j * np.pi * (digital_if + doppler) * sample_times)
        spectra = np.fft.fft(samples * wipe[None, :], axis=1)
        for prn in chosen:
            correlation = np.fft.ifft(spectra * local_ffts[prn][None, :], axis=1)
            power = np.sum(np.abs(correlation) ** 2, axis=0)
            lag = int(np.argmax(power))
            peak = float(power[lag])
            if peak > best[prn]["peak_power"]:
                median = float(np.median(power))
                best[prn] = {"prn": prn, "peak_power": peak,
                             "peak_doppler_hz": float(doppler),
                             "peak_total_digital_frequency_hz": float(digital_if + doppler),
                             "peak_correlation_lag_samples": lag,
                             "estimated_code_phase_chips_at_first_sample": float((-lag * CA_RATE_HZ / fs) % CA_LENGTH),
                             "peak_to_median_power": peak / max(median, np.finfo(float).tiny)}
    start_s = float(meta.get("time_offset_s", 0))
    sow = float(meta["start_gps_sow"]) - start_s
    for prn, item in best.items():
        paths = expected_paths(truth, prn, start_s, count / fs, sow)
        strongest = max(paths, key=lambda p: p["relative_mean_power"])
        item["truth_paths"] = paths
        item["comparison_reference"] = "largest predicted mean path power; coherent multipath can shift the measured peak"
        item["expected_mean_doppler_hz"] = strongest["expected_mean_doppler_hz"]
        item["doppler_error_hz"] = item["peak_doppler_hz"] - strongest["expected_mean_doppler_hz"]
        item["expected_code_phase_chips_at_first_sample"] = strongest["expected_code_phase_chips_at_first_sample"]
        item["code_phase_error_chips_circular"] = circular_chip_difference(
            item["estimated_code_phase_chips_at_first_sample"], strongest["expected_code_phase_chips_at_first_sample"])
    report = {
        "diagnostic": "GPS L1 C/A FFT acquisition search only",
        "created_utc": datetime.now(timezone.utc).isoformat(), "run_directory": str(run_dir),
        "sample_rate_hz": fs, "samples_processed": count,
        "coherent_integration_ms": 1, "noncoherent_blocks": block_count,
        "doppler_search_max_hz": doppler_max_hz, "doppler_search_step_hz": doppler_step_hz,
        "code_phase_grid_chips": CA_RATE_HZ / fs,
        "code_phase_definition": "local transmitted C/A chip phase at the recording's first sample; phase=(-FFT correlation lag)*chip_rate/fs modulo 1023",
        "results": [best[p] for p in chosen],
        "limitations": [
            "No DLL/PLL tracking, LNAV decoding, pseudorange generation, position or velocity solution.",
            "Peak/median is an uncalibrated diagnostic, not a detection probability or false-alarm test.",
            "Frequency accuracy is limited by the search grid, integration duration, noise and changing Doppler.",
            "Expected code phase is at the first sample; noncoherent accumulation can smear peaks during motion.",
            "Coherent paths sharing one PRN may shift the peak away from any individual path's truth.",
            "No claim of GNSS-SDR compatibility or cold-start navigation is made.",
        ],
    }
    if Path(output_name).name != output_name:
        raise ValueError("Output must be a plain filename within run_dir")
    target = run_dir / output_name
    with target.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--integrate-ms", type=int, default=10)
    parser.add_argument("--doppler-max-hz", type=float, default=10000)
    parser.add_argument("--doppler-step-hz", type=float, default=250)
    parser.add_argument("--prns", type=int, nargs="+")
    parser.add_argument("--output-name", default="acquisition_check.json")
    args = parser.parse_args()
    report = inspect(args.run_dir, args.integrate_ms, args.doppler_max_hz, args.doppler_step_hz, args.prns, args.output_name)
    print(json.dumps({"output": str(args.run_dir / args.output_name), "results": [
        {k: row[k] for k in ("prn", "peak_doppler_hz", "expected_mean_doppler_hz", "doppler_error_hz", "code_phase_error_chips_circular", "peak_to_median_power")}
        for row in report["results"]]}, indent=2))


if __name__ == "__main__":
    main()
