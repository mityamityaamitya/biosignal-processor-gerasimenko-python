"""Ядро обработки биосигналов: чистые функции без веб-фреймворков.

Модуль реализует конвейер варианта 4 (ЭКГ):

1. сглаживание скользящим средним (окно 7 отсчётов) — против высокочастотного
   мышечного тремора;
2. ФВЧ Баттерворта 2-го порядка (0.5 Гц) с нулевой фазой — против дрейфа
   изолинии;
3. детекция R-пиков по энергии первой производной (Pan-Tompkins-подобная);
4. границы QRS по падению энергии первой производной ниже 10 % от максимума
   в окрестности R-пика;
5. расчёт признаков.

Здесь нет ни одного импорта FastAPI/Flask/uvicorn: модуль тестируется отдельно
от сети и переиспользуется любым транспортом.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import ndimage, signal as scipy_signal

import config

MILLISECONDS_PER_SECOND = 1000.0
SECONDS_PER_MINUTE = 60.0


# --- Вспомогательные преобразования ------------------------------------------


def _samples(ms: float, fs: float) -> int:
    """Переводит длительность в миллисекундах в число отсчётов (не меньше 1)."""
    return max(1, int(round(ms * fs / MILLISECONDS_PER_SECOND)))


def _odd_window_samples(ms: float, fs: float) -> int:
    """Окно сглаживания в отсчётах: нечётное и не меньше 3.

    Центрированное окно без смещения фазы возможно только при нечётной длине.
    """
    samples = _samples(ms, fs)
    if samples % 2 == 0:
        samples += 1
    return max(3, samples)


def moving_average(data: np.ndarray, window: int) -> np.ndarray:
    """Центрированное скользящее среднее с усечённым окном на краях.

    ``y[i] = mean(x[max(0, i-half) .. min(n-1, i+half)])``, деление — на
    фактическое число доступных отсчётов. Нулями окно не дополняется: иначе на
    первых и последних ``half`` отсчётах появился бы ложный провал к нулю,
    который следующий ФВЧ превратил бы в краевой всплеск.

    Чётное окно уменьшается до ближайшего нечётного. Если сглаживать нечем
    (``window <= 1`` или ``window > n``), возвращается копия входа.
    """
    values = np.asarray(data, dtype=float)
    size = values.size
    if size == 0:
        return values.copy()
    if window <= 1 or window > size:
        return values.copy()

    effective = window - 1 if window % 2 == 0 else window
    if effective <= 1:
        return values.copy()

    half = effective // 2
    cumulative = np.concatenate(([0.0], np.cumsum(values)))
    indices = np.arange(size)
    left = np.maximum(0, indices - half)
    right = np.minimum(size - 1, indices + half)
    sums = cumulative[right + 1] - cumulative[left]
    counts = right - left + 1
    return sums / counts


def highpass_coefficients(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Коэффициенты ФВЧ Баттерворта 2-го порядка (билинейное преобразование).

    ``K = tan(pi*fc/fs)``, ``norm = 1/(1 + sqrt(2)*K + K^2)``;
    ``b = norm * [1, -2, 1]``, ``a = [1, 2*(K^2-1)*norm, (1 - sqrt(2)*K + K^2)*norm]``.
    """
    b, a = scipy_signal.butter(
        config.HIGHPASS_ORDER,
        config.HIGHPASS_CUTOFF_HZ,
        btype="high",
        fs=fs,
    )
    return b, a


def highpass_filter(data: np.ndarray, fs: float) -> np.ndarray:
    """ФВЧ Баттерворта с нулевой фазой (``filtfilt``, двойной проход).

    Двойной проход удваивает эффективный порядок (2 → 4), АЧХ возводится в
    квадрат, а фазовый набег взаимно уничтожается — вершина R не смещается.

    ``padlen`` берётся не меньше ``3 * fs``: полюс ФВЧ 0.5 Гц близок к
    единичной окружности, и при коротком паддинге на первых отсчётах остаётся
    переходный процесс, порождающий ложный R-пик.

    ``padtype="even"`` — отражение с реверсом без повтора крайнего отсчёта,
    ровно как в эталонной реализации (``reflectPad``). На эталонной записи
    такой паддинг даёт min −0.3829, max 0.9956, mean 0.0000, std 0.1722 —
    совпадение с §3.2 разбора в пределах допуска; при ``padtype="odd"``
    (значение scipy по умолчанию) среднее уезжает на −0.0101.
    """
    values = np.asarray(data, dtype=float)
    if values.size < 2:
        return values.copy()

    b, a = highpass_coefficients(fs)
    padding = max(
        config.FILTFILT_MIN_PADDING_SAMPLES,
        int(config.FILTFILT_PADDING_SECONDS * fs),
    )
    # padlen должен быть строго меньше длины сигнала.
    padding = min(padding, values.size - 1)
    return scipy_signal.filtfilt(b, a, values, padlen=padding, padtype="even")


# --- Детекция R-пиков --------------------------------------------------------


def _derivative_energy(data: np.ndarray) -> np.ndarray:
    """Энергия центральной производной ``((x[i+1] - x[i-1]) / 2)^2``.

    На краях массива производная нулевая — там нет второго соседа.
    """
    energy = np.zeros_like(data)
    if data.size >= 3:
        derivative = (data[2:] - data[:-2]) / 2.0
        energy[1:-1] = derivative * derivative
    return energy


def _sliding_max(data: np.ndarray, half: int) -> np.ndarray:
    """Максимум в скользящем окне ``[i-half, i+half]`` (края — nearest)."""
    if half <= 0:
        return data.copy()
    return ndimage.maximum_filter1d(data, size=2 * half + 1, mode="nearest")


def _refine_peak(data: np.ndarray, candidate: int, half: int) -> int:
    """Уточняет вершину R как ``argmax |y|`` в окне ±half вокруг кандидата.

    Модуль берётся потому, что полярность отведения не фиксирована.
    """
    start = max(0, candidate - half)
    stop = min(data.size - 1, candidate + half)
    segment = np.abs(data[start : stop + 1])
    return start + int(np.argmax(segment))


def detect_r_peaks(filtered: np.ndarray, fs: float) -> list[int]:
    """Индексы R-пиков (Pan-Tompkins-подобный детектор).

    Шаги:
    1. ``d[i] = (y[i+1] - y[i-1]) / 2`` — первая производная (не зависит от
       дрейфа изолинии);
    2. ``e[i] = d[i]^2`` — энергия;
    3. сглаживание ``e`` окном :data:`config.R_PEAK_ENERGY_WINDOW_MS` (80 мс):
       энергия комплекса собирается в один бугор, одиночный шумовой отсчёт
       перестаёт быть кандидатом;
    4. порог — 30 % от максимума энергии в локальном окне ±1 с, но не ниже 5 %
       от глобального максимума (глобальные 30 % отсекли бы слабые комплексы);
    5. локальные максимумы выше порога с рефрактерным периодом 200 мс;
    6. уточнение позиции как ``argmax |y|`` в окне ±40 мс.
    """
    values = np.asarray(filtered, dtype=float)
    size = values.size
    if size < 3:
        return []

    energy = _derivative_energy(values)
    smoothed = moving_average(energy, _odd_window_samples(config.R_PEAK_ENERGY_WINDOW_MS, fs))

    global_max = float(smoothed.max())
    if global_max <= 0.0:
        return []

    half_local = _samples(config.R_PEAK_LOCAL_WINDOW_SEC * MILLISECONDS_PER_SECOND, fs)
    local_max = _sliding_max(smoothed, half_local)
    floor = config.R_PEAK_GLOBAL_FLOOR_RATIO * global_max
    refractory = _samples(config.R_PEAK_REFRACTORY_MS, fs)
    guard = _samples(config.R_PEAK_EDGE_GUARD_MS, fs)
    refine_half = _samples(config.R_PEAK_REFINE_WINDOW_MS, fs)

    candidates: list[int] = []
    for i in range(1, size - 1):
        if i < guard or i > size - 1 - guard:
            continue
        value = float(smoothed[i])
        if value <= floor:
            continue
        if value <= config.R_PEAK_ENERGY_THRESHOLD_RATIO * float(local_max[i]):
            continue
        # Локальный максимум; плато допускается (сравнение нестрогое).
        if value < smoothed[i - 1] or value < smoothed[i + 1]:
            continue

        if candidates and i - candidates[-1] < refractory:
            # В пределах рефрактерного периода оставляем более сильный кандидат.
            if value > smoothed[candidates[-1]]:
                candidates[-1] = i
            continue
        candidates.append(i)

    refined = {_refine_peak(values, candidate, refine_half) for candidate in candidates}
    return sorted(refined)


# --- Границы QRS -------------------------------------------------------------


def _smoothed_abs_difference(data: np.ndarray, fs: float) -> np.ndarray:
    """Энергия первой разности ``|y[i] - y[i-1]|``, сглаженная окном 20 мс.

    Порог задан как доля от максимума, поэтому берётся ``|Δ|``, а не ``Δ²``:
    10 % от максимума ``Δ²`` — это 31.6 % от максимума амплитуды производной,
    границы съезжают внутрь и ширина занижается. Сглаживание обязательно:
    без него одиночный шумовой отсчёт рвёт проход и ширина «прыгает» в разы.
    """
    values = np.asarray(data, dtype=float)
    difference = np.abs(np.diff(values, prepend=values[0]))
    return moving_average(difference, _odd_window_samples(config.QRS_ENERGY_SMOOTHING_MS, fs))


def detect_qrs_boundaries(filtered: np.ndarray, r_peaks: list[int], fs: float) -> list[dict]:
    """Границы QRS-комплексов по падению энергии первой производной.

    Для каждого R-пика в окне ``[r - 120 мс, r + 160 мс]``:

    ``E[i] = |y[i] - y[i-1]|``, ``Es = MA(E, 20 мс)``,
    ``thr = 0.10 * max(Es в окне)``; от R идём влево и вправо, пока
    ``Es[i] >= thr``; первое падение — граница.

    «Мёртвая зона» у вершины R (там производная ≈ 0) пропускается: движение
    начинается с первого отсчёта выше порога, иначе onset и offset совпали бы
    с R и любой комплекс получал бы минимальную ширину.

    Инвариант ``onset < r <= offset`` гарантируется конструктивно; ширина
    ограничена физиологичными 40–200 мс.
    """
    values = np.asarray(filtered, dtype=float)
    size = values.size
    if size == 0 or not r_peaks:
        return []

    energy = _smoothed_abs_difference(values, fs)
    before = _samples(config.QRS_SEARCH_BEFORE_MS, fs)
    after = _samples(config.QRS_SEARCH_AFTER_MS, fs)
    min_width = _samples(config.MIN_QRS_WIDTH_MS, fs)
    max_width = max(min_width, _samples(config.MAX_QRS_WIDTH_MS, fs))

    complexes: list[dict] = []
    for peak in r_peaks:
        r_peak = min(max(int(peak), 0), size - 1)
        window_start = max(0, r_peak - before)
        window_end = min(size - 1, r_peak + after)

        threshold = config.QRS_ENERGY_THRESHOLD_RATIO * float(energy[window_start : window_end + 1].max())

        onset = window_start
        left = r_peak
        while left >= window_start and energy[left] < threshold:
            left -= 1
        if left >= window_start:
            onset = left
            index = left - 1
            while index >= window_start and energy[index] >= threshold:
                onset = index
                index -= 1

        offset = window_end
        right = r_peak
        while right <= window_end and energy[right] < threshold:
            right += 1
        if right <= window_end:
            while right <= window_end and energy[right] >= threshold:
                right += 1
            offset = min(right, window_end)

        # Ширина — интервал между границами: onset — последний отсчёт выше
        # порога слева, offset — первый отсчёт ниже порога справа. Для
        # 108–127 это 19 отсчётов = 76 мс, как в §3.2 разбора.
        width = offset - onset
        if width < min_width or width > max_width:
            target = min_width if width < min_width else max_width
            half = target // 2
            onset = max(0, r_peak - half)
            offset = min(size - 1, onset + target)
            onset = max(0, offset - target)

        if onset >= r_peak:
            onset = max(0, r_peak - 1)
        if offset < r_peak:
            offset = min(size - 1, r_peak)

        complexes.append(
            {
                "type": "QRS_COMPLEX",
                "r_peak_index": r_peak,
                "onset_index": onset,
                "offset_index": offset,
            }
        )
    return complexes


# --- Признаки ----------------------------------------------------------------


def _event_width_ms(onset: int, offset: int, fs: float) -> float:
    """Ширина комплекса как интервал между границами, мс.

    ``(offset - onset) / fs * 1000`` — эталонная формула §3.5 разбора: границы
    108–127 дают ровно 76 мс, средняя ширина — 88.67 мс. Вариант
    ``offset - onset + 1`` (число отсчётов внутри комплекса) даёт 92.67 мс и
    расходится с измеренными значениями задания.
    """
    return (offset - onset) / fs * MILLISECONDS_PER_SECOND


def extract_features(filtered: np.ndarray, complexes: list[dict], fs: float) -> dict:
    """Признаки варианта 4 по отфильтрованному сигналу и найденным QRS."""
    values = np.asarray(filtered, dtype=float)
    if values.size == 0:
        return {
            "mean_qrs_width_ms": None,
            "max_peak_amplitude": None,
            "mean_amplitude": None,
            "std_amplitude": None,
            "heart_rate_bpm": None,
            "r_peak_count": 0,
            "qrs_count": 0,
        }

    widths_ms = [_event_width_ms(item["onset_index"], item["offset_index"], fs) for item in complexes]
    mean_width = float(np.mean(widths_ms)) if widths_ms else None

    r_peaks = [item["r_peak_index"] for item in complexes]
    heart_rate = None
    if len(r_peaks) >= 2:
        rr_ms = np.diff(np.asarray(r_peaks, dtype=float)) / fs * MILLISECONDS_PER_SECOND
        mean_rr = float(rr_ms.mean())
        if mean_rr > 0.0:
            heart_rate = SECONDS_PER_MINUTE * MILLISECONDS_PER_SECOND / mean_rr

    qrs_count = sum(1 for item in complexes if item["onset_index"] < item["r_peak_index"] <= item["offset_index"])

    return {
        "mean_qrs_width_ms": mean_width,
        "max_peak_amplitude": float(values.max()),
        "mean_amplitude": float(values.mean()),
        "std_amplitude": float(values.std()),
        "heart_rate_bpm": heart_rate,
        "r_peak_count": len(r_peaks),
        "qrs_count": qrs_count,
    }


# --- Конвейер -----------------------------------------------------------------


def process_biosignal(raw_signal_list: list[float], fs: float = config.DEFAULT_SAMPLING_RATE_HZ) -> dict:
    """Центральная функция управления конвейером обработки.

    :param raw_signal_list: отсчёты исходного сигнала;
    :param fs: частота дискретизации, Гц;
    :returns: словарь с исходным и отфильтрованным сигналом, событиями и
        признаками (готов к сериализации в JSON).
    :raises ValueError: если сигнал короче двух отсчётов или ``fs <= 0``.
    """
    raw = np.asarray(raw_signal_list, dtype=float)
    if raw.size < 2:
        raise ValueError("Для обработки нужно минимум 2 отсчёта")
    if not math.isfinite(fs) or fs <= 0.0:
        raise ValueError("Частота дискретизации должна быть положительной")

    smoothed = moving_average(raw, config.MOVING_AVERAGE_WINDOW)
    filtered = highpass_filter(smoothed, fs)

    r_peaks = detect_r_peaks(filtered, fs)
    complexes = detect_qrs_boundaries(filtered, r_peaks, fs)
    features = extract_features(filtered, complexes, fs)

    events = [
        {
            "type": item["type"],
            "r_peak_index": item["r_peak_index"],
            "onset_index": item["onset_index"],
            "offset_index": item["offset_index"],
            "onset_time_ms": item["onset_index"] / fs * MILLISECONDS_PER_SECOND,
            "offset_time_ms": item["offset_index"] / fs * MILLISECONDS_PER_SECOND,
            "width_ms": _event_width_ms(item["onset_index"], item["offset_index"], fs),
        }
        for item in complexes
    ]

    return {
        "raw_signal": raw.tolist(),
        "filtered_signal": filtered.tolist(),
        "detected_events": events,
        "calculated_features": features,
    }
