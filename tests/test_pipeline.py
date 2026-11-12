"""Проверка конвейера на эталонной записи (§3.2 разбора)."""

from __future__ import annotations

import unittest
from pathlib import Path

from biosignal.processing import EcgPipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_SIGNAL = PROJECT_ROOT / "test_data" / "raw_signal.txt"
FS = 250.0


class EcgPipelineReferenceTest(unittest.TestCase):
    """Конвейер должен воспроизводить эталонные числа задания."""

    @classmethod
    def setUpClass(cls) -> None:
        signal = [float(value) for value in RAW_SIGNAL.read_text(encoding="utf-8").split()]
        cls.result = EcgPipeline().process(signal, FS)

    def test_r_peaks(self) -> None:
        self.assertEqual(
            [complex_.r_peak_index for complex_ in self.result.complexes],
            [116, 325, 532, 742, 957, 1176],
        )

    def test_boundaries(self) -> None:
        self.assertEqual(
            [(complex_.onset_index, complex_.offset_index) for complex_ in self.result.complexes],
            [(108, 127), (317, 339), (524, 545), (734, 755), (946, 971), (1165, 1190)],
        )

    def test_widths(self) -> None:
        widths = [complex_.width_ms(FS) for complex_ in self.result.complexes]
        self.assertEqual(widths, [76.0, 88.0, 84.0, 84.0, 100.0, 100.0])

    def test_mean_width(self) -> None:
        self.assertAlmostEqual(self.result.features.mean_qrs_width_ms, 88.67, delta=2.0)

    def test_heart_rate(self) -> None:
        self.assertAlmostEqual(self.result.features.heart_rate_bpm, 70.75, delta=0.5)

    def test_amplitudes(self) -> None:
        features = self.result.features
        self.assertAlmostEqual(features.max_peak_amplitude, 0.9958, delta=0.01)
        self.assertAlmostEqual(features.std_amplitude, 0.1715, delta=0.01)
        self.assertEqual(features.r_peak_count, 6)
        self.assertEqual(features.qrs_count, 6)

    def test_artifact_is_suppressed(self) -> None:
        """Сырой выброс 2,15 на отсчёте 742 после фильтрации падает до ~0,877."""
        self.assertAlmostEqual(self.result.filtered_signal[742], 0.877, delta=0.01)
        self.assertEqual(
            max(range(len(self.result.filtered_signal)), key=self.result.filtered_signal.__getitem__),
            532,
        )


if __name__ == "__main__":
    unittest.main()
