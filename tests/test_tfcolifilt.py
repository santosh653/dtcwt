import os

import pytest
from dtcwt.tf.lowlevel import _HAVE_TF as HAVE_TF
pytest.mark.skipif(not HAVE_TF, reason="Tensorflow not present")

import numpy as np
import tensorflow as tf
from dtcwt.tf.lowlevel import colifilt
from dtcwt.coeffs import qshift
from dtcwt.numpy.lowlevel import colifilt as np_colifilt

from pytest import raises

import tests.datasets as datasets

def setup():
    global mandrill, mandrill_t
    mandrill = datasets.mandrill()
    mandrill_t = tf.expand_dims(tf.constant(mandrill, dtype=tf.float32),axis=0)

def test_mandrill_loaded():
    assert mandrill.shape == (512, 512)
    assert mandrill.min() >= 0
    assert mandrill.max() <= 1
    assert mandrill.dtype == np.float32
    assert mandrill_t.get_shape() == (1, 512, 512)

def test_odd_filter():
    with raises(ValueError):
        colifilt(mandrill_t, (-1,2,-1), (-1,2,1))

def test_different_size_h():
    with raises(ValueError):
        colifilt(mandrill_t, (-1,2,1), (-0.5,-1,2,-1,0.5))

def test_zero_input():
    Y = colifilt(mandrill_t, (-1,1), (1,-1))
    with tf.Session() as sess:
        y = sess.run(Y, {mandrill_t : [np.zeros_like(mandrill)]})[0]
    assert np.all(y[:0] == 0)

def test_bad_input_size():
    with raises(ValueError):
        colifilt(mandrill_t[:,:511,:], (-1,1), (1,-1))

def test_good_input_size():
    colifilt(mandrill_t[:,:,:511], (-1,1), (1,-1))

def test_output_size():
    Y = colifilt(mandrill_t, (-1,1), (1,-1))
    assert Y.shape[1:] == (mandrill.shape[0]*2, mandrill.shape[1])

def test_non_orthogonal_input():
    Y = colifilt(mandrill_t, (1,1), (1,1))
    assert Y.shape[1:] == (mandrill.shape[0]*2, mandrill.shape[1])

def test_output_size_non_mult_4():
    Y = colifilt(mandrill_t, (-1,0,0,1), (1,0,0,-1))
    assert Y.shape[1:] == (mandrill.shape[0]*2, mandrill.shape[1])

def test_non_orthogonal_input_non_mult_4():
    Y = colifilt(mandrill_t, (1,0,0,1), (1,0,0,1))
    assert Y.shape[1:] == (mandrill.shape[0]*2, mandrill.shape[1])

@pytest.mark.skip(reason='Cant pad by more than half the dimension of the input')
def test_equal_small_in():
    ha = qshift('qshift_b')[0]
    hb = qshift('qshift_b')[1]
    im = mandrill[0:4,0:4]
    im_t = tf.expand_dims(tf.constant(im, tf.float32), axis=0)
    ref = np_coldfilt(im, ha, hb)
    y_op = coldfilt(im_t, ha, hb)
    with tf.Session() as sess:
        y = sess.run(y_op)
    np.testing.assert_array_almost_equal(y[0], ref, decimal=4)

def test_equal_numpy_qshift1():
    ha = qshift('qshift_c')[0]
    hb = qshift('qshift_c')[1]
    ref = np_colifilt(mandrill, ha, hb)
    y_op = colifilt(mandrill_t, ha, hb)
    with tf.Session() as sess:
        y = sess.run(y_op)
    np.testing.assert_array_almost_equal(y[0], ref, decimal=4)

def test_equal_numpy_qshift2():
    ha = qshift('qshift_c')[0]
    hb = qshift('qshift_c')[1]
    im = mandrill[:508, :502]
    im_t = tf.expand_dims(tf.constant(im, tf.float32), axis=0)
    ref = np_colifilt(im, ha, hb)
    y_op = colifilt(im_t, ha, hb)
    with tf.Session() as sess:
        y = sess.run(y_op)
    np.testing.assert_array_almost_equal(y[0], ref, decimal=4)

# vim:sw=4:sts=4:et
