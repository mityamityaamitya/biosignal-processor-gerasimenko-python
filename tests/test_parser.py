"""Проверка разбора входного файла и кодов ошибок."""

from __future__ import annotations

import unittest

import config
from biosignal.errors import SignalInputError
from biosignal.io import AnalysisRequestValidator, SignalTextParser


class SignalTextParserTest(unittest.TestCase):
    """Разбор чисел, выбор колонки и ошибки формата."""

    def setUp(self) -> None:
        self.parser = SignalTextParser()

    def test_single_column(self) -> None:
        rows = self.parser.parse(b"-0.570\n-0.560\n0.100\n")
        self.assertEqual(rows, [[-0.570], [-0.560], [0.100]])

    def test_several_columns_and_separators(self) -> None:
        rows = self.parser.parse(b"0.000 1.5\n0.004\t2.5\n0.008;3.5\n")
        self.assertEqual(self.parser.extract_column(rows, 1), [1.5, 2.5, 3.5])

    def test_empty_file(self) -> None:
        with self.assertRaises(SignalInputError) as context:
            self.parser.parse(b"   \n\n")
        self.assertEqual(context.exception.code, config.ERROR_EMPTY_FILE)

    def test_bad_token(self) -> None:
        with self.assertRaises(SignalInputError) as context:
            self.parser.parse(b"1.0\nabc\n")
        self.assertEqual(context.exception.code, config.ERROR_PARSE_ERROR)

    def test_missing_column(self) -> None:
        rows = self.parser.parse(b"1.0\n2.0\n")
        with self.assertRaises(SignalInputError) as context:
            self.parser.extract_column(rows, 3)
        self.assertEqual(context.exception.code, config.ERROR_INVALID_COLUMN)


class AnalysisRequestValidatorTest(unittest.TestCase):
    """Коды ошибок валидации параметров запроса."""

    def setUp(self) -> None:
        self.validator = AnalysisRequestValidator()

    def test_extension(self) -> None:
        with self.assertRaises(SignalInputError) as context:
            self.validator.validate_filename("signal.dat")
        self.assertEqual(context.exception.code, config.ERROR_INVALID_FILE_FORMAT)

    def test_sampling_rate(self) -> None:
        with self.assertRaises(SignalInputError) as context:
            self.validator.validate_sampling_rate(0)
        self.assertEqual(context.exception.code, config.ERROR_INVALID_SAMPLING_RATE)

    def test_signal_length(self) -> None:
        with self.assertRaises(SignalInputError) as context:
            self.validator.validate_signal_length(5)
        self.assertEqual(context.exception.code, config.ERROR_SIGNAL_TOO_SHORT)


if __name__ == "__main__":
    unittest.main()
