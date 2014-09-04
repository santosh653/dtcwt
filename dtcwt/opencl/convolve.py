"""
Convolution
===========

Low-level convolution routines for OpenCL.
"""

import os
import numpy as np
import dtcwt.coeffs

try:
    import pyopencl as cl
    import pyopencl.array as cla
    _HAVE_OPENCL = True
except ImportError:
    _HAVE_OPENCL = False

_PROGRAM_PATH=os.path.join(os.path.dirname(__file__), 'convolve.cl')
_DEFAULT_CHUNK_SIZE=32

def _array_to_spec(array):
    data = array.base_data
    offset = np.int32(array.offset // array.dtype.itemsize)
    strides = cla.vec.make_int2(*np.divide(array.strides, array.dtype.itemsize))
    shape = cla.vec.make_int2(*array.shape)
    return data, offset, strides, shape

@np.vectorize
def _ceil_multiple(x, m):
        return m * ((x+(m-1)) // m)

def _global_and_local_size(output_shape, chunk_size):
    local_size = tuple(int(x) for x in (chunk_size, chunk_size))
    global_size = tuple(int(x) for x in _ceil_multiple(output_shape[:2], local_size))
    return global_size, local_size

def _good_chunk_size_for_queue(queue):
    # By default use _DEFAULT_CHUNK_SIZE for chunk size but reduce it if
    # the device does not support a work group that big.
    chunk_size = _DEFAULT_CHUNK_SIZE
    if chunk_size * chunk_size > queue.device.max_work_group_size:
        # Set chunk size to largest which will fit
        chunk_size = int(np.floor(np.sqrt(queue.device.max_work_group_size)))
    return chunk_size

def _build_program(queue, kernel_half_width, chunk_size):
    """Load and build the convolution kernel program for a specified kernel
    half width and chunk size. Returns a cl.Program object on success.

    """
    constants = {
        'KERNEL_HALF_WIDTH': kernel_half_width,
        'CHUNK_SIZE': chunk_size,
    }
    options = list('-D{0}={1}'.format(k,v) for k,v in constants.items())
    program = cl.Program(queue.context, open(_PROGRAM_PATH).read())
    program.build(options)
    return program

def _write_input_pixel_test_image(queue, output_array, input_offset, input_shape, wait_for=None):
    chunk_size = _good_chunk_size_for_queue(queue)
    program = _build_program(queue, 0, chunk_size)
    out_data, out_offset, out_strides, out_shape = _array_to_spec(output_array)
    global_size, local_size = _global_and_local_size(output_array.shape, chunk_size)
    return program.test_edge_reflect(queue, global_size, local_size,
            cla.vec.make_int2(*input_offset), cla.vec.make_int2(*input_shape),
            out_data, out_offset, out_strides, out_shape, wait_for=wait_for)

class Convolution1D(object):
    """A 1d convolution on the OpenCL device.

    A convolution is planned for a particular set of kernel coefficients and a
    particular input dtype.

    *kernel_coeffs* is a 1d vector of :py:class:`pyopencl.array.vec.float2`
    which stores the lowpass kernel coefficients in the 'x' field and the
    highpass coefficients in the 'y' field.

    *input_dtype* specifies the dtype of the input array. If this is a scalar
    type then the output array dtype will be a 2-component vector where the 'x'
    field corresponds to convolving the input with the lowpass kernel and the
    'y' field corresponds to convolving the input with the highpass kernel. If
    *input_dtype* is a 2 component vector then the output will have four
    components. The 'xy' fields corresponding to the low- and highpass
    convolution of the 'x' field of the input and the 'zw' fields corresponds
    to the low- and highpass convolution of the 'y' field of the input.

    The convolution expects a 2D array as input and will convolve along the
    first dimension.

    .. py:attribute:: input_dtype

        Read-only. The expected dtype of the input array.

    .. py:attribute:: output_dtype

        Read-only. The output dtype resulting from :py:attr:`input_dtype`.

    """

    def __init__(self, queue, kernel_coeffs, input_dtype):
        if kernel_coeffs.dtype != cla.vec.float2 or len(kernel_coeffs.shape) != 1:
            raise ValueError('Kernel coefficients must be a 1d vector of float2')
        if kernel_coeffs.shape[0] % 2 != 1:
            raise ValueError('Kernel coefficients vector must have odd length')

        # Remember which queue we work on
        self._queue = queue

        # Copy kernel to device if necessary
        self._kernel_coeffs = cla.to_device(queue, kernel_coeffs)

        # Compute chunk size, kernel half width and build device program
        self._chunk_size = _good_chunk_size_for_queue(queue)
        self._kernel_half_width = (kernel_coeffs.shape[0] - 1)>>1
        self._program = _build_program(queue, self._kernel_half_width, self._chunk_size)

        # Fetch kernels
        self.input_dtype = input_dtype
        if input_dtype == np.float32:
            self._convolve = self._program.convolve_scalar
            self.output_dtype = cla.vec.float2
        elif input_dtype == cla.vec.float2:
            self._convolve = self._program.convolve_vec2
            self.output_dtype = cla.vec.float4
        else:
            raise ValueError('an input dtype of "{0}" is not supported'.format(input_dtype))

    def __call__(self, *args, **kwargs):
        return self.convolve(*args, **kwargs)

    def convolve(self, input_array, output_array, wait_for=None):
        """Perform the convolution. *input_array* and *output_array* should be
        instances of :py:class:`pyopencl.array.Array` with the correct dtypes
        as specified in :py:attr:`input_dtype` and :py:attr:`output_dtype`.

        *wait_for* is either *None* or a sequence of OpenCL evens to wait for
        before performing the convolution.

        Returns an OpenCL event which represents the convolution succeeding.

        This method can also be accessed via the :py:meth:`__call__` method in
        order to treat the convolution as a callable.

        """
        # Check dtypes
        if input_array.dtype != self.input_dtype:
            raise ValueError('Input array has wrong dtype "{0}". Was expecting "{1}"'.format(
                self.input_dtype, input_array.dtype))
        if input_array.dtype != self.input_dtype:
            raise ValueError('Output array has wrong dtype "{0}". Was expecting "{1}"'.format(
                self.input_dtype, input_array.dtype))

        in_data, in_offset, in_strides, in_shape = _array_to_spec(input_array)
        out_data, out_offset, out_strides, out_shape = _array_to_spec(output_array)
        global_size, local_size = _global_and_local_size(output_array.shape, self._chunk_size)
        return self._convolve(self._queue, global_size, local_size,
                self._kernel_coeffs.data,
                in_data, in_offset, in_strides, in_shape,
                out_data, out_offset, out_strides, out_shape, wait_for=wait_for)

class Convolution2D(object):
    """A 2-dimensional convolution."""

    def __init__(self, queue, kernel_coeffs):
        if kernel_coeffs.dtype != cla.vec.float2 or len(kernel_coeffs.shape) != 1:
            raise ValueError('Kernel coefficients must be a 1d vector of float2')
        if kernel_coeffs.shape[0] % 2 != 1:
            raise ValueError('Kernel coefficients vector must have odd length')

        # Remember which queue we work on
        self._queue = queue

        # Set input and output dtypes we work with
        self.input_dtype = np.float32
        self.workspace_dtype = cla.vec.float2
        self.output_dtype = cla.vec.float4

        # Prepare convolutions
        self._convolution1 = Convolution1D(queue, kernel_coeffs, self.input_dtype)
        self._convolution2 = Convolution1D(queue, kernel_coeffs, self.workspace_dtype)

    def workspace_size_for_input(self, input_array):
        if input_array.dtype != self.input_dtype:
            raise ValueError('Input array has invalid dtype {0}. Expected {1}'.format(
                input_array.dtype, self.input_dtype))
        return int(np.product(input_array.shape) * input_array.dtype.itemsize * 2)

    def convolve(self, input_array, output_array, workspace_buffer, wait_for=None):
        if input_array.dtype != self.input_dtype:
            raise ValueError('Input array has dtype {0}. Expected {1}'.format(
                input_array.dtype, self.input_dtype))
        if output_array.dtype != self.output_dtype:
            raise ValueError('Output array has dtype {0}. Expected {1}'.format(
                output_array.dtype, self.output_dtype))
        if len(input_array.shape) != 2:
            raise ValueError('Input array must be 2 dimensional')
        if len(output_array.shape) != 2:
            raise ValueError('Output array must be 2 dimensional')
        req_workspace_size = self.workspace_size_for_input(input_array)
        if workspace_buffer.size < req_workspace_size:
            raise ValueError('Workspace size {0} is too small. At least {1} is required'.format(
                workspace_buffer.size, req_workspace_size))

        workspace_array = cla.Array(
            self._queue, input_array.shape,
            self.workspace_dtype, data=workspace_buffer
        )
        evt1 = self._convolution1(input_array, workspace_array, wait_for=wait_for)

        # Re-interpret workspace and output as transposed versions of themselves
        workspace_array = cla.Array(
            self._queue, workspace_array.shape[::-1],
            workspace_array.dtype, data=workspace_buffer,
            strides=workspace_array.strides[::-1]
        )
        output_array = cla.Array(
            self._queue, output_array.shape[::-1],
            output_array.dtype,
            data=output_array.base_data, offset=output_array.offset,
            strides=output_array.strides[::-1]
        )

        # Perform second convolution
        return self._convolution2(workspace_array, output_array, wait_for=[evt1])

    def __call__(self, *args, **kwargs):
        return self.convolve(*args, **kwargs)
