# This is a flag used to build ete2 standalone package.
in_ete_pkg=True
#!/usr/bin/env python

import sys
import re
import numpy
from os import path

from scipy import stats
import math


class ArrayTable(object):
    """This object is thought to work with matrix datasets (like
    microarrays). It allows to load the matrix an access easily to row
    and column vectors. """

    def __init__(self, matrix_file=None, mtype="float"):
        self.colNames  = []
        self.rowNames  = []
        self.colValues = {}
        self.rowValues = {}
        self.matrix   = None
        self.mtype = None

	# If matrix file is supplied
        if matrix_file is not None:

	    if path.exists(matrix_file):
		from pygenomics.parser import text_arraytable
		text_arraytable.read_arraytable(matrix_file, \
						    mtype=mtype, \
						    arraytable_object = self)

    def get_row_vector(self,rowname):
        """ Returns the vector associated to the given row name """
	return self.rowValues.get(rowname,None)


    def get_column_vector(self,colname):
        """ Returns the vector associated to the given column name """
	return self.colValues.get(colname,None)


    def get_several_column_vectors(self,colnames):
        """ Returns a list of vectors associated to several column names """
	vectors = [self.colValues[cname] for cname in colnames]
	return numpy.array(vectors)
        
    def get_several_row_vectors(self,rownames):
        """ Returns a list vectors associated to several row names """
	vectors = [self.rowValues[rname] for rname in rownames]
	return numpy.array(vectors)

    def remove_column(self,colname):
        """Removes the given column form the current dataset """
        col_value = self.colValues.pop(colname, None) 
        if col_value != None:
            new_indexes = range(len(self.colNames))
            index = self.colNames.index(colname)
            self.colNames.pop(index)
            new_indexes.pop(index)
            newmatrix = self.matrix.swapaxes(0,1)
            newmatrix = newmatrix[new_indexes].swapaxes(0,1)
            self._link_names2matrix(newmatrix)

    def merge_columns(self, groups, grouping_criterion):
        """ Returns a new ArrayTable object in which columns are
        merged according to a given criterion. 

	'groups' argument must be a dictionary in which keys are the
        new column names, and each value is the list of current
        column names to be merged.

	'grouping_criterion' must be 'min', 'max' or 'mean', and
	defines how numeric values will be merged.

	Example: 
           my_groups = {'NewColumn':['column5', 'column6']}
	   new_Array = Array.merge_columns(my_groups, 'max')

	"""

        if grouping_criterion == "max":
            grouping_f = get_max_vector
        elif grouping_criterion == "min":
            grouping_f = get_min_vector
        elif grouping_criterion == "mean":
            grouping_f = get_mean_vector
        else:
            raise 'ValueError', "grouping_criterion not supported. Use max|min|mean "

        grouped_array = self.__class__()
        grouped_matrix = []
        colNames = []
        for gname,tnames in groups.iteritems():
            all_vectors=[]
            for tn in tnames:
                if tn not in self.colValues: 
                    logger(0, tn,"not found in original dataset. Skipped")
                    continue
                vector = self.get_column_vector(tn).astype(int)
                all_vectors.append(vector)
            # Store the group vector = max expression of all items in group
            if len(all_vectors)>0:
                grouped_matrix.append(grouping_f(all_vectors))
                # store group name
                colNames.append(gname)
            else:
                logger(0, gname, "is missing. Skipped")

        grouped_array.rowNames= self.rowNames
        grouped_array.colNames= colNames
        vmatrix = numpy.array(grouped_matrix).transpose()
        grouped_array._link_names2matrix(vmatrix)
        return grouped_array

    def transpose(self):
	""" Returns a new ArrayTable in which current matrix is transposed. """

        transposedA = self.__class__()
        transposedM = self.matrix.transpose()
        transposedA.colNames = list(self.rowNames)
        transposedA.rowNames = list(self.colNames)
        transposedA._link_names2matrix(transposedM)

        # Check that everything is ok
        # for n in self.colNames:
        #     print self.get_column_vector(n) ==  transposedA.get_row_vector(n)
        # for n in self.rowNames:
        #     print self.get_row_vector(n) ==  transposedA.get_column_vector(n)
        return transposedA

    def _link_names2matrix(self, m):
	""" Synchronize curent column and row names to the given matrix"""
	if len(self.rowNames) != m.shape[0]:
	    raise 'ValueError' , "Expecting matrix with  %d rows" % m.size[0]

	if len(self.colNames) != m.shape[1]:
	    raise 'ValueError' , "Expecting matrix with  %d columns" % m.size[1]

	self.matrix = m
	self.colValues.clear()
	self.rowValues.clear()
	# link columns names to vectors
	i = 0
	for colname in self.colNames:
	    self.colValues[colname] = self.matrix[:,i]
	    i+=1
	# link row names to vectors
	i = 0
	for rowname in self.rowNames:
	    self.rowValues[rowname] = self.matrix[i,:]
	    i+=1

def get_centroid_dist(vcenter,vlist,fdist):
    d = 0.0
    for v in vlist:
        d += fdist(v,vcenter)
    return 2*(d / len(vlist))

def get_average_centroid_linkage_dist(vcenter1,vlist1,vcenter2,vlist2,fdist):
    d1,d2 = 0.0, 0.0
    for v in vlist1:
        d1 += fdist(v,vcenter2)
    for v in vlist2:
        d2 += fdist(v,vcenter1)
    return (d1+d2) / (len(vlist1)+len(vlist2))

def safe_mean(values):
    """ Returns mean value discarding non finite values """
    valid_values = []
    for v in values:
        if numpy.isfinite(v):
            valid_values.append(v)
    return numpy.mean(valid_values), numpy.std(valid_values)

def safe_mean_vector(vectors):
    """ Returns mean profile discarding non finite values """
    # if only one vector, avg = itself
    if len(vectors)==1:
        return vectors[0], numpy.zeros(len(vectors[0]))
    # Takes the vector length form the first item
    length = len(vectors[0])
    
    safe_mean = []
    safe_std  = []
    
    for pos in xrange(length):
        pos_mean = []
        for v in vectors:
            if numpy.isfinite(v[pos]):
                pos_mean.append(v[pos])
        safe_mean.append(numpy.mean(pos_mean))
        safe_std.append(numpy.std(pos_mean))
    return safe_mean, safe_std

# ####################
# distance functions
# ####################

def pearson_dist(v1,v2):
    if (v1 == v2).all(): 
        return 0.0
    else:
        return 1.0 - stats.pearsonr(v1,v2)[0]

def spearman_dist(v1,v2):
    if (v1 == v2).all(): 
        return 0.0
    else:
        return 1.0 - stats.spearmanr(v1,v2)[0]

def euclidean_dist(v1,v2):
    if (v1 == v2).all(): 
        return 0.0
    else:
        return math.sqrt( square_euclidean_dist(v1,v2) )

def get_mean_vector(vlist):
    a = numpy.array(vlist)
    return numpy.mean(a,0)

def get_median_vector(vlist):
    a = numpy.array(vlist)
    return numpy.median(a)

def get_max_vector(vlist):
    a = numpy.array(vlist)
    return numpy.max(a,0)

def get_min_vector(vlist):
    a = numpy.array(vlist)
    return numpy.min(a,0)


def square_euclidean_dist(v1,v2):
    if (v1 == v2).all(): 
        return 0.0
    valids  = 0
    distance= 0.0
    for i in xrange(len(v1)):
        if numpy.isfinite(v1[i]) and numpy.isfinite(v2[i]):
            valids += 1
            d = v1[i]-v2[i]
            distance += d*d
    if valids==0:
        raise ValueError, "Cannot calculate values"
    return  distance/valids

__version__="1.0rev95"
__author__="Jaime Huerta-Cepas"