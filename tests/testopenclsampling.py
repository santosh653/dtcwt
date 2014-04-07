import dtcwt
import dtcwt.opencl.sampling
import dtcwt.numpy.sampling as npsample
from dtcwt.sampling import rescale, sample

from .util import skip_if_no_cl

import numpy as np

@skip_if_no_cl
def setup():
    dtcwt.push_backend('opencl')

@skip_if_no_cl
def teardown():
    dtcwt.pop_backend()

@skip_if_no_cl
def test_correct_backend():
    # Test that the correct backend will be used for sampling
    assert dtcwt._sampling is dtcwt.opencl.sampling

@skip_if_no_cl
def test_rescale_pixel_centre():
    # Create random 100x120 image
    X = np.random.rand(100,120).astype(np.float32)

    # Re size up
    Xrs = rescale(X, (200, 240), 'nearest')
    assert Xrs.shape == (200, 240)

    # Output should be 4x4 blocks identical to original
    for dx, dy in ((0,0), (0,1), (1,0), (1,1)):
        Y = Xrs[dx::2,dy::2]
        assert np.all(np.abs(X-Y) < 1e-8)

@skip_if_no_cl
def test_rescale_nearest():
    # Create random 100x120 image
    X = np.random.rand(100,120).astype(np.float32)

    # Re size up
    Xrs = rescale(X, (200, 240), 'nearest')
    assert Xrs.shape == (200, 240)

    # And down
    Xrecon = rescale(Xrs, X.shape, 'nearest')
    assert Xrecon.shape == X.shape

    # Got back roughly the same thing
    assert np.all(np.abs(X-Xrecon) < 1e-8)

@skip_if_no_cl
def test_nearest_against_numpy_2d():
    # Create random 100x120 image
    X = np.random.rand(100,120).astype(np.float32)

    # Generate random sampling co-ords
    sample_shape = (320, 240)
    ys = (4 * np.random.rand(*sample_shape) - 2) * X.shape[0]
    xs = (4 * np.random.rand(*sample_shape) - 2) * X.shape[1]

    # Sample
    Xsampled = sample(X, xs, ys, 'nearest')
    assert Xsampled.shape == sample_shape

    # Sample via numpy
    Xsampled_np = npsample.sample_nearest(X, xs, ys)
    assert Xsampled_np.shape == Xsampled.shape

    # Sampling should agree to within tolerance
    assert np.all(np.abs(Xsampled-Xsampled_np) < 1e-6)

@skip_if_no_cl
def test_nearest_against_numpy_3d():
    # Create random 100x120x4 image
    X = np.random.rand(100,120,4)

    # Generate random sampling co-ords
    sample_shape = (320, 240)
    ys = (4 * np.random.rand(*sample_shape) - 2) * X.shape[0]
    xs = (4 * np.random.rand(*sample_shape) - 2) * X.shape[1]

    # Sample
    Xsampled = sample(X, xs, ys, 'nearest')
    assert Xsampled.shape == sample_shape + X.shape[2:]

    # Sample via numpy
    Xsampled_np = npsample.sample_nearest(X, xs, ys)
    assert Xsampled_np.shape == Xsampled.shape

    # Sampling should agree to within tolerance
    assert np.all(np.abs(Xsampled-Xsampled_np) < 1e-6)

@skip_if_no_cl
def test_bilinear_against_numpy_2d():
    # Create random 100x120 image
    X = np.random.rand(100,120).astype(np.float32)

    # Generate random sampling co-ords
    sample_shape = (320, 240)
    ys = (4 * np.random.rand(*sample_shape) - 2) * X.shape[0]
    xs = (4 * np.random.rand(*sample_shape) - 2) * X.shape[1]

    # Sample
    Xsampled = sample(X, xs, ys, 'bilinear')
    assert Xsampled.shape == sample_shape

    # Sample via numpy
    Xsampled_np = npsample.sample_bilinear(X, xs, ys)
    assert Xsampled_np.shape == Xsampled.shape

    # Sampling should agree to within tolerance
    assert np.all(np.abs(Xsampled-Xsampled_np) < 1e-4)

@skip_if_no_cl
def test_bilinear_against_numpy_3d():
    # Create random 100x120x4 image
    X = np.random.rand(100,120,4)

    # Generate random sampling co-ords
    sample_shape = (320, 240)
    ys = (4 * np.random.rand(*sample_shape) - 2) * X.shape[0]
    xs = (4 * np.random.rand(*sample_shape) - 2) * X.shape[1]

    # Sample
    Xsampled = sample(X, xs, ys, 'bilinear')
    assert Xsampled.shape == sample_shape + X.shape[2:]

    # Sample via numpy
    Xsampled_np = npsample.sample_bilinear(X, xs, ys)
    assert Xsampled_np.shape == Xsampled.shape

    # Sampling should agree to within tolerance
    assert np.all(np.abs(Xsampled-Xsampled_np) < 1e-4)
