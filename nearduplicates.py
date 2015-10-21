# -*- coding: utf-8 -*-
import time
import os,sys
import itertools
import math
import argparse
import numpy as np
from multiprocessing import Pool
from hashlib import sha1
from datasketch import MinHash
import random, struct
from random import sample,choice
from sklearn import metrics

NUM_PERM=100

#use 32-bit hashing
M_PRIME = (1 << 61) - 1
MAX_HASH = (1 << 32) - 1

random.seed(427)
A,B = np.array([(random.randint(1, M_PRIME),random.randint(0, M_PRIME)) for _ in range(NUM_PERM)]).T

#############
# functions #
#############

def get_permuted_hashes(token):
    # get a hash value
    hv = struct.unpack('<I', sha1(token).digest()[:4])[0]
    #do random bijective permutation
    return np.bitwise_and((A * hv + B) % M_PRIME,MAX_HASH)

def get_lsh(sig,nbands):
    for i,band in enumerate(np.array_split(sig,nbands)):
        yield sha1("ab" + unicode(band) + "ba"+unicode(i)).digest()
         
def get_bandwidth(n, tr):
        """
        Threshold tr = (1/b) ** (1/r) where
        b #bands
        r #rows per band
        n = b * r  #elements in signature
        """
        best = n, 1
        minerr  = float("inf")
        for r in xrange(1, n + 1):
            try:
                b = 1. / (tr ** r)
            except: 
                return best
            err = abs(n - b * r)
            if err < minerr:
                best = r
                minerr = err
        return best

def jaccard(h1,h2):
    '''
    Compute jaccard similarity between two minhash signatures.
    Make sure to only compute jaccard similarity for hashes created with same hash functions (i.e. same seed for random permutation)
    '''
    return np.float(np.count_nonzero(h1==h2)) /np.float(h2.size)

def run_jaccard_list(obj):
    '''
    compute jaccard similarity between two hash signatures
    input:
        two hash signatures
    '''
    x1,x2=obj['signatures']
    return jaccard(np.array(x1),np.jaccard(x2))

def run_jaccard_array(obj):
    '''
    compute jaccard similarity between two hash signatures
    input:
        two hash signatures
    '''
    x1,x2=obj['signatures']
    return jaccard(x1,x2)

def connected(seed,lshdict,doc2lsh,t):
    '''
    Computes clusters based on the lsh bucket candidates.
    We do not actually check the full connected component. 
    We only check for similar docs amongst the lsh candidates for each cluster member.
    currently requires as input
        - doc2lsh: dictionary of documentID:lsh_signatures 
        - lshdict: dictionary of lsh_signature:documentIDs
        - seed: seed document id
        - threshold: jaccard similarity threshold
    output:
        -set of documentIDs
    '''
    seed = obj['seed']
    lshdict = obj['lshdict']
    doc2lsh = obj['doc2lsh']
    t= obj['threshold']
    cluster=set([seed])
    #get candidates and flatten list
    base=set([seed])
    while len(base)>0:
        s=base.pop()
        #get candidates and flatten list
        candidates=set(itertools.chain.from_iterable([lshdict[sig] for sig in doc2lsh[s]]))
        m1=hashcorp[s]
        for cand in candidates:
            if cand in cluster:continue#don't check if we've already added this
            m2=hashcorp[cand]
            if jaccard(m2,m1) >=t:
                cluster.add(cand)
                base.add(cand)
    #all candidates have been checked 
    return cluster 

def run_near_duplicates(obj):
    '''
    get near duplicates for a seed ad
    currently requires as input
        - doc2lsh: dictionary of documentID:lsh_signatures 
        - lshdict: dictionary of lsh_signature:documentIDs
        - seed: seed document id
        - threshold: jaccard similarity threshold
    output:
        -set of documentIDs
    '''
    seed = obj['seed']
    lshdict = obj['lshdict']
    doc2lsh = obj['doc2lsh']
    t= obj['threshold']
    cluster=set([seed])
    #get candidates and flatten list
    candidates=set(itertools.chain.from_iterable([lshdict[sig] for sig in doc2lsh[s]]))
    m1=hashcorp[seed]
    for cand in candidates:
        if cand in cluster:continue#don't check if we've already added this
        m2=hashcorp[cand]
        if jaccard(m2,m1) >=t:
            cluster.add(cand)
    #all candidates have been checked 
    return cluster 

def run_getminhash(obj):
    '''
    Compute minhash signatures for raw text.
    This functions takes documents and their ids as input and returns ids and the corresponding minhash signature.
    The minhash signature is a set of NUM_PERM positiv integer values created with NUM_PERM hash functions.
    The minhash signature allows for a fast Jaccard similariy estimation of two documents. 
    input:
        keys,documents (TODO define exact input. Dicionary or json.)
    output:
        dictionary of key,hashvalues (this can easily be modified to return a list of tuples or a json object) 
    '''
    #compute hashes
    hashcorp=dict.fromkeys([key for key,doc in obj['objects']])
    for key,doc in obj['objects']:
        #compute minhash signature
        hashvalues=np.empty(NUM_PERM)
        hashvalues.fill(MAX_HASH)
        for token in doc.lower().split(): 
            hashvalues = np.minimum(get_permuted_hashes(token.encode('utf-8','ignore')), hashvalues)
        #do something with the hash. save it? return it?
        hashcorp[key]=hashvalues
    return hashcorp

def run_lsh(obj):
    """
    Compute the Locality sensitive hashing signatures for a particular threshold.
    Utilize the fact that similar items generate similar hashcodes. 
    LSH signatures help to get a small set of candidates to which a document needs to be compared.
    To get an accurate estimate of Jaccard similarity, the similariy still needs to be computed using the minhash integer signature. 
    input:
        threshold (default 0.9)
        key,hashvalues
    """
    if 'threshold' in obj:
        thr=obj['threshold']
    else:
        thr=0.9
    bandwidth=get_bandwidth(NUM_PERM, thr)#r
    bands=int(math.ceil(float(NUM_PERM)/float(bandwidth)))#b
    doc_to_lsh={}
    lsh_dict={}
    for key,hashvalues in obj['hashcorp']:
        #compute lsh 
        signatures = [sig for sig in get_lsh(hashvalues,bands)]
        #store signatures for this document
        doc_to_lsh[key]=signatures
        #store lsh signature to key
        for sig in signatures:
            if sig in lsh_dict:
                lsh_dict[sig].append(key)
            else:
                lsh_dict[sig]=[key]
    return doc_to_lsh,lsh_dict



