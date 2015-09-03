﻿# -*- coding: utf-8 -*-
"""
    biosppy.clustering
    ------------------
    
    This module provides various unsupervised machine learning (clustering) algorithms.
    
    :copyright: (c) 2015 by Instituto de Telecomunicacoes
    :license: BSD 3-clause, see LICENSE for more details.
"""

# Imports
# built-in

# 3rd party
import numpy as np
import scipy.cluster.hierarchy as sch
import scipy.cluster.vq as scv
import scipy.sparse as sp
import sklearn.cluster as skc
from sklearn.grid_search import ParameterGrid

# local
from . import metrics, utils

# Globals


def dbscan(data=None, min_samples=5, eps=0.5, metric='euclidean', metric_args=None):
    """Perform clustering using the DBSCAN algorithm [1].
    
    The algorithm works by grouping data points that are closely packed together
    (with many nearby neighbors), marking as outliers points that lie in low-
    density regions.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        min_samples (int): Minimum number of samples in a cluster.
        
        eps (float): Maximum distance between two samples in the same cluster.
        
        metric (str): Distance metric (see scipy.spatial.distance).
        
        metric_args (dict): Additional keyword arguments to pass to the distance function (optional).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from 'data') for each found cluster;
                             outliers have key -1; clusters are assigned integer keys starting at 0.
    
    References:
        [1] M. Ester, H. P. Kriegel, J. Sander, and X. Xu, “A Density-Based Algorithm
            for Discovering Clusters in Large Spatial Databases with Noise”,
            Proceedings of the 2nd International Conference on Knowledge Discovery
            and Data Mining, pp. 226-231, 1996.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if metric_args is None:
        metric_args = {}
    
    # compute distances
    D = metrics.pdist(data, metric=metric, **metric_args)
    D = metrics.squareform(D)
    
    # fit
    db = skc.DBSCAN(eps=eps, min_samples=min_samples, metric='precomputed')
    labels = db.fit_predict(D)
    
    # get cluster indices
    clusters = _extract_clusters(labels)
    
    return utils.ReturnTuple((clusters, ), ('clusters', ))


def hierarchical(data=None, k=0, linkage='average', metric='euclidean', metric_args=None):
    """Perform clustering using hierarchical agglomerative algorithms.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        k (int): Number of clusters to extract; if 0 uses the life-time criterion (optional).
        
        linkage (str): Linkage criterion; one of 'average', 'centroid', 'complete',
                      'median', 'single', 'ward', or 'weighted'.
        
        metric (str): Data distances metric (see scipy.spatial.distance).
        
        metric_args (dict): Additional keyword arguments to pass to the distance function (optional).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from 'data') for each found cluster;
                             outliers have key -1; clusters are assigned integer keys starting at 0.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if linkage not in ['average', 'centroid', 'complete', 'median', 'single', 'ward', 'weighted']:
        raise ValueError("Unknown linkage criterion '%r'." % linkage)
    
    if metric_args is None:
        metric_args = {}
    
    N = len(data)
    if k > N:
        raise ValueError("Number of clusters 'k' is higher than the number of input samples.")
    
    if k < 0:
        k = 0
    
    # compute distances
    D = metrics.pdist(data, metric=metric, **metric_args)
    
    # build linkage
    Z = sch.linkage(D, method=linkage)
    
    # extract clusters
    if k == 0:
        # life-time
        labels = _life_time(Z, N)
    else:
        labels = sch.fcluster(Z, k, 'maxclust')
    
    # get cluster indices
    clusters = _extract_clusters(labels)
    
    return utils.ReturnTuple((clusters, ), ('clusters', ))


def kmeans(data=None, k=None, init='random', max_iter=300, n_init=10, tol=0.0001):
    """Perform clustering using the k-means algorithm.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        k (int): Number of clusters to extract.
        
        init (str, array): If string, one of 'random' or 'k-means++';
                           If array, it should be of shape (n_clusters, n_features),
                           specifying the initial centers (optional).
        
        max_iter (int): Maximum number of iterations (optional).
        
        n_init (int): Number of initializations (optional).
        
        tol (float): Relative tolerance to declare convergence (optional).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from 'data') for each found cluster;
                             outliers have key -1; clusters are assigned integer keys starting at 0.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if k is None:
        raise TypeError("Please specify the number 'k' of clusters.")
    
    clf = skc.KMeans(n_clusters=k, init=init, max_iter=max_iter, n_init=n_init, tol=tol)
    labels = clf.fit_predict(data)
    
    # get cluster indices
    clusters = _extract_clusters(labels)
    
    return utils.ReturnTuple((clusters, ), ('clusters', ))


def consensus(data=None, k=0, linkage='average', fcn=None, grid=None):
    """Perform clustering based in an ensemble of partitions.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        k (int): Number of clusters to extract; if 0 uses the life-time criterion (optional).
        
        linkage (str): Linkage criterion for final partition extraction;
                       one of 'average', 'centroid', 'complete', 'median',
                       'single', 'ward', or 'weighted'.
        
        fcn (function): A clustering function.
        
        grid (dict, list): A (list of) dictionary with parameters for each run
                           of the clustering method (see sklearn.grid_search.ParameterGrid).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from 'data') for each found cluster;
                             outliers have key -1; clusters are assigned integer keys starting at 0.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if fcn is None:
        raise TypeError("Please specify the clustering function.")
    
    if grid is None:
        grid = {}
    
    # create ensemble
    ensemble, = create_ensemble(data=data, fcn=fcn, grid=grid)
    
    # generate coassoc
    coassoc, = create_coassoc(ensemble=ensemble, N=len(data))
    
    # extract partition
    clusters, = coassoc_partition(coassoc=coassoc, k=k, linkage=linkage)
    
    return utils.ReturnTuple((clusters, ), ('clusters', ))


def consensus_kmeans(data=None, k=0, linkage='average', nensemble=100, kmin=None, kmax=None):
    """Perform clustering based on an ensemble of k-means partitions.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        k (int): Number of clusters to extract; if 0 uses the life-time criterion (optional).
        
        linkage (str): Linkage criterion for final partition extraction;
                       one of 'average', 'centroid', 'complete', 'median',
                       'single', 'ward', or 'weighted'.
        
        nensemble (int): Number of partitions in the ensemble (optional).
        
        kmin (int): Minimum k for the k-means partitions; defaults to sqrt(m) / 2 (optional).
        
        kmax (int): Maximum k for the k-means partitions: defaults to sqrt(m) (optional).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from 'data') for each found cluster;
                             outliers have key -1; clusters are assigned integer keys starting at 0.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    N = len(data)
    
    if kmin is None:
        kmin = int(round(np.sqrt(N) / 2.))
    
    if kmax is None:
        kmax = int(round(np.sqrt(N)))
    
    # initialization grid
    grid = {'k': np.random.random_integers(low=kmin, high=kmax, size=nensemble)}
    
    # run consensus
    clusters, = consensus(data=data, k=k, linkage=linkage, fcn=kmeans, grid=grid)
    
    return utils.ReturnTuple((clusters, ), ('clusters', ))


def create_ensemble(data=None, fcn=None, grid=None):
    """Create an ensemble of partitions of the data using the given clustering method.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        fcn (function): A clustering function.
        
        grid (dict, list): A (list of) dictionary with parameters for each run
                           of the clustering method (see sklearn.grid_search.ParameterGrid).
    
    Returns:
        (ReturnTuple): containing:
            ensemble (list): Obtained ensemble partitions.
     
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if fcn is None:
        raise TypeError("Please specify the clustering function.")
    
    if grid is None:
        grid = {}
    
    # grid iterator
    grid = ParameterGrid(grid)
    
    # run clustering
    ensemble = []
    for params in grid:
        ensemble.append(fcn(data, **params)['clusters'])
    
    return utils.ReturnTuple((ensemble, ), ('ensemble', ))


def create_coassoc(ensemble=None, N=None):
    """Create the co-association matrix from a clustering ensemble.
    
    Args:
        ensemble (list): Clustering ensemble partitions.
        
        N (int): Number of data samples.
    
    Returns:
        (ReturnTuple): containing:
            coassoc (array): Co-association matrix.
    
    """
    
    # check inputs
    if ensemble is None:
        raise TypeError("Please specify the clustering ensemble.")
    
    if N is None:
        raise TypeError("Please specify the number of samples in the original data set.")
    
    nparts = len(ensemble)
    assoc = 0
    for part in ensemble:
        nsamples = np.array([len(part[key]) for key in part.iterkeys()])
        dim = np.sum(nsamples * (nsamples - 1)) / 2
        
        I = np.zeros(dim)
        J = np.zeros(dim)
        X = np.ones(dim)
        ntriplets = 0
        
        for v in part.itervalues():
            nb = len(v)
            if nb > 0:
                for h in xrange(nb):
                    for f in xrange(h + 1, nb):
                        I[ntriplets] = v[h]
                        J[ntriplets] = v[f]
                        ntriplets += 1
        
        assoc_aux = sp.csc_matrix((X, (I, J)), shape=(N, N))
        assoc += assoc_aux
    
    a = assoc + assoc.T
    a.setdiag(nparts * np.ones(N))
    coassoc = a.todense()
    
    return utils.ReturnTuple((coassoc, ), ('coassoc', ))


def coassoc_partition(coassoc=None, k=0, linkage='average'):
    """Extract the consensus partition from a co-association matrix using hierarchical agglomerative methods.
    
    Args:
        coassoc (array): Co-association matrix.
        
        k (int): Number of clusters to extract; if 0 uses the life-time criterion (optional).
        
        linkage (str): Linkage criterion for final partition extraction;
                       one of 'average', 'centroid', 'complete', 'median',
                       'single', 'ward', or 'weighted'.
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from 'data') for each found cluster;
                             outliers have key -1; clusters are assigned integer keys starting at 0.
    
    """
    
    # check inputs
    if coassoc is None:
        raise TypeError("Please specify the input co-association matrix.")
    
    if linkage not in ['average', 'centroid', 'complete', 'median', 'single', 'ward', 'weighted']:
        raise ValueError("Unknown linkage criterion '%r'." % linkage)
    
    N = len(coassoc)
    if k > N:
        raise ValueError("Number of clusters 'k' is higher than the number of input samples.")
    
    if k < 0:
        k = 0
    
    # convert coassoc to condensed format, dissimilarity
    mx = np.max(coassoc)
    D = metrics.squareform(mx - coassoc)
    
    # build linkage
    Z = sch.linkage(D, method=linkage)
    
    # extract clusters
    if k == 0:
        # life-time
        labels = _life_time(Z, N)
    else:
        labels = sch.fcluster(Z, k, 'maxclust')
    
    # get cluster indices
    clusters = _extract_clusters(labels)
    
    return utils.ReturnTuple((clusters, ), ('clusters', ))


def mdist_templates(data=None, clusters=None, ntemplates=1, metric='euclidean', metric_args=None):
    """Template selection based on the MDIST method [1].
    
    Extends the original method with the option of also providing a data clustering,
    in which case the MDIST criterion is applied for each cluster [2].
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        clusters (dict): Dictionary with the sample indices (rows from 'data') for each cluster (optional).
        
        ntemplates (int): Number of templates to extract.
        
        metric (str): Data distances metric (see scipy.spatial.distance).
        
        metric_args (dict): Additional keyword arguments to pass to the distance function (optional).
    
    Retrurns:
        (ReturnTuple): containing:
            templates (array): Selected templates from the input data.
    
    References:
        [1]  U. Uludag, A. Ross, A. Jain, "Biometric template selection and
             update: a case study in fingerprints", Pattern Recognition 37 (2004).
        
        [2] A. Lourenco, C. Carreiras, H. Silva, A. Fred, "ECG biometrics:
            A template selection approach", 2014 IEEE International Symposium on
            Medical Measurements and Applications (MeMeA).
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if clusters is None:
        clusters = {0: np.arange(len(data), dtype='int')}
    
    # cluster labels
    ks = clusters.keys()
    
    # remove the outliers' cluster, if present
    if '-1' in ks:
        ks.remove('-1')
    
    cardinals = [len(clusters[k]) for k in ks]
    
    # check number of templates
    if np.isscalar(ntemplates):
        if ntemplates < 1:
            raise ValueError("The number of templates has to be at least 1.")
        # allocate templates per cluster
        ntemplatesPerCluster = utils.highestAveragesAllocator(cardinals, ntemplates, divisor='dHondt', check=True)
    else:
        # ntemplates as a list is unofficially supported; we have to account for cluster label order
        if np.sum(ntemplates) < 1:
            raise ValueError("The total number of templates has to be at least 1.")
        # just copy
        ntemplatesPerCluster = ntemplates
    
    templates = []
    
    for i, k in enumerate(ks):
        c = np.array(clusters[k])
        length = cardinals[i]
        nt = ntemplatesPerCluster[i]
        
        if nt == 0:
            continue
        
        if length == 0:
            continue
        elif length == 1:
            templates.append(data[c][0])
        elif length == 2:
            if nt == 1:
                # choose randomly
                r = round(np.random.rand())
                templates.append(data[c][r])
            else:
                for j in range(length):
                    templates.append(data[c][j])
        else:
            # compute mean distances
            indices, _ = _mean_distance(data[c], metric=metric, metric_args=metric_args)
            
            # select templates
            sel = indices[:nt]
            for item in sel:
                templates.append(data[c][item])
    
    templates = np.array(templates)
    
    return utils.ReturnTuple((templates, ), ('templates', ))


def centroid_templates(data=None, clusters=None, ntemplates=1):
    """Template selection based on cluster centroids.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        clusters (dict): Dictionary with the sample indices (rows from 'data') for each cluster.
        
        ntemplates (int): Number of templates to extract; if more than 1,
                          k-means is used to obtain more templates.
    
    Retrurns:
        (ReturnTuple): containing:
            templates (array): Selected templates from the input data.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if clusters is None:
        raise TypeError("Please specify a data clustering.")
    
    # cluster labels
    ks = clusters.keys()
    
    # remove the outliers' cluster, if present
    if '-1' in ks:
        ks.remove('-1')
    
    cardinals = [len(clusters[k]) for k in ks]
    
    # check number of templates
    if np.isscalar(ntemplates):
        if ntemplates < 1:
            raise ValueError("The number of templates has to be at least 1.")
        # allocate templates per cluster
        ntemplatesPerCluster = utils.highestAveragesAllocator(cardinals, ntemplates, divisor='dHondt', check=True)
    else:
        # ntemplates as a list is unofficially supported; we have to account for cluster label order
        if np.sum(ntemplates) < 1:
            raise ValueError("The total number of templates has to be at least 1.")
        # just copy
        ntemplatesPerCluster = ntemplates
    
    # select templates
    templates = []
    for i, k in enumerate(ks):
        c = np.array(clusters[k])
        length = cardinals[i]
        nt = ntemplatesPerCluster[i]
        
        # ignore cases
        if nt == 0 or length == 0:
            continue
        
        if nt == 1:
            # cluster centroid
            templates.append(np.mean(data[c], axis=0))
        elif nt == length:
            # centroids are the samples
            templates.extend(data[c])
        else:
            # divide space using k-means
            nb = min([nt, length])
            # centroidsKmeans, _ = kmeans(data[c], nb, 50) # bug in initialization
            centroidsKmeans, _ = scv.kmeans2(data[c], k=nb, iter=50, minit='points')
            for item in centroidsKmeans:
                templates.append(item)
    
    templates = np.array(templates)
    
    return utils.ReturnTuple((templates, ), ('templates', ))


def outliers_dbscan(data=None, min_samples=5, eps=0.5, metric='euclidean', metric_args=None):
    """Perform outlier removal using the DBSCAN algorithm [1].
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        min_samples (int): Minimum number of samples in a cluster.
        
        eps (float): Maximum distance between two samples in the same cluster.
        
        metric (str): Distance metric (see scipy.spatial.distance).
        
        metric_args (dict): Additional keyword arguments to pass to the distance function (optional).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from
                             'data') for the outliers (key -1) and the normal
                             (key 0) groups.
            
            templates (dict): Elements from 'data' for the outliers (key -1) and
                              the normal (key 0) groups.
    
    References:
        [1] M. Ester, H. P. Kriegel, J. Sander, and X. Xu, “A Density-Based Algorithm
            for Discovering Clusters in Large Spatial Databases with Noise”,
            Proceedings of the 2nd International Conference on Knowledge Discovery
            and Data Mining, pp. 226-231, 1996.
    
    """
    
    # perform clustering
    clusters, = dbscan(data=data, min_samples=min_samples, eps=eps,
                       metric=metric, metric_args=metric_args)
    
    # merge clusters
    clusters = _merge_clusters(clusters)
    
    # separate templates
    templates = {-1: data[clusters[-1]],
                 0: data[clusters[0]],
                 }
    
    # output
    args = (clusters, templates)
    names = ('clusters', 'templates')
    
    return utils.ReturnTuple(args, names)


def outliers_dmean(data=None, alpha=0.5, beta=1.5, metric='euclidean', metric_args=None, max_idx=None):
    """Perform outlier removal using the DMEAN algorithm [1].
    
    A sample is considered valid if it cumulatively verifies:
        * distance to average template smaller than a (data derived) threshold 'T';
        * sample minimum greater than a (data derived) threshold 'M';
        * sample maximum smaller than a (data derived) threshold 'N';
        * [optional] position of the sample maximum is the same as the given index.
    
    .. math::
    
        For a set of {X_1, ..., X_n} n samples,
        Y = \\frac{1}{n} \\sum_{i=1}^{n}{X_i}
        d_i = dist(X_i, Y)
        D_m = \\frac{1}{n} \\sum_{i=1}^{n}{d_i}
        D_s = \\sqrt{\frac{1}{n - 1} \\sum_{i=1}^{n}{(d_i - D_m)^2}}
        T = D_m + \\alpha * D_s
        M = \\beta * median({max(X_i), i=1, ..., n})
        N = \\beta * median({min(X_i), i=1, ..., n})
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        alpha (float): Parameter for the distance threshold (optional).
        
        beta (float): Parameter for the maximum and minimum thresholds (optional).
        
        metric (str): Distance metric (see scipy.spatial.distance) (optional).
        
        metric_args (dict): Additional keyword arguments to pass to the distance function (optional).
        
        max_idx (int): Index of the expected maximum (optional).
    
    Returns:
        (ReturnTuple): containing:
            clusters (dict): Dictionary with the sample indices (rows from
                             'data') for the outliers (key -1) and the normal
                             (key 0) groups.
            
            templates (dict): Elements from 'data' for the outliers (key -1) and
                              the normal (key 0) groups.
    
    References:
        [1] A. Lourenco, H. Silva, C. Carreiras, A. Fred, "Outlier Detection in
            Non-intrusive ECG Biometric System", Image Analysis and Recognition,
            vol. 7950, pp. 43-52, 2013.
    
    """
    
    # check inputs
    if data is None:
        raise TypeError("Please specify input data.")
    
    if metric_args is None:
        metric_args = {}
    
    # distance to mean wave
    mean_wave = np.mean(data, axis=0, keepdims=True)
    dists = metrics.cdist(data, mean_wave, metric=metric, **metric_args)
    dists = dists.flatten()
    
    # distance threshold
    th = np.mean(dists) + alpha * np.std(dists, ddof=1)
    
    # median of max and min
    M = np.median(np.max(data, 1)) * beta
    m = np.median(np.min(data, 1)) * beta
    
    # search for outliers
    outliers = []
    for i, item in enumerate(data):
        idx = np.argmax(item)
        if (max_idx is not None) and (idx != max_idx):
            outliers.append(i)
        elif item[idx] > M:
            outliers.append(i)
        elif np.min(item) < m:
            outliers.append(i)
        elif dists[i] > th:
            outliers.append(i)
    
    outliers = np.unique(outliers)
    normal = np.setdiff1d(range(len(data)), outliers, assume_unique=True)
    
    # output
    clusters = {-1: outliers,
                0: normal,
                }
    
    templates = {-1: data[outliers],
                 0: data[normal],
                 }
    
    args = (clusters, templates)
    names = ('clusters', 'templates')
    
    return utils.ReturnTuple(args, names)


def _life_time(Z, N):
    """Life-Time criterion for automatic selection of the number of clusters.
    
    Args:
        Z (array): The hierarchical clustering encoded as a linkage matrix.
        
        N (int): Number of data samples.
    
    Returns:
        labels (array): Cluster labels.
    
    """
    
    if N < 3:
        return np.arange(N, dtype='int')
    
    # find maximum
    df = np.diff(Z[:, 2])
    idx = np.argmax(df)
    mx = df[idx]
    th = Z[idx, 2]
    
    idxs = Z[np.nonzero(Z[:, 2] > th)[0], 2]
    cont = len(idxs) + 1
    
    # find minimum
    mi = np.min(df[np.nonzero(df != 0)])
    
    if mi != mx:
        if mx < 2 * mi:
            cont = 1
    
    if cont > 1:
        labels = sch.fcluster(Z, cont, 'maxclust')
    else:
        labels = np.arange(N, dtype='int')
    
    return labels


def _extract_clusters(labels):
    """Extract cluster indices from an array of cluster labels.
    
    Args:
        labels (array): Input cluster labels.
    
    Returns:
        clusters (dict): Dictionary with the sample indices for each found
                         cluster; outliers have key -1; clusters are assigned
                         integer keys starting at 0.
    
    """
    
    # ensure numpy
    labels = np.array(labels)
    
    # unique labels and sort
    unq = np.unique(labels).tolist()
    
    
    clusters = {}
    
    # outliers
    if -1 in unq:
        clusters[-1] = np.nonzero(labels == -1)[0]
        unq.remove(-1)
    elif '-1' in unq:
        clusters[-1] = np.nonzero(labels == '-1')[0]
        unq.remove('-1')
    
    for i, u in enumerate(unq):
        clusters[i] = np.nonzero(labels == u)[0]
    
    return clusters


def _mean_distance(data, metric='euclidean', metric_args=None):
    """Compute the sorted mean distance between the input samples.
    
    Args:
        data (array): An m by n array of m data samples in an n-dimensional space.
        
        metric (str): Data distances metric (see scipy.spatial.distance).
        
        metric_args (dict): Additional keyword arguments to pass to the distance function (optional).
    
    Returns:
        (tulpe): containing:
            indices (array): Indices that sort the computed mean distances.
            
            mdist (array): Mean distance characterizing each data sample.
    
    """
    
    if metric_args is None:
        metric_args = {}
    
    # compute distances
    D = metrics.pdist(data, metric=metric, **metric_args)
    D = metrics.squareform(D)
    
    # compute mean
    mdist = np.mean(D, axis=0)
    
    # sort
    indices = np.argsort(mdist)
    
    return indices, mdist


def _merge_clusters(clusters):
    """Merge non-outlier clusters in a partition.
    
    Args:
        clusters (dict): Dictionary with the sample indices for each found
                         cluster; outliers have key -1.
    
    Returns:
        res (dict): Merged clusters.
    
    """
    
    keys = clusters.keys()
    
    # outliers
    if -1 in keys:
        keys.remove(-1)
        res = {-1: clusters[-1]}
    else:
        res = {-1: np.array([], dtype='int')}
    
    # normal clusters
    aux = np.concatenate([clusters[k] for k in keys])
    res[0] = np.unique(aux).astype('int')
    
    return res
