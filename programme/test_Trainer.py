"""
AUTHOR: Tawana Kwaramba: 19476700
LAST EDITED:

PURPOSE: to  test the class of DataSet to enusre that the functionality
meets the expected functionality

TO DO:
"""

import unittest
from Trainer import *
from DataSet import *

class test_Trainer(unittest.TestCase):
    test_path = '../Digits-2020S2/'
    train_path = '../train_updated/'
    val_path = '../val_updated/'

    test = Trainer(test_path=test_path,train_path=train_path,
            val_path=val_path)

    def test_accessors(self):
        #ensuring that all the accessors return the correct type
        self.assertEqual(Data_Set,type(self.test.test_set),
                "checking types for the test set")
        self.assertEqual(Data_Set, type(self.test.train_set),
                "checking type for the train set")
        self.assertEqual(Data_Set, type(self.test.val_set),
                "checking type for the validation set")

    def test_visual_set(self):
        labels = self.test.val_set.labels

        for ii in labels:
            curr_set = self.test.val_set.set[ii]
            for jj, im in enumerate(curr_set.data):
                cv.imshow('set: %s, img %s' % (ii, jj), im)

        labels = self.test.test_set.labels

        for ii in labels:
            curr_set = self.test.test_set.set[ii]
            for jj, im in enumerate(curr_set.data):
                cv.imshow('set: %s, img %s' %(ii,jj), im)

        labels = self.test.train_set.labels

        for ii in labels:
            curr_set = self.test.train_set.set[ii]
            for jj, im in enumerate(curr_set.data):
                cv.imshow('set: %s, img %s' % (ii, jj), im)

        cv.waitKey()
