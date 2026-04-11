"""Tests for the canonical schema and CSV I/O.

This file is the contract enforcement for the project. If something here
breaks, downstream modules cannot be trusted.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from vera.io_csv import (
    SchemaError,
    extract_feature_matrix,
    extract_labels,
    extract_leds,
    extract_lif,
    extract_spectra,
    read_measurements_csv,
    validate_dataframe,
    write_measurements_csv,
)
from vera.schema import (
    ALL_COLUMNS,
    LED_COLS,
    LIF_COL,
    MINERAL_CLASSES,
    N_FEATURES_TOTAL,
    N_LED,
    N_SPEC,
    N_SWIR,
    SPEC_COLS,
    SPEC_LAMBDA_MAX_NM,
    SPEC_LAMBDA_MIN_NM,
    SWIR_COLS,
    WAVELENGTHS,
    Measurement,
)


# ---------------------------------------------------------------------------
# Constants / shape contract
# ---------------------------------------------------------------------------


def test_constants_shape():
    assert N_SPEC == 288
    assert N_LED == 12
    assert N_FEATURES_TOTAL == 288 + 2 + 12 + 1  # spec + swir + led + lif = 303
    assert len(SPEC_COLS) == N_SPEC
    assert len(LED_COLS) == N_LED
    # 8 metadata + 288 spec + 2 swir + 12 LED + 1 LIF = 311
    assert len(ALL_COLUMNS) == 8 + 288 + 2 + 12 + 1
    assert len(set(ALL_COLUMNS)) == len(ALL_COLUMNS), "duplicate column names"


def test_wavelength_grid_endpoints_and_monotonic():
    assert WAVELENGTHS.shape == (N_SPEC,)
    assert WAVELENGTHS[0] == pytest.approx(SPEC_LAMBDA_MIN_NM)
    assert WAVELENGTHS[-1] == pytest.approx(SPEC_LAMBDA_MAX_NM)
    assert np.all(np.diff(WAVELENGTHS) > 0)
    # ~1.78 nm/px
    step = (SPEC_LAMBDA_MAX_NM - SPEC_LAMBDA_MIN_NM) / (N_SPEC - 1)
    assert np.allclose(np.diff(WAVELENGTHS), step)


def test_class_label_space():
    assert len(MINERAL_CLASSES) == 6
    assert "ilmenite_rich" in MINERAL_CLASSES
    assert "glass_agglutinate" in MINERAL_CLASSES
    assert "mixed" in MINERAL_CLASSES


# ---------------------------------------------------------------------------
# Pydantic Measurement model
# ---------------------------------------------------------------------------


def _good_measurement(**overrides) -> Measurement:
    base = dict(
        sample_id="S001",
        measurement_id="M001",
        timestamp="2026-04-07T16:00:00Z",
        mineral_class="olivine_rich",
        ilmenite_fraction=0.05,
        integration_time_ms=200,
        ambient_temp_c=21.5,
        packing_density="medium",
        spec=[0.5] * N_SPEC,
        swir=[0.4, 0.35],
        led=[0.4] * N_LED,
        lif_450lp=0.3,
    )
    base.update(overrides)
    return Measurement(**base)


def test_measurement_round_trip_to_row_and_back():
    m = _good_measurement()
    row = m.to_row()
    # to_row() emits ALL_COLUMNS plus sensor_mode and SWIR columns
    expected_keys = set(ALL_COLUMNS) | {"sensor_mode"}
    assert set(row.keys()) == expected_keys
    m2 = Measurement.from_row(row)
    assert m2.sample_id == m.sample_id
    assert m2.spec == m.spec
    assert m2.led == m.led
    assert m2.lif_450lp == m.lif_450lp
    assert m2.mineral_class == m.mineral_class
    assert m2.sensor_mode == "full"


def test_measurement_rejects_bad_class():
    with pytest.raises(Exception):
        _good_measurement(mineral_class="foo")


def test_measurement_rejects_bad_packing():
    with pytest.raises(Exception):
        _good_measurement(packing_density="hard")


def test_measurement_rejects_ilmenite_out_of_range():
    with pytest.raises(Exception):
        _good_measurement(ilmenite_fraction=1.2)
    with pytest.raises(Exception):
        _good_measurement(ilmenite_fraction=-0.01)


def test_measurement_rejects_wrong_spec_length():
    with pytest.raises(Exception):
        _good_measurement(spec=[0.5] * (N_SPEC - 1))


def test_measurement_rejects_wrong_led_length():
    with pytest.raises(Exception):
        _good_measurement(led=[0.5] * (N_LED + 1))


def test_measurement_rejects_nonfinite_spec():
    bad = [0.5] * N_SPEC
    bad[0] = float("nan")
    with pytest.raises(Exception):
        _good_measurement(spec=bad)


def test_measurement_rejects_nonpositive_integration_time():
    with pytest.raises(Exception):
        _good_measurement(integration_time_ms=0)


# ---------------------------------------------------------------------------
# DataFrame validation
# ---------------------------------------------------------------------------


def _good_df(n: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for i in range(n):
        m = _good_measurement(
            sample_id=f"S{i:03d}",
            measurement_id=f"M{i:03d}",
            spec=list(rng.uniform(0.1, 0.9, size=N_SPEC).astype(float)),
            swir=list(rng.uniform(0.1, 0.9, size=N_SWIR).astype(float)),
            led=list(rng.uniform(0.1, 0.9, size=N_LED).astype(float)),
            lif_450lp=float(rng.uniform(0.1, 0.9)),
        )
        rows.append(m.to_row())
    # Use ALL_COLUMNS order
    cols = list(ALL_COLUMNS)
    return pd.DataFrame(rows)[cols]


def test_validate_good_dataframe_passes():
    df = _good_df(5)
    validate_dataframe(df)  # must not raise


def test_validate_rejects_missing_column():
    df = _good_df(2).drop(columns=[SPEC_COLS[0]])
    with pytest.raises(SchemaError):
        validate_dataframe(df)


def test_validate_rejects_extra_column():
    df = _good_df(2)
    df["mystery"] = 1.0
    with pytest.raises(SchemaError):
        validate_dataframe(df)


def test_validate_rejects_bad_class_in_df():
    df = _good_df(2)
    df.loc[0, "mineral_class"] = "not_a_class"
    with pytest.raises(SchemaError):
        validate_dataframe(df)


def test_validate_rejects_nan_spec():
    df = _good_df(2)
    df.loc[0, SPEC_COLS[10]] = np.nan
    with pytest.raises(SchemaError):
        validate_dataframe(df)


def test_validate_rejects_ilmenite_out_of_range():
    df = _good_df(2)
    df.loc[0, "ilmenite_fraction"] = 1.5
    with pytest.raises(SchemaError):
        validate_dataframe(df)


# ---------------------------------------------------------------------------
# CSV round-trip
# ---------------------------------------------------------------------------


def test_csv_round_trip_preserves_values(tmp_path: Path):
    df = _good_df(7)
    out = tmp_path / "round.csv"
    write_measurements_csv(df, out)
    df2 = read_measurements_csv(out)
    assert list(df2.columns) == list(ALL_COLUMNS)
    pd.testing.assert_frame_equal(
        df.reset_index(drop=True),
        df2.reset_index(drop=True),
        check_dtype=False,
    )


def test_csv_write_from_measurement_iterable(tmp_path: Path):
    measurements = [
        _good_measurement(sample_id=f"S{i:03d}", measurement_id=f"M{i:03d}")
        for i in range(4)
    ]
    out = tmp_path / "iter.csv"
    write_measurements_csv(measurements, out)
    df = read_measurements_csv(out)
    assert len(df) == 4
    assert df["sample_id"].tolist() == ["S000", "S001", "S002", "S003"]


def test_csv_read_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_measurements_csv(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def test_extract_blocks_have_expected_shapes():
    df = _good_df(6)
    spec = extract_spectra(df)
    led = extract_leds(df)
    lif = extract_lif(df)
    feats = extract_feature_matrix(df)
    assert spec.shape == (6, N_SPEC)
    assert led.shape == (6, N_LED)
    assert lif.shape == (6,)
    assert feats.shape == (6, N_FEATURES_TOTAL)  # 303 = 288 + 2 + 12 + 1
    # feature matrix is [spec | swir | led | lif]
    np.testing.assert_array_equal(feats[:, :N_SPEC], spec)
    np.testing.assert_array_equal(feats[:, N_SPEC + N_SWIR : N_SPEC + N_SWIR + N_LED], led)
    np.testing.assert_array_equal(feats[:, -1], lif)


def test_extract_labels_returns_indices_and_fractions():
    df = _good_df(4)
    df.loc[0, "mineral_class"] = "ilmenite_rich"
    df.loc[0, "ilmenite_fraction"] = 0.9
    idx, ilm = extract_labels(df)
    assert idx.dtype == np.int64
    assert ilm.dtype == np.float64
    assert idx[0] == 0  # ilmenite_rich is class 0
    assert ilm[0] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# AS7265x dual-sensor support (v1.1)
# ---------------------------------------------------------------------------


from vera.schema import (
    AS7265X_BANDS,
    AS7265X_COLS,
    N_AS7265X,
    SCHEMA_VERSION,
    columns_for_mode,
    get_feature_count,
)


def test_as7265x_bands_shape_and_endpoints():
    assert len(AS7265X_BANDS) == 18
    assert AS7265X_BANDS[0] == 410
    assert AS7265X_BANDS[-1] == 940


def test_n_as7265x_constant():
    assert N_AS7265X == 18


def test_as7265x_cols_format():
    assert AS7265X_COLS[0] == "as7_410"
    assert AS7265X_COLS[1] == "as7_435"
    assert AS7265X_COLS[-1] == "as7_940"
    assert len(AS7265X_COLS) == 18
    for col, band in zip(AS7265X_COLS, AS7265X_BANDS):
        assert col == f"as7_{band}"


def test_get_feature_count_full():
    assert get_feature_count("full") == 303  # 288 + 2 + 12 + 1


def test_get_feature_count_multispectral():
    assert get_feature_count("multispectral") == 33  # 18 + 2 + 12 + 1


def test_get_feature_count_combined():
    assert get_feature_count("combined") == 321  # 288 + 18 + 2 + 12 + 1


def test_get_feature_count_invalid_mode():
    with pytest.raises(ValueError, match="Unknown sensor_mode"):
        get_feature_count("bogus")


def test_schema_version_is_1_2_0():
    assert SCHEMA_VERSION == "1.2.0"


def test_measurement_with_as7265x_none_validates():
    """Backward compat: as7265x=None must be accepted."""
    m = _good_measurement(as7265x=None)
    assert m.as7265x is None


def test_measurement_rejects_wrong_as7265x_length():
    with pytest.raises(Exception):
        _good_measurement(as7265x=[0.5] * 10)


def test_measurement_with_correct_as7265x_validates():
    m = _good_measurement(as7265x=[0.5] * 18)
    assert len(m.as7265x) == 18


def test_measurement_to_row_includes_sensor_mode():
    m = _good_measurement()
    row = m.to_row()
    assert "sensor_mode" in row
    assert row["sensor_mode"] == "full"


def test_columns_for_mode_full():
    cols = columns_for_mode("full")
    # 8 meta + sensor_mode + 288 spec + 2 swir + 12 LED + 1 LIF = 312
    assert len(cols) == 8 + 1 + N_SPEC + N_SWIR + N_LED + 1


def test_columns_for_mode_multispectral():
    cols = columns_for_mode("multispectral")
    # 8 meta + sensor_mode + 18 AS7265x + 2 swir + 12 LED + 1 LIF = 42
    assert len(cols) == 8 + 1 + N_AS7265X + N_SWIR + N_LED + 1


def test_columns_for_mode_combined():
    cols = columns_for_mode("combined")
    # 8 meta + sensor_mode + 288 spec + 18 AS7265x + 2 swir + 12 LED + 1 LIF = 330
    assert len(cols) == 8 + 1 + N_SPEC + N_AS7265X + N_SWIR + N_LED + 1


def test_legacy_309_column_df_validates():
    """Old v1.0 309-column DataFrames without sensor_mode, AS7265x,
    or SWIR columns must still validate (backward compatibility)."""
    df = _good_df(3)
    # Strip SWIR columns to simulate a v1.0 DataFrame
    df = df.drop(columns=[c for c in SWIR_COLS if c in df.columns])
    # Ensure no AS7265x cols exist
    for c in AS7265X_COLS:
        assert c not in df.columns
    assert "sensor_mode" not in df.columns
    validate_dataframe(df)  # must not raise
