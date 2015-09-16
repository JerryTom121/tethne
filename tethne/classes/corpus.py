"""
A :class:`.Corpus` organizes :class:`.Paper`\s for analysis.
"""

from collections import Counter
import hashlib

from tethne.classes.feature import FeatureSet, Feature
from tethne.utilities import _iterable, argsort


def _tfidf(f, c, C, DC, N):
    tf = float(c)
    idf = np.log(float(N)/float(DC))
    return tf*idf


def _filter(s, C, DC):
    if C > 3 and DC > 1 and len(s) > 3:
        return True
    return False


class Corpus(object):
    """
    A :class:`.Corpus` represents a collection of :class:`.Paper` instances.

    :class:`.Corpus` objects are generated by the bibliographic readers in the
    :mod:`tethne.readers` module.

    .. code-block:: python

       >>> from tethne.readers.wos import read
       >>> read('/path/to/data')
       <tethne.classes.corpus.Corpus object at 0x10278ea10>

    You can also build a :class:`.Corpus` from a list of :class:`.Paper`\s.

    .. code-block:: python

       >>> papers = however_you_generate_papers()   # <- list of Papers.
       >>> corpus = Corpus(papers)

    All of the :class:`.Paper`\s in the :class:`.Corpus` will be indexed. You can control
    which field is used for indexing by passing the ``index_by`` keyword argument to one
    of the ``read`` methods or to the :class:`.Corpus` constructor.

    .. code-block:: python

       >>> corpus = Corpus(papers, index_by='doi')
       >>> corpus.indexed_papers.keys()
       ['doi/123', 'doi/456', ..., 'doi/789']

    The WoS ``read`` method uses the ``wosid`` field by default, and the DfR ``read``
    method uses ``doi``. The Zotero ``read`` method tries to use whatever it can find. If
    the selected ``index_by`` field is not set or not available, a unique key will be
    generated using the title and author names.

    By default, :class:`.Corpus` will also index the ``authors`` and ``citations``
    fields. To control which fields are indexed, pass the ``index_fields``
    argument, or call :meth:`.Corpus.index` directly.

    .. code-block:: python

       >>> corpus = Corpus(papers, index_fields=['authors', 'date'])
       >>> corpus.indices.keys()
       ['authors', 'date']


    Similarly, :class:`.Corpus` will index features. By default, ``authors``
    and ``citations`` will be indexed as features (i.e. available for
    network-building methods). To control which fields are indexed as features,
    pass the ``index_features`` argument, or call
    :meth:`.Corpus.index_features`\.

    .. code-block:: python

       >>> corpus = Corpus(papers, index_features=['unigrams'])
       >>> corpus.features.keys()
       ['unigrams']

    There are a variety of ways to select :class:`.Paper`\s from the corpus.

    .. code-block:: python

       >>> corpus = Corpus(papers)
       >>> corpus[0]    # Integer indices yield a single Paper.
       <tethne.classes.paper.Paper object at 0x103037c10>

       >>> corpus[range(0,5)]  # A list of indices will yield a list of Papers.
       [<tethne.classes.paper.Paper object at 0x103037c10>,
        <tethne.classes.paper.Paper object at 0x10301c890>,
        ...
        <tethne.classes.paper.Paper object at 0x10302f5d0>]

       >>> corpus[('date', 1995)]  # You can select based on indexed fields.
       [<tethne.classes.paper.Paper object at 0x103037c10>,
        <tethne.classes.paper.Paper object at 0x10301c890>,
        ...
        <tethne.classes.paper.Paper object at 0x10302f5d0>]

       >>> corpus['citations', ('DOLE RJ 1952 CELL')]   # All papers with this citation!
       [<tethne.classes.paper.Paper object at 0x103037c10>,
        <tethne.classes.paper.Paper object at 0x10301c890>,
        ...
        <tethne.classes.paper.Paper object at 0x10302f5d0>]

       >>> corpus[('date', range(1993, 1995))]  # Multiple values are supported, too.
       [<tethne.classes.paper.Paper object at 0x103037c10>,
        <tethne.classes.paper.Paper object at 0x10301c890>,
        ...
        <tethne.classes.paper.Paper object at 0x10302f5d0>]

    If you prefer to retrieve a :class:`.Corpus` rather than simply a list of
    :class:`.Paper` instances (e.g. to build networks), use
    :meth:`.Corpus.subcorpus`\. ``subcorpus`` accepts selector arguments
    just like :meth:`.Corpus.__getitem__`\.

    .. code-block:: python

       >>> corpus = Corpus(papers)
       >>> subcorpus = corpus.subcorpus(('date', 1995))
       >>> subcorpus
       <tethne.classes.corpus.Corpus object at 0x10278ea10>

    """
    @property
    def papers(self):
        return self.indexed_papers.values()

    def __init__(self, papers=None, index_by=None,
                 index_fields=['authors', 'citations'],
                 index_features=['authors', 'citations'], **kwargs):
        """
        Parameters
        ----------
        paper : list
        index_by : str
        index_fields : str or iterable of strs
        kwargs : kwargs

        """

        self.index_by = index_by
        self.indices = {}
        self.features = {}
        self.slices = []

        self.indexed_papers = {self._generate_index(paper): paper for paper in papers}

        if index_features:
            for feature_name in index_features:
                self.index_feature(feature_name)

        if index_fields:
            for attr in _iterable(index_fields):
                self.index(attr)


    def __len__(self):
        return len(self.indexed_papers)

    def _generate_index(self, paper):
        """
        If the ``index_by`` field is not set or not available, generate a unique
        identifier using the :class:`.Paper`\'s title and author names.
        """

        if self.index_by is None or not hasattr(paper, self.index_by):
            if not hasattr(paper, 'hashIndex'): # Generate a new index for this paper.
                authors = zip(*paper.authors)[0]
                m = hashlib.md5()
                hashable = ' '.join(list([paper.title] + [l + f for l, f in authors]))
                m.update(hashable)
                setattr(paper, 'hashIndex', m.hexdigest())
            return getattr(paper, 'hashIndex')
        return getattr(paper, self.index_by)    # Identifier is already available.

    def index_feature(self, feature_name):
        """
        Create a new :class:`.Feature` from the attribute ``feature_name``
        in each :class:`.Paper`\.

        Parameters
        ----------
        feature_name : str
            The name of a :class:`.Paper` attribute.

        """
        feats = {self._generate_index(p): Feature(getattr(p, feature_name))
                 for p in self.papers if hasattr(p, feature_name)}
        self.features[feature_name] = FeatureSet(feats)

    def index(self, attr):
        """
        Index ``papers`` by ``attr``

        Parameters
        ----------
        attr : str
            The name of a :class:`.Paper` attribute.

        """

        self.indices[attr] = {}
        for i, paper in self.indexed_papers.iteritems():
            if hasattr(paper, attr):
                value = getattr(paper, attr)
                for v in _iterable(value):
                    if type(value) is Feature:
                        v_ = v[:-1]
                    else:
                        v_ = v

                    if hasattr(v_, '__iter__'):
                        if len(v_) == 1:
                            t = type(v_[0])
                            v_ = t(v_[0])

                    if v_ not in self.indices[attr]:
                        self.indices[attr][v_] = []
                    self.indices[attr][v_].append(i)


    def __getitem__(self, selector):
        return self.select(selector)

    def __getattr__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        elif key in self.indices:
            return self.indices[key]
        raise AttributeError("Corpus has no such attribute")

    def select(self, selector):
        """
        Retrieve a subset of :class:`.Paper`\s based on selection criteria.

        There are a variety of ways to select :class:`.Paper`\s.

        .. code-block:: python

           >>> corpus = Corpus(papers)
           >>> corpus[0]    # Integer indices yield a single Paper.
           <tethne.classes.paper.Paper object at 0x103037c10>

           >>> corpus[range(0,5)]  # A list of indices yields a list of Papers.
           [<tethne.classes.paper.Paper object at 0x103037c10>,
            <tethne.classes.paper.Paper object at 0x10301c890>,
            ...
            <tethne.classes.paper.Paper object at 0x10302f5d0>]

           >>> corpus[('date', 1995)]  # Select based on indexed fields.
           [<tethne.classes.paper.Paper object at 0x103037c10>,
            <tethne.classes.paper.Paper object at 0x10301c890>,
            ...
            <tethne.classes.paper.Paper object at 0x10302f5d0>]

           >>> corpus['citations', ('DOLE RJ 1952 CELL')]   # Citing papers!
           [<tethne.classes.paper.Paper object at 0x103037c10>,
            <tethne.classes.paper.Paper object at 0x10301c890>,
            ...
            <tethne.classes.paper.Paper object at 0x10302f5d0>]

           >>> corpus[('date', range(1993, 1995))] # Multiple values are OK.
           [<tethne.classes.paper.Paper object at 0x103037c10>,
            <tethne.classes.paper.Paper object at 0x10301c890>,
            ...
            <tethne.classes.paper.Paper object at 0x10302f5d0>]

        If you prefer to retrieve a :class:`.Corpus` rather than simply a
        list of :class:`.Paper` instances (e.g. to build networks), use
        :meth:`.Corpus.subcorpus`\.

        Parameters
        ----------
        selector : object
            See method description.

        Returns
        -------
        list
            A list of :class:`.Paper`\s.
        """

        if type(selector) is tuple: # Select papers by index.
            index, value = selector
            if type(value) is list:  # Set of index values.
                papers = [p for v in value for p in self[index, v]]
            else:
                papers = [self.indexed_papers[p] for p  # Single index value.
                          in self.indices[index][value]]
        elif type(selector) is list:
            if selector[0] in self.indexed_papers:
                # Selector is a list of primary indices.
                papers = [self.indexed_papers[s] for s in selector]
            elif type(selector[0]) is int:
                papers = [self.papers[i] for i in selector]
        elif type(selector) is int:
            papers = self.papers[selector]
        return papers

    def slice(self, window_size=1, step_size=1):
        """
        Returns a generator that yields ``(key, subcorpus)`` tuples for
        sequential time windows.

        Two common slicing patterns are the "sliding time-window" and the
        "time-period" patterns. Whereas time-period slicing divides the corpus
        into subcorpora by sequential non-overlapping time periods, subcorpora
        generated by time-window slicing can overlap.

        .. figure:: _static/images/bibliocoupling/timeline.timeslice.png
           :width: 400
           :align: center

           **Time-period** slicing, with a window-size of 4 years.

        .. figure:: _static/images/bibliocoupling/timeline.timewindow.png
           :width: 400
           :align: center

           **Time-window** slicing, with a window-size of 4 years and a
           step-size of 1 year.

        *Sliding time-window* -- Set ``step_size=1``, and ``window_size`` to
        the desired value.
        *Time-period* -- ``step_size`` and ``window_size`` should have the same
        value.

        The value of ``key`` is always the first year in the slice.

        Example
        -------
        .. code-block:: python

           >>> from tethne.readers.wos import read
           >>> corpus = read('/path/to/data')
           >>> for key, subcorpus in corpus.slice():
           ...     print key, len(subcorpus)
           2005, 5
           2006, 5

        Parameters
        ----------
        window_size : int
            (default: 1) Size of the time window, in years.
        step_size : int
            (default: 1) Number of years to advance window at each step.

        Returns
        -------
        generator
        """


        if 'date' not in self.indices:
            self.index('date')

        start = min(self.indices['date'].keys())
        end = max(self.indices['date'].keys())
        print start, type(start), end, type(end), window_size, type(window_size)
        while start <= end - (window_size - 1):
            selector = ('date', range(start, start + window_size, 1))
            yield start, self.subcorpus(selector)
            start += step_size

    def distribution(self, **slice_kwargs):
        """
        Calculate the number of papers in each slice, as defined by
        ``slice_kwargs``.

        Example
        -------
        .. code-block:: python

           >>> corpus.distribution(step_size=1, window_size=1)
           [5, 5]

        Parameters
        ----------
        slice_kwargs : kwargs
            Keyword arguments to be passed to :method:`.Corpus.slice`\.

        Returns
        -------
        list
        """

        return [len(papers[1]) for papers in self.slice(**slice_kwargs)]

    def feature_distribution(self, featureset_name, feature, mode='counts',
                             **slice_kwargs):
        """
        Calculate the distribution of a feature across slices of the corpus.

        Example
        -------
        .. code-block:: python

           >>> corpus.feature_distribution(featureset_name='citations', \
           ...                             feature='DOLE RJ 1965 CELL', \
           ...                             step_size=1, window_size=1)
           [2, 15, 25, 1]

        Parameters
        ----------
        featureset_name : str
            Name of a :class:`.FeatureSet` in the :class:`.Corpus`\.
        feature : str
            Name of the specific feature of interest. E.g. if
            ``featureset_name='citations'``, then ``feature`` could be
            something like ``'DOLE RJ 1965 CELL'``.
        mode : str
            (default: ``'counts'``) If set to ``'counts'``, values will be the
            sum of all count values for the feature in each slice. If set to
            ``'documentCounts'``, values will be the number of papers in which
            the feature occurs in each slice.
        slice_kwargs : kwargs
            Keyword arguments to be passed to :method:`.Corpus.slice`\.

        Returns
        -------
        list
        """

        values = []
        keys = []

        for key, subcorpus in self.slice(**slice_kwargs):
            values.append(subcorpus.features[featureset_name].count(feature))
            keys.append(key)
        return keys, values

    def top_features(self, featureset_name, topn=20, by='counts',
                     perslice=False, slice_kwargs={}):
        """
        Retrieve the top ``topn`` most numerous features in the corpus.

        Parameters
        ----------
        featureset_name : str
            Name of a :class:`.FeatureSet` in the :class:`.Corpus`\.
        topn : int
            (default: ``20``) Number of features to return.
        by : str
            (default: ``'counts'``) If ``'counts'``, uses the sum of feature
            count values to rank features. If ``'documentCounts'``, uses the
            number of papers in which features occur.
        perslice : bool
            (default: False) If True, retrieves the top ``topn`` features in
            each slice.
        slice_kwargs : kwargs
            If ``perslice=True``, these keyword arguments are passed to
            :meth:`.Corpus.slice`\.
        """

        if perslice:
            return [(k, subcorpus.features[featureset_name].top(topn, by=by))
                    for k, subcorpus in self.slice(**slice_kwargs)]
        return self.features[featureset_name].top(topn, by=by)

    def subcorpus(self, selector):
        """
        Generate a new :class:`.Corpus` using the criteria in ``selector``.

        Accepts selector arguments just like  :meth:`.Corpus.select`\.

        .. code-block:: python

           >>> corpus = Corpus(papers)
           >>> subcorpus = corpus.subcorpus(('date', 1995))
           >>> subcorpus
           <tethne.classes.corpus.Corpus object at 0x10278ea10>

        """

        subcorpus = Corpus(self[selector], index_by=self.index_by,
                           index_fields=self.indices.keys(),
                           index_features=self.features.keys())

        # Transfer FeatureSets.
        for featureset_name, featureset in self.features.iteritems():
            if featureset_name not in subcorpus:
                new_featureset = FeatureSet()
                for k, f in featureset.items():
                    if k in subcorpus.indexed_papers:
                        new_featureset.add(k, f)
                subcorpus.features[featureset_name] = new_featureset

        return subcorpus
