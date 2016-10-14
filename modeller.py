#!/usr/bin/env python 
# -*- coding: utf-8 -*-
import sys
import argparse
import logging
import json 
import os
from random import shuffle
from gensim.models.doc2vec import LabeledSentence
from gensim.models import Doc2Vec
from sklearn.cross_validation import train_test_split
from reader import MongoReader
import numpy as np 

logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)
logging.root.level = logging.INFO


class BuildDoc2VecModel(object):
    ''' Build Doc2Vec model file. 
    '''
    def __init__(self, fileoutput, dm=0, size=150, negative=5, hs=0, min_count=2, 
                 workers=3, numpasses=10, numiter=10):
        ''' init
            :param fileoutput: output model file
            :param dm: defines the algorithm. 0 = PV-DBOW, 1 = PV-DM . default=0
            :param size: the dimensionality of the feature vectors. default=100.
            :param negative: if > 0, negative sampling will be used, the int for negative 
                             specifies how many “noise words” should be drawn
            :param hs: if 0 (default), hierarchical sampling will not be used
            :param min_count: ignore all words with total frequency lower than this
            :param worker: threads to train the model
            :param numpasees: number of passes
            :param numiter: number of iteration 
        '''
        self.fileoutput = fileoutput
        self.dm=dm
        self.size = size
        self.negative = negative
        self.hs = hs
        self.min_count = min_count
        self.workers = workers
        self.numpasses = numpasses
        self.numiter = numiter

        self.d2v_model = None
        self.test_sents = None

    def build(self, reader):
        ''' Build model
            :param reader: source Reader object
        '''
        sentences = [LabeledSentence(words=doc.get('texts'), tags=doc.get('tags')) for doc in reader.iterate()] 
        # Split model into 90/10 training and test
        train_sents, self.test_sents = train_test_split(sentences, test_size=0.1, random_state=42) 

        model= Doc2Vec(dm=self.dm, 
                       size=self.size,
                       negative=self.negative, 
                       hs=self.hs, 
                       min_count=self.min_count, 
                       workers=self.workers,
                       iter=self.numiter)

        model.build_vocab(sentences)

        alpha = 0.025
        min_alpha = 0.001
        alpha_delta = (alpha - min_alpha) / self.numpasses

        for i in xrange(self.numpasses):
            shuffle(sentences)
            model.alpha = alpha
            model.min_alpha = alpha
            model.train(sentences)
            alpha -= alpha_delta

        model.save(self.fileoutput)
        self.d2v_model = model
        self.sentences = sentences
        return 

    def score_similiarity(self):
        ''' Test similarity using Jaccard
        '''
        score = 0.0 
        for test_sent in self.test_sents: 
            pred_vec = self.d2v_model.infer_vector(test_sent.words)
            pred_tags = self.d2v_model.docvecs.most_similar([pred_vec], topn=3)
            sim = jaccard_similarity(test_sent.tags, [x[0] for x in pred_tags])
            score += sim

        print "Jaccard similarity score: ", score/len(self.test_sents)

    def sample_test(self):
        # print out random test result
        sentences = self.sentences
        model = self.d2v_model
        for i in range(15):
            docid = np.random.randint(len(sentences))
            pred_vec = model.infer_vector(sentences[docid].words)
            actual_tags=sentences[docid].tags
            #actual_tags = map(lambda x: unmark_tag(x), sentences[docid].tags)
            pred_tags = model.docvecs.most_similar([pred_vec], topn=3)
            print "Plots: %s" % (self.sentences[docid].words)
            #print "Tokens: %s" % (orig_tokens[docid])
            print "... Actual tags: %s" % (", ".join(actual_tags))
            #print "... Predicted tags:", map(lambda x: (unmark_tag(x[0]), x[1]), pred_tags)
            print "... Predicted tags:", pred_tags
            print "==="
        return 

def jaccard_similarity(labels, preds):
    lset = set(labels)
    pset = set(preds)
    return len(lset.intersection(pset)) / len(lset.union(pset))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Doc2Vec model builder.")
    parser.add_argument('--model', help="Specify output model file. default: doc2vec.model", default="./doc2vec.model")
    parser.add_argument('--db', help="Specify MongoDB db name.")
    parser.add_argument('--coll', help="Specify MongoDB collection name.")
    parser.add_argument('--mongoURI', help="Specify MongoDB URI for different server/ports. default=localhost:27017", default="mongodb://localhost:27017")
    parser.add_argument('--limit', help="Specify the limit of records to read from source. default: None", type=int, default=None)

    parser.add_argument('--featsize', help="Specify number of feature vectors. default 150", type=int, default=150)
    parser.add_argument('--negative', help="Specify how many noise words should be drawn for negative sampling.", type=int, default=5)
    parser.add_argument('--hsampling', help="Specify flag for hierarchy sampling. 0/1", type=int, default=0)
    parser.add_argument('--mincount', help="Specify the minimum words frequency to be accounted", type=int, default=2)
    parser.add_argument('--workers', help="Specify the number of workers for training models", type=int, default=1)
    parser.add_argument('--numpasses', help="Specify number of passes/iteration", type=int, default=20)

    args = parser.parse_args()
    if not (args.db or args.coll):
        parser.print_help()
        sys.exit(1)

    builder = BuildDoc2VecModel(fileoutput=args.model)
    reader = MongoReader(mongoURI=args.mongoURI, dbName=args.db, collName=args.coll, limit=args.limit)
    builder.build(reader)
    builder.score_similiarity()
    builder.sample_test()


if __name__ == "__main__":
    pass