"""Machine-load readings, and the threshold for "you would notice this".

Calibrated to a near-silent desktop: idle is ~32% fan and 45-50C. Generic
datacentre thresholds (75C / 60% fan) would have read green through an entire
day of audible fans, which is worse than having no threshold at all.
"""
from __future__ import annotations

from gauntlet.overlay import format_load
from gauntlet.telemetry import GpuLoad, parse_nvidia_smi, system_memory


def test_parses_a_full_reading():
    gpu = parse_nvidia_smi("73, 62, 98, 29795, 32607")
    assert (gpu.temperature_c, gpu.fan_pct, gpu.utilisation_pct) == (73, 62, 98)
    assert (gpu.vram_used_mib, gpu.vram_total_mib) == (29795, 32607)


def test_parses_units_and_whitespace():
    """nvidia-smi emits '73 C' / '62 %' / '29795 MiB' depending on flags."""
    gpu = parse_nvidia_smi(" 73 C , 62 % , 98 % , 29795 MiB , 32607 MiB ")
    assert (gpu.temperature_c, gpu.fan_pct, gpu.vram_used_mib) == (73, 62, 29795)


def test_a_not_available_field_does_not_discard_the_whole_reading():
    """Fan speed reads [N/A] on laptops and some datacentre cards. Losing the
    temperature because the fan is unreported would be the wrong trade."""
    gpu = parse_nvidia_smi("73, [N/A], 98, 29795, 32607")
    assert gpu.temperature_c == 73
    assert gpu.fan_pct is None
    assert gpu.is_hot


def test_a_short_row_leaves_missing_fields_none():
    gpu = parse_nvidia_smi("55")
    assert gpu.temperature_c == 55
    assert gpu.vram_total_mib is None
    assert gpu.vram_pct is None


def test_idle_on_this_machine_is_not_stressed():
    """The real observed idle: 47C, 32% fan. Must read calm, or the indicator
    cries wolf and gets ignored."""
    assert not GpuLoad(temperature_c=47, fan_pct=32).is_stressed


def test_the_state_that_prompted_the_complaint_reads_stressed():
    """Observed mid-run: 73C, fan climbing. This is the case a generic 75C
    threshold would have missed entirely."""
    assert GpuLoad(temperature_c=73, fan_pct=62).is_stressed
    assert GpuLoad(temperature_c=73, fan_pct=None).is_stressed  # heat alone
    assert GpuLoad(temperature_c=None, fan_pct=55).is_stressed  # noise alone


def test_a_busy_but_cool_and_quiet_card_is_not_stressed():
    """Utilisation is deliberately not part of the judgement -- a card pinned at
    100% that stays cool and silent is not something anyone notices."""
    assert not GpuLoad(temperature_c=52, fan_pct=35, utilisation_pct=100).is_stressed


def test_vram_percentage():
    assert GpuLoad(vram_used_mib=16000, vram_total_mib=32000).vram_pct == 50.0
    assert GpuLoad().vram_pct is None


def test_format_load_omits_missing_fields_rather_than_showing_zero():
    assert format_load(None) == ""
    assert format_load(GpuLoad(temperature_c=61)) == "61°C"
    text = format_load(GpuLoad(temperature_c=61, fan_pct=40,
                               vram_used_mib=20480, vram_total_mib=32607))
    assert "61°C" in text and "fan 40%" in text and "20.0/32GB" in text


def test_system_memory_reads_something_sane():
    """The reading that VRAM alone missed: a KV cache overflowing the card
    spills to system RAM, and that spill is what made the machine crawl."""
    mem = system_memory()
    assert mem is not None
    assert mem.total_gb > 1
    assert 0 <= mem.used_gb <= mem.total_gb
    assert 0 <= mem.used_pct <= 100
