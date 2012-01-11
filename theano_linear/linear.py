"""
XXX
"""
import sys
import copy
import numpy
import theano
import theano.tensor as tensor

# XXX: import this function to utils
import pylearn.io.image_tiling

prod = numpy.prod

def dot(x, y):
    """Return the linear transformation of `y` by `x` or `x` by `y` when one
    or both of `x` and `y` is a LinearTransform instance
    """
    if isinstance(x, LinearTransform):
        return x.rmul(y)
    elif isinstance(y, LinearTransform):
        return y.lmul(x)
    else:
        return theano.dot(x,y)


def dot_shape_from_shape(x, y):
    """Compute `dot(x, y).shape` from the shape of the non-LinearTransform
    """
    if isinstance(x, LinearTransform):
        return x.col_shape() + x.split_right_shape(y)[1]
    elif isinstance(y, LinearTransform):
        return y.split_left_shape(x)[0] + y.row_shape()
    else:
        raise TypeError('One of x or y should be a LinearTransform')


def dot_shape(x, y):
    """Return the linear transformation of `y` by `x` or `x` by `y` when one
    or both of `x` and `y` is a LinearTransform instance
    """
    if isinstance(x, LinearTransform):
        return dot_shape_from_shape(x, tuple(y.shape))
    elif isinstance(y, LinearTransform):
        return dot_shape_from_shape(tuple(x.shape), y)
    else:
        raise TypeError('One of x or y should be a LinearTransform')


class LinearTransform(object):
    """

    Attributes:
    _params: a list of theano shared variables
        that parametrize the linear transformation

    """
    def __init__(self, params):
        self.set_params(params)

    def set_params(self, params):
        self._params = list(params)

    def params(self):
        return list(self._params)

    def __str__(self):
        return self.__class__.__name__ +'{}'

    # N.B. Don't implement __mul__ and __lmul__ because these mean
    # element-wise multiplication in numpy land.

    def __add__(self, other):
        return Sum([self, other])

    def __radd__(self, other):
        return Sum([other, self])

    # OVER-RIDE THIS (or rmul)
    def lmul(self, x, T=False):
        """mul(x, A) or mul(x, A.T)

        If T is True this method returns mul(x, A.T).
        If T is False this method returns mul(x, A).

        """
        # this is a circular definition with rmul so that they are both
        # implemented as soon as one of them is overridden by a base class.
        return self.transpose_right(
                self.rmul(
                    self.transpose_left(x),
                    not T))

    # OVER-RIDE THIS (or lmul)
    def rmul(self, x, T=False):
        """mul(A, x) or mul(A.T, x)
        """
        # this is a circular definition with rmul so that they are both
        # implemented as soon as one of them is overridden by a base class.
        return self.transpose_left(
                self.lmul(
                    self.transpose_right(x),
                    not T))

    def transpose_left(self, x):
        """
        """
        cshp = self.col_shape()
        xshp = x.shape
        ndim_rows = x.ndim - len(cshp)
        pattern = range(ndim_rows, x.ndim) + range(ndim_rows)
        return x.transpose(pattern)

    def transpose_right(self, x):
        """
        """
        rshp = self.row_shape()
        xshp = x.shape
        ndim_rows = len(rshp)
        pattern = range(ndim_rows, x.ndim) + range(ndim_rows)
        return x.transpose(pattern)

    def transpose_left_shape(self, xshp):
        """
        """
        rowtuple, coltuple = self.split_left_shape(xshp)
        return coltuple + rowtuple

    def transpose_right_shape(self, xshp):
        """
        """
        rowtuple, coltuple = self.split_right_shape(xshp)
        return coltuple + rowtuple

    def split_left_shape(self, xshp):
        if type(xshp) != tuple:
            raise TypeError('need tuple', xshp)
        cshp = self.col_shape()
        assert type(cshp) == tuple
        if xshp[-len(cshp):] != cshp:
            raise ValueError('invalid left shape',
                    dict(xshp=xshp, col_shape=cshp))
        return xshp[:-len(cshp)], xshp[-len(cshp):]

    def split_right_shape(self, xshp):
        """
        """
        if type(xshp) != tuple:
            raise TypeError('need tuple', xshp)
        rshp = self.row_shape()
        assert type(rshp) == tuple
        if xshp[:len(rshp)] != rshp:
            raise ValueError('invalid right shape',
                    dict(xshp=xshp, row_shape=rshp))
        return xshp[:len(rshp)], xshp[len(rshp):]

    def is_valid_left_shape(self, xshp):
        """
        """
        try:
            self.split_left_shape(xshp)
            return True
        except ValueError:
            return False

    def is_valid_right_shape(self, xshp):
        """
        """
        try:
            self.split_right_shape(xshp)
            return True
        except ValueError:
            return False

    # OVER-RIDE THIS
    def row_shape(self):
        raise NotImplementedError('override me')

    # OVER-RIDE THIS
    def col_shape(self):
        raise NotImplementedError('override me')

    def transpose(self):
        return TransposeTransform(self)

    T = property(lambda self: self.transpose())

    # OVER-RIDE THIS
    def tile_columns(self, **kwargs):
        raise NotImplementedError('override me')


class TransposeTransform(LinearTransform):
    def __init__(self, base):
        super(TransposeTransform, self).__init__([])
        self.base = base

    def transpose(self):
        return self.base

    def params(self):
        return self.base.params()

    def lmul(self, x, T=False):
        return self.base.lmul(x, not T)

    def rmul(self, x, T=False):
        return self.base.rmul(x, not T)

    def transpose_left(self, x):
        return self.base.transpose_right(x)

    def transpose_right(self, x):
        return self.base.transpose_left(x)

    def transpose_left_shape(self, x):
        return self.base.transpose_right_shape(x)

    def transpose_right_shape(self, x):
        return self.base.transpose_left_shape(x)

    def split_left_shape(self, x):
        return self.base.split_right_shape(x)

    def split_right_shape(self, x):
        return self.base.split_left_shape(x)

    def is_valid_left_shape(self, x):
        return self.base.is_valid_right_shape(x)

    def is_valid_right_shape(self, x):
        return self.base.is_valid_left_shape(x)

    def row_shape(self):
        return self.base.col_shape()

    def col_shape(self):
        return self.base.row_shape()

    def print_status(self):
        return self.base.print_status()

    def tile_columns(self):
        # yes, it would be nice to do rows, but since this is a visualization
        # and there *is* no tile_rows, we fall back on this.
        return self.base.tile_columns()


if 0: # needs to be brought up to date with LinearTransform method names
    class MatrixMul(LinearTransform):
        """
        Linear transform backed by an actual matrix.
        """
        # Works for Sparse and TensorType matrices
        def __init__(self, W, row_shape=None, col_shape=None):
            """

            If W is not shared variable, row_shape and col_shape must be
            specified.
            """
            super(MatrixMul, self).__init__([W])
            self._W = W
            Wval = None
            if row_shape is None:
                Wval = W.get_value(borrow=True)
                rows, cols = Wval.shape
                self.__row_shape = rows,
            else:
                self.__row_shape = tuple(row_shape)
            if col_shape is None:
                if Wval is None:
                    Wval = W.get_value(borrow=True)
                    rows, cols = Wval.shape
                self.__col_shape = cols,
            else:
                self.__col_shape = tuple(col_shape)

        def _lmul(self, x, T):
            if T:
                W = self._W.T
                rshp = tensor.stack(x.shape[0], *self.__row_shape)
            else:
                W = self._W
                rshp = tensor.stack(x.shape[0], *self.__col_shape)
            rval = theano.dot(x.flatten(2), W).reshape(rshp)
            return rval
        def _row_shape(self):
            return self.__row_shape
        def _col_shape(self):
            return self.__col_shape

        def print_status(self):
            print ndarray_status(self._W.get_value(borrow=True), msg=self._W.name)

        def _tile_columns(self, channel_major=False, scale_each=False,
                min_dynamic_range=1e-4, **kwargs):
            W = self._W.get_value(borrow=False).T
            shape = self.row_shape()
            if channel_major:
                W.shape = (W.shape[0:1]+shape)
                W = W.transpose(0,2,3,1) #put colour last
            else:
                raise NotImplementedError()

            return pylearn.io.image_tiling.tile_slices_to_image(W,
                    scale_each=scale_each,
                    **kwargs)

    class Concat(LinearTransform):
        """
        Form a linear map of the form [A B ... Z].

        For this to be valid, A,B...Z must have identical row_shape.

        The col_shape defaults to being the concatenation of flattened output from
        each of A,B,...Z, but a col_shape tuple specified via the constructor will
        reshape that vector.
        """
        def __init__(self, Wlist, col_shape=None):
            super(Concat, self).__init__([])
            self._Wlist = list(Wlist)
            if not isinstance(col_shape, (int,tuple,type(None))):
                raise TypeError('col_shape must be int or int tuple')
            self._col_sizes = [prod(w.col_shape()) for w in Wlist]
            if col_shape is None:
                self.__col_shape = sum(self._col_sizes),
            elif isinstance(col_shape, int):
                self.__col_shape = col_shape,
            else:
                self.__col_shape = tuple(col_shape)
            assert prod(self.__col_shape) == sum(self._col_sizes)
            self.__row_shape = Wlist[0].row_shape()
            for W in Wlist[1:]:
                if W.row_shape() != self.row_shape():
                    raise ValueError('Transforms has different row_shape',
                            W.row_shape())

        def params(self):
            rval = []
            for W in self._Wlist:
                rval.extend(W.params())
            return rval
        def _lmul(self, x, T):
            if T:
                if len(self.col_shape())>1:
                    x2 = x.flatten(2)
                else:
                    x2 = x
                n_rows = x2.shape[0]
                offset = 0
                xWlist = []
                assert len(self._col_sizes) == len(self._Wlist)
                for size, W in zip(self._col_sizes, self._Wlist):
                    # split the output rows into pieces
                    x_s = x2[:,offset:offset+size]
                    # multiply each piece by one transform
                    xWlist.append(
                            W.lmul(
                                x_s.reshape(
                                    (n_rows,)+W.col_shape()),
                                T))
                    offset += size
                # sum the results
                rval = tensor.add(*xWlist)
            else:
                # multiply the input by each transform
                xWlist = [W.lmul(x,T).flatten(2) for W in self._Wlist]
                # join the resuls
                rval = tensor.join(1, *xWlist)
            return rval
        def _col_shape(self):
            return self.__col_shape
        def _row_shape(self):
            return self.__row_shape
        def _tile_columns(self):
            # hard-coded to produce RGB images
            arrays = [W._tile_columns() for W in self._Wlist]
            o_rows = sum([a.shape[0]+10 for a in arrays]) - 10
            o_cols = max([a.shape[1] for a in arrays])
            rval = numpy.zeros(
                    (o_rows, o_cols, 3),
                    dtype=arrays[0].dtype)
            offset = 0
            for a in arrays:
                if a.ndim==2:
                    a = a[:,:,None] #make greyscale broadcast over colors
                rval[offset:offset+a.shape[0], 0:a.shape[1],:] = a
                offset += a.shape[0] + 10
            return rval
        def print_status(self):
            for W in self._Wlist:
                W.print_status()


    class Sum(LinearTransform):
        def __init__(self, terms):
            self.terms = terms
            for t in terms[1:]:
                assert t.row_shape() == terms[0].row_shape()
                assert t.col_shape() == terms[0].col_shape()
        def params(self):
            rval = []
            for t in self.terms:
                rval.extend(t.params())
            return rval
        def _lmul(self, x, T):
            results = [t._lmul(x, T)]
            return tensor.add(*results)
        def _row_shape(self):
            return self.terms[0].col_shape()
        def _col_shape(self):
            return self.terms[0].row_shape()
        def print_status(self):
            for t in terms:
                t.print_status()
        def _tile_columns(self):
            raise NotImplementedError('TODO')



if 0: # This is incomplete
    class Compose(LinearTransform):
        """ For linear transformations [A,B,C]
        this represents the linear transformation A(B(C(x))).
        """
        def __init__(self, linear_transformations):
            self._linear_transformations = linear_transformations
        def dot(self, x):
            return reduce(
                    lambda t,a:t.dot(a),
                    self._linear_transformations,
                    x)
        def transpose_dot(self, x):
            return reduce(
                    lambda t, a: t.transpose_dot(a),
                    reversed(self._linear_transformations),
                    x)
        def params(self):
            return reduce(
                    lambda t, a: a + t.params(),
                    self._linear_transformations,
                    [])

