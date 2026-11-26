import pytest
from cinemaready.pipeline import open_fixture
from cinemaready.show_handoffs.service import load_samples
from cinemaready.turnover_calendar.service import build_windows
from cinemaready.hall_signature.service import fit_features, transform_windows
from cinemaready.cleanup_trend.service import fit_model, predict


@pytest.fixture
def observation():
    return dict(open_fixture()['records'][0])


@pytest.fixture(scope='session')
def fitted_vectors():
    sample = open_fixture()
    intake = load_samples(sample['records'],sample['as_of'])
    windows = build_windows(intake.entries)
    reference = fit_features(windows.train)
    prepared = transform_windows(windows,reference)
    return prepared.train, prepared.live, reference.fingerprint


@pytest.fixture(scope='session')
def prediction(fitted_vectors):
    train, live, stamp = fitted_vectors
    anchor = fit_model(train,stamp)
    inferred = predict(anchor,live[:1],stamp)[0]
    return inferred
