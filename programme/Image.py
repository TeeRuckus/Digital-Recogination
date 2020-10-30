"""
FILENAME:  Image.py

AUTHOR: Tawana Kwaramba: 19476700
LAST EDITED:

PURPOSE OF FILE: the purpose of this file is to facilate any based image
operations. I.e. segmeneting the image to get the region of interest, and
extracting the digits from the region of interest
"""

from abc import abstractmethod
import numpy as np
from Errors import *
from Colours import *
import cv2 as cv
from statistics import mode

class Image(object):
    def __init__(self, im, img_id):
        #set this to true, if you want to see each step of the image
        #segmentation process
        self._DEBUG = False
        self._im = self.get_ROI(im, img_id)

    #===========================ACCESORS========================================
    @property
    def im(self):
        return self._im

    @property
    def DEBUG(self):
        return self._DEBUG

    @im.setter
    def im(self, in_im):
        self._im = self.get_ROI(in_im)

    #===========================METHODS=========================================
    def debug(self):
        """
        IMPORT: none
        EXPORT: none

        PURPOSE: to act as a toggle to witch the debugging features for this
        class
        """
        if self.DEBUG:
            self._DEBUG = False
        else:
            self._DEBUG = True

    def get_ROI(self, im, img_id):
        """
        IMPORT:
            im : numpy array of data type uint8
            img_id : integer

        EXPORT:
            cropped_image : numpy array of data type uint8
            digits : numpy array of data type uint8

        PURPOSE: it's to extract the region of interest which is the area which
        contains all the house numbers in the image, and to extract each digit
        inside that cropped area
        """
        #to determine if we need to re-adjust our bounding boxes to meet the
        #sepcifications of the original images
        resized = False
        if im.shape[0] > 900 and im.shape[1] > 900:
            resized = True
            im = self.resize_image(im, 536, 884)

        #makind sure that we have actually passed in an image, and not anything
        #else
        im = self._validate_image(im)
        gray = cv.cvtColor(im, cv.COLOR_BGR2GRAY)
        #decreasing the required memory the image needs but still keeping the
        #important features of the image
        gray = cv.GaussianBlur(gray, (5,5), 0)
        #thresholding, so we can extract the background and the foreground of
        #the image
        thresh = cv.threshold(gray, 0, 255, cv.THRESH_BINARY+cv.THRESH_OTSU)[1]

        edge_thresh = 100

        #the openCV doc recommends that you will have your upper thresh hold
        #twice as the lower threshold
        canny_trans = cv.Canny(thresh, edge_thresh, edge_thresh * 2)
        #getting the shape and size of the structual element suitable to this
        #image. Hence, the window which is going over this image
        rect_kern = cv.getStructuringElement(cv.MORPH_RECT, (5,5))

        #removing the boundaries of the foreground of the image, so we can
        #have less noise around teh actual digits
        canny_trans = cv.erode(thresh, None, iterations=1)
        #the numbers are a lot smaller at this point hence, we will expand
        #those eroded boundaries in order to fill in holes, and to make the
        #number fuller
        canny_trans = cv.dilate(thresh, None, iterations=1)

        if self._DEBUG:
            cv.imshow("found edges after morphology" , canny_trans)
            cv.waitKey()
            cv.destroyAllWindows()

        mser = cv.MSER_create()
        regions, bboxes = mser.detectRegions(canny_trans)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "original bounding boxes found")

        #filtering the bounding boxes relative to the height and width. The
        #heights should be greater thna the heights
        bboxes = self.filter_bounding_boxes(bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "filtered bounding boxes")

        #the numbers should be relative close to each other hence, we're going
        #to filter out the boxes which are not close to each other
        bboxes = self.find_clusters(bboxes, 1.10, 0.25)
        #joinning those boxes which are close together, to make one section
        bboxes = self.group_clusters(bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "groups of bounding boxes found")

        #by this stage it will just be the numbers left with some noise
        #hence we're going to filter out the areas which don't align with the
        #numbers in the image
        bboxes = self.filter_areas(bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "filtering by the area")


        #when we have a zero or an eight. MSER will detect as bounding boxes
        #the reigons inside these digits. Hence, we need to remove those regions
        #so we can crop the full number successfully
        bboxes = self.non_max_suppression(bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "non max suppression")


        #the numbers should be at the relative same heights hence, remove any
        #box which doesn't agree with this height
        bboxes  = self.filter_heights(bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "filtering by the heights in image")

        #the numbers should be at the relative same widths hence, remove any box
        #which doesn't agree with this
        bboxes  = self.filter_width(bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "filtering by widths of the image")


        #by this point they're still some noise boxes left although, they're
        #more boxes which contain the number left in the image hence, we can
        #filter these boxes out given the dominant color
        bboxes = self.filter_dominant_color(im.copy(), bboxes)

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "filtering done by dominant color")


        #getting the points required to create our region of interest
        #getting the left most - upper most bounding box point
        left_pt = self.find_leftmost_pt(bboxes)
        #getting the right most lower most bounding box in the image
        right_pt = self.find_leftmost_pt(bboxes, True)


        #creating a new bounding box which will represent the region of interest
        new_region = self.make_new_region(left_pt, right_pt)
        cropped_image = self.crop_img(im.copy(),new_region)
        #a padding is needed for better digit detection. If the digit is a
        #part of the border in some cases that part won't be detected by
        #MSER
        cropped_image = self.pad_image(cropped_image)

        digits = self.extract_digits(cropped_image)

        file_name = 'output/DetectedArea' + str(img_id) + ".jpg"
        bbox_file_name = 'output/BoundingBox' +str(img_id) + ".txt"

        cv.imwrite(file_name, cropped_image)
        np.savetxt(bbox_file_name, [new_region], delimiter=',')

        if self._DEBUG:
            self.show_debug_boxes([new_region], im, "new region found")

        if self._DEBUG:
            cv.imshow("extracted area", cropped_image)
            cv.waitKey()
            cv.destroyAllWindows()

        return cropped_image, digits

    def extract_digits(self, im):
        """
        IMPORT:
                im : numpy array array datatype of uint8
        EXPORT:
            list of numpy arrays of datatypes of uint8

        PURPOSE: is to get the region of interest produced by the image, and
        to extract the individual digits out of this image
        """

        im = self._validate_image(im)
        gray = cv.cvtColor(im, cv.COLOR_BGR2GRAY)
        #decreasing the required memory the image needs but still keeping the
        #important features of the image
        gray = cv.GaussianBlur(gray, (5,5), 0)
        #thresholding, so we can extract the background and the foreground of
        #the image
        thresh = cv.threshold(gray, 0, 255, cv.THRESH_BINARY+cv.THRESH_OTSU)[1]

        edge_thresh = 100
        #the openCV doc recommends that you will have your upper thresh hold
        #twice as the lower threshold
        canny_trans = cv.Canny(thresh, edge_thresh, edge_thresh * 2)
        rect_kern = cv.getStructuringElement(cv.MORPH_RECT, (5,5))
        canny_trans = cv.erode(thresh, None, iterations=1)
        canny_trans = cv.dilate(thresh, None, iterations=1)
        #canny_trans_invert = canny_trans.max() - canny_trans

        if self._DEBUG:
            cv.imshow("found edges after morphology" , canny_trans)
            #cv.imshow("the inversion of that image", canny_trans_invert)
            cv.waitKey()
            cv.destroyAllWindows()

        mser = cv.MSER_create()
        regions, bboxes = mser.detectRegions(canny_trans)
        #trying to filter the bounding boxes in relation to the heights, and the width

        if self._DEBUG:
            self.show_debug_boxes(bboxes, im, "original bounding boxes found")

        bboxes = self.filter_bounding_boxes(bboxes, 1.1, 4.8)
        bboxes = self.non_max_suppression(bboxes)
        #sorting the bounding boxes so they read left to right, and it's
        #displayed in the right order
        bboxes = sorted(bboxes, key=lambda x: x[0])

        return [self.crop_img(im.copy(), box) for box in bboxes]

    def pad_image(self, im):
        """
        IMPORT: im : numpy array of datatype unit8
        EXPORT: padded image: numpy array of datatype unit8

        PURPOSE: it's to place a black padding around an image, so that
        the numbers of the image don't become a part of the border
        """

        #number of pixels which we want to pad the image with all around
        row_pad = 2
        col_pad = 2
        npad = ((row_pad, col_pad), (row_pad, col_pad), (0,0))
        return np.pad(im, pad_width=npad, mode='constant', constant_values=0)

    def filter_heights(self, bboxes):
        """
        IMPORT: bboxes : numpy of array of dtype int32
        EXPORT: bboxes numpy of array of dtype int32

        PURPOSE: to filter out the bounding boxes by height so the bounding
        boxes which are relativily around the same height will remain in
        the image
        """
        #sorting the bounding boxes in relation to the poistion on the image.
        #placing the upper most box first in the bboxes list and the lowest
        #box last in the list
        bboxes = sorted(bboxes, key=lambda y: y[1])
        #just creating a list which only contains the heights of the bounding
        #boxes
        heights = [box[1] for box in bboxes]
        #finding the median height of the bounding boxes
        common_height =  np.median(heights)

        #grabbing the bounding box with the lowest height in the image
        #and grabbing its width
        TOL = bboxes[-1][3]

        for indx, box in enumerate(bboxes):
            #a safe gaurd to make sure that we don't try to access an invalid
            #index of the bounding boxes
            if indx < len(bboxes):
                #remove the bounding boxes which are not about the
                #same height as the median value of the bounding boxes
                if (abs(box[1] - common_height)) >= TOL:
                    #you don't want to delete the elements as yet, as
                    #that will make the array smaller, and will cause
                    #python to try to access an index which is out of range
                    bboxes[indx] = [-1,-1,-1,-1]

        bboxes = self.remove_invalid(bboxes)

        return bboxes

    def filter_width(self, bboxes):
        """
        IMPORT: bboxes  : numpy array of datatype int32
        EXPORT: bboxes  : numpy array of datatype int32

        PURPOSE: the purpose is to filter out boxes which are not
        relatively close to each other in the provided bounding boxes as
        these points are most likely going to be noise in the image
        """
        #sorting the bounding boxes so we can access the boxes from
        #left to the right side of the image
        bboxes = sorted(bboxes, key=lambda x: x[0])
        #grabbing just the widths of all the bounding boxes in the image
        widths = [box[0] for box in bboxes]

        #the numbers in the image should be the middle number by this stage
        common_width = np.median(widths)

        #grabbing the right most box
        TOL = bboxes[-1][2] * 4

        for indx, box in enumerate(bboxes):
            #a safe gaurd to ensure the algorithm doesn't try to index
            #outside of the list
            if indx < len(bboxes):
                if (abs(box[0] - common_width)) >= TOL:
                    #you don't want to delete the elements as yet, as
                    #that will make the array smaller, and will cause
                    #python to try to access an index which is out of range
                    bboxes[indx] = [-1,-1,-1,-1]


        bboxes = self.remove_invalid(bboxes)

        return bboxes


    def filter_dominant_color(self, img, bboxes):
        """
        IMPORT:
                 img : numpy array of dataype uint8
                 bboxes: numpy array of datatype int32

        EXPORT: bboxes : numy array of dataype int32

        PURPOSE: the idea is that the numbers should be on the same
        coloured background and the numbers should be the same color aswell
        and the dominant color should be either the background or
        the foreground of the image. Hence, filter away any box which
        are not the same color as the numbers
        """
        #normalising the image, removing any effects from brightness and
        # contrast
        img = cv.normalize(img, img, 0, 255, cv.NORM_MINMAX)
        #best color space to use from experimenting
        img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        img_sections = []

        for box in bboxes:
            #creating a list of images of wahtever is inside the bounding
            #boxes found in the image
            img_sections.append(self.crop_img(img.copy(), box))

        section_colors = []
        for section in img_sections:
            #finding the dominant color in each of those cropped sections
            #before
            section_colors.append(self.find_dominant_color(section))

        #if they is any invalid data remove it from the section colors
        #list
        section_colors = self.remove_invalid(section_colors)
        #go throught the list of dominant colors and find the most
        #occurring color in that given list
        dominant_color = self.find_dominant_color_ls(section_colors)

        #this gave the best results  so far from trial and error of multiple
        #values
        TOL = [25, 25, 25]

        #anything which doesn't have this dominant color should be deleted in
        for indx, color in enumerate(section_colors):
            #safe gaurd to try stop the algorithm from accessing an invalid index
            if  indx < len(section_colors):
                if (abs(color - dominant_color) > TOL).all():
                    #deleting the bounding box which doesn't have the dominant color
                    #in it
                    bboxes[indx] = [-1,-1,-1,-1]

        bboxes = self.remove_invalid(bboxes)

        return bboxes

    def find_dominant_color(self, img):
        #THIS IS ACTUALLY FINDING THE DOMINANT COLOR WITH OPENCV
        """
        use the refernce which you used for assigment one for this
        """
        #they should be only two colors the background and the foreground of
        #the plate
        #img = cv.cvtColor(img.copy(), cv.COLOR_BGR2HSV)

        #pixels = np.float32(img.reshape(-1,3))
        pixels = np.float32(img.flatten())
        n_colors = 2

        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 200, 1)
        #flags = cv.KMEANS_RANDOM_CENTERS
        flags = cv.KMEANS_PP_CENTERS

        labels, palette  = cv.kmeans(pixels, n_colors, None, criteria, 10,
                flags)[1:]

        counts = np.unique(labels, return_counts=True)[1]

        return palette[np.argmax(counts)]

    def find_dominant_color_ls(self, color_ls):
        """
        to find the domiannt color given a list. This algorihtm is going to use
        brute force to find the dominant color, and therefore is going to be
        in-efficient
        """

        temp_color = None
        prev_found_times = 0
        found_times = 0

        for color in color_ls:
            temp_color = color
            for count in color_ls:
                if (count == temp_color).all():
                    found_times += 1

            if  found_times >= prev_found_times:
                dominant_color = color
                prev_found_times = found_times
                found_times = 0

        return dominant_color


    def crop_img(self, img, bbox):
        #want to make sure that extracted area has padding so it will be easier
        #to detect the digits in the next sections of the programme
        padding = 0  # this caused one of your indexes to be invalid
        x_l = int(bbox[0] - padding)
        y_l = int(bbox[1] - padding)
        x_r = int(bbox[0] + bbox[2] + padding)
        y_r = int(bbox[1] + bbox[3] + padding)

        return img[y_l:y_r, x_l:x_r]


    def filter_areas(self, bboxes):
        all_areas = []
        #getting all the areas of each bounding box in the image, so I can
        #fileter out the boxes which are most likely going to be outliers
        for box in bboxes:
            all_areas.append(self.find_area(box))
        bboxes = self.remove_outliers(all_areas, bboxes)

        return bboxes

    def get_five_num_summary(self, area_ls):
        min_area, max_area = min(area_ls), max(area_ls)
        percentiles = np.percentile(area_ls, [25, 50, 75])
        #average = np.mean(area_ls)
        summary = [min_area, percentiles[0], percentiles[1], percentiles[2],
                max_area]
        #return min_area, max_area, median, average
        return summary

    def sort_bboxes(self, sorted_indxs, bboxes):
        temp_bboxes = bboxes.copy()
        for indx, box in enumerate(temp_bboxes):
            bboxes[indx] = temp_bboxes[sorted_indxs[indx]]

        return bboxes

    def remove_outliers(self, area_ls, bboxes):
        """
        an outlier is a point which will lay siginificantly far away from the
        average
        """
        area_ls = np.array(area_ls)
        sorted_indxs = area_ls.argsort()

        bboxes = self.sort_bboxes(sorted_indxs, bboxes)
        #actually puting the areas in their sorted order
        area_ls = area_ls[sorted_indxs]
        #converting area_list back to a list so I can use the in-built list
        #functions
        area_ls = area_ls.tolist()


        #if they're going to be only two boxes in the bounding box array
        #they is not point in trying to find the outliers, as one of those
        #boxes will be filtered out which is not what we want
        if len(bboxes) > 3:
            #ordering the areas from the smallest area to the largest area
            #area_ls = sorted(area_ls, key=lambda a: a[0])
            #area_ls.sort()
            num_summary = self.get_five_num_summary(area_ls)
            IQR = self.find_IQR(num_summary)
            median = num_summary[2]
            #PLAY AROUND WITH THIS THRESH HOLD
            #the numbers are most likely going to be a similiar size to the
            #median value
            #thresh = 1.05
            #thresh = 1.15
            #this as the lower thereshold worked pretty well
            #thresh_lower = 1.25
            #thresh_lower = 1.50 #here it started dropping numbers out of the
            #detected numbers, so maybe try to go down from here
            #obtained through trial and error through all the images
            thresh_lower = 1.45
            #obtained through trial and error
            thresh_upper = 0.75
            #
            #tr09.jpgtr09.jpgthresh = 1.20
            #area can't be a negative number hence,
            lower_bound = abs(int(median - (thresh_lower * IQR)))
            upper_bound = int(median + (thresh_upper * IQR))

            for area in area_ls:
                #YOU MIGHT HAVE TO BE CAREFUL ABOUT INDX GOING OUT OF RANGE: PLEASE
                #DON'T FORGET TO PUT A GUARD HERE
                indx = area_ls.index(area)

                if area < lower_bound:
                    #I am going to set the index of the outlier indexes to -1 because
                    #if I delete the index straight away it will be hard to keep a
                    #track on which index belongs to which index in the lists
                    bboxes[indx] = [-1, -1, -1, -1]

                if area > upper_bound:
                    #same reasoning applied above applies here aswell
                    bboxes[indx] = [-1, -1, -1, -1]

            bboxes = self.remove_invalid(bboxes)

        return  bboxes


    def find_IQR(self, num_summary):
        """
        finding the inter-quartile range of the obtained data, so we can
        filter out the outliers in the data
        """

        #IQR is the difference between the lower  25 percent quartle, and the
        #upper 75 percent quartile
        IQR = num_summary[3] - num_summary[1]
        return IQR




        for indx, area in enumerate(bboxes):
            pass

    def find_area(self, box):
        """
        regardless of the poisiton of the box the area is going to be always
        w * h
        """
        return box[2] * box[3]

    def non_max_suppression(self, bboxes):
        #sorting boxes by the smallest area to the largest area
        #bboxes = sorted(bboxes, key=lambda area:  bboxes[2] * bboxes[3])
        bboxes = sorted(bboxes, key=lambda x: self.find_area(x))

        ##searching for boxes which are inside one another
        for curr_box_indx, curr_box in enumerate(bboxes):
            x,y,w,h = curr_box
            #ensuring that the algorithm is not comparing to itself, and it's
            #searching relative to the other boxes
            #search_space = bboxes[curr_box_indx:]
            for alt_box in bboxes:
            #for alt_box in search_space:
                #safe-gaurd for trying to delete an index which doesn't
                #exist in the image
                if curr_box_indx < len(bboxes):
                    #is the current box inside any of the alternate boxes
                    x_alt,y_alt,w_alt,h_alt = alt_box
                    end_point_curr_box = x + w
                    end_point_alt_box  = x_alt + w_alt
                    #is the end point of the current box inside the alternate
                    #box and is the beggining x point inside the alternate box
                    #aswell

                    #THIS SHIT IS NEW
#                    diff_end_points = (end_point_curr_box -
#                            end_point_alt_box)
                    #diff_end_points = (end_point_alt_box - end_point_curr_box)

                    if x > x_alt and end_point_curr_box < end_point_alt_box:
                    #if diff_end_points > padding:
                        #is the height of the current box inside the alternate
                        #box
                        height_curr_box = y + h
                        height_alt_box = y_alt + h_alt
#                        height_curr_box_end = end_point_curr_box + h
#                        height_alt_box_end = end_point_alt_box + h_alt

                        #THIS SHIT IS NEW
#                        diff_height_upper = (height_curr_box - height_alt_box)
#                        diff_height_lower = (height_curr_box_end -
#                                height_alt_box_end)
#                        diff_height_upper = (height_alt_box - height_curr_box)
#                        diff_height_lower = (height_alt_box_end -
#                                height_curr_box_end)

                        if height_curr_box < height_alt_box and \
                                y > y_alt:
#                        if height_curr_box < height_alt_box and \
#                        height_curr_box_end > height_alt_box:
#                        if diff_height_upper > padding and \
#                        diff_height_lower > padding:
                            #current box is insde another box, we don't need
                            #this box so we can delete it
                            del bboxes[curr_box_indx]

        return bboxes



    def area_bboxes(self, bboxes):
        #regardless where the bounding box is located the area is always
        #going to be w * h
        return bboxes[2] * bboxes[3]

    def make_new_region(self, left_box, right_box):
        #top left corner of the left-most upper most point in the image
        #coordinates
        x = left_box[0]
        y = left_box[1]

        #right most lower most corner in the image coordiantes
        x_r =  right_box[0] + right_box[2]
        y_r = right_box[1] + right_box[3]

        w = x_r - x
        h = y_r - y

        return np.array([x, y, w, h], dtype='int32')



    def show_debug_boxes(self, bboxes, im, title):
            debug_im = im.copy()
            blue = (255,0,0)
            self.draw_boxes(bboxes, debug_im, blue)
            cv.imshow(title, debug_im)
            cv.waitKey()
            cv.destroyAllWindows()

    #FUNCTIONS WHICH WILL HELP TO FIND THE INTEREST AREA
    def resize_image(self, im, x, y):
        return cv.resize(im, (int(x), int(y)))

#    def group_clusters(self, clusters):
#        pass
#
#
#    def find_clusters(self,bboxes, thresh_x, thresh_y):
#        """
#        """
#
#        cluster_ls = []
#
#        bboxes = sorted(bboxes, key=lambda x: x[0])
#        bboxes = self.remove_invalid(bboxes)
#
#        for start, curr_box in enumerate(bboxes):
#            x,y,w,h = curr_box
#            pt1 = (x,y)
#            pt2 = (x+w, y+h)
#
#            for alt_box in bboxes:
#                x_alt, y_alt, w_alt, h_alt = alt_box
#                pt1_alt = (x_alt, y_alt)
#                pt2_alt = (x_alt + w_alt, y_alt + h_alt)

    def group_clusters(self, clusters):
        """
        many boxes where founf by the find_clusters algorithm, this function
        responsibility it to clean up the bounding boxes found hence, to select
        the biggest box out of the cluster
        """
        cluster_b = []
        #NEW
        #the bboxes are put into pairs whereby each pair is very close to each
        #other hence, we can just sort by first box as that box will be
        #left most box out of the two boxes
        clusters = sorted(clusters, key=lambda x: x[0][0])

        for indx, cluster in enumerate(clusters):
            box_one = cluster[0]
            box_two = cluster[1]

            x_1, y_1, w_1, h_1 = box_one
            x_2, y_2, w_2, h_2 = box_two

            #getting the longer lines out of the two boxes parsed in
            nw_h = max(h_1, h_2)
            nw_w = max(w_1, w_2)

            #getting the left-most x and y points so we know where the clusters
            #are going to begin
            nw_x = min(x_1, x_2)
            nw_y = min(y_1, y_2)


            nw_box = np.array([nw_x, nw_y, nw_w, nw_h], dtype='int32')
            clusters[indx] = nw_box

            #I have finished analysing the search space now, I want ot move onto
            #the next pair. This is to avoid dupilcates, and doubling up
            #of parameters in the programme
        return clusters

    def  find_clusters(self, bboxes, thresh_x, thresh_y):
        """
        the numbers which are in the image should be relatively close to each
        other hence, we're going to get rid of all the boxes which are not
        close to each other because the chance of these boxes not been a number
        is very high
        """
        cluster = []

        bboxes = sorted(bboxes, key=lambda x: x[0])
        bboxes = self.remove_invalid(bboxes)

        for start, curr_box in enumerate(bboxes):
            x,y,w,h = curr_box
            pt1 = (x, y)
            pt2 = (x+w, y+h)
            #search_region = bboxes[start:]
            for alt_box in bboxes:
                #if len(search_region) > 0:
                x_alt,y_alt,w_alt,h_alt = alt_box
                pt1_alt = (x_alt,y_alt)
                pt2_alt =(x_alt+w_alt, y_alt+h_alt)

                x_diff = abs(pt2[0] - pt1_alt[0])
                y_diff = abs(pt2[1] - pt2_alt[1])
                #y_diff = abs(pt1[1] - pt1_alt[1])

#                    line_seg_x = max(pt2[0], pt2_alt[0])
#                    line_seg_y = max(pt2[1], pt2_alt[1])
                line_seg_x = max(w, w_alt)
                line_seg_y = max(h, h_alt)

                line_TOL_x  = line_seg_x * thresh_x
                line_TOL_y = line_seg_y * thresh_y

                #if x_diff < pt2[0]  and x_diff < pt2_alt[0]:
                #I don't think you're doing this comparison correctly if I
                #am being honest
                if x_diff <= line_TOL_x:
                        #if y_diff < h:
                        if y_diff <= line_TOL_y:
                            pair = [curr_box, alt_box]
                            pair = sorted(pair, key=lambda x: x[0])
                            cluster.append([curr_box, alt_box])
        return cluster

    def filter_bounding_boxes(self, bboxes, lower_thresh=1.10, upper_thresh=3.21):
        """
        we know that for the bounding boxes which will contain the digits
        the height is going to be longer than the width
        """
        #NEW
        bboxes = sorted(bboxes, key=lambda x: x[0])

        for indx, box in  enumerate(bboxes):
            x,y,w,h = box
            pt1 = (x, y)
            pt2 = (x+w, y+h)

            #if (abs(pt1[0] - pt2[0]) >= abs(pt1[1] - pt2[1])):
            if w >= h:
                bboxes[indx] = [-1, -1, -1, -1]

            ratio = h/w
            #we're going to expect the height of the digits to be no more than
            #250% of the widht of the image, and the length to be no less
            #than the width of the bounding box
            #if ratio < 1.10 or ratio > 3.21:
            if ratio < lower_thresh or ratio > upper_thresh:
            #if ratio <= 1.5 or ratio >= 2.0:
            #if ratio < 1.0 and ratio > 2.0:
                bboxes[indx]  = [-1, -1, -1, -1]

        bboxes = self.remove_invalid(bboxes)

        return bboxes

    def draw_boxes(self,bboxes, im, color):
        for box in bboxes:
            if box[0] == -1:
                pass
            else:
                x,y,w,h = box
                cv.rectangle(im, (x,y), (x+w, y+h), color, 1)

    def find_leftmost_pt(self, bboxes, reverse=False):
        """
        if reverse is true, it will find the right-most lower most point of the
        bounding boxes

        Notes:
            - if a box is inside another box, it's going to find the box  inside
            because it's comparing in relation to the left point of the box
        """
        bboxes = self.remove_invalid(bboxes)
        left_most_boxes = sorted(bboxes, key=lambda x: x[0], reverse=reverse)

        temp_box = left_most_boxes[0]

        #CASE 1: clear left most box will be met if it fails CASE 2's and
        #CASE 3's checks

        #CASE 2: boxes are the same x-coordinate hence to enusre that
        #the upper-most box is selected
        for box in left_most_boxes:
            #case: when two boxes have the same x-dimension but differing
            #y-dimensions
            if temp_box[0] == box[0]:
                if temp_box[1] > box[1]:
                    temp_box = box

        #CASE 3: the left most box is selected but if they's a box which is
        #higher than the current box combine find the intersecting points
        highest_boxes = sorted(bboxes, key=lambda y: y[1], reverse=reverse)
        highest_box = highest_boxes[0]

        equal = highest_box == temp_box
        #if the current box is not the highest box, form an intersection
        #with the highest box
        if not equal.all():
            temp_box = self.find_intersection(highest_box, temp_box,
                    reverse=reverse)

        if self._DEBUG:
            print('='*80)
            print(red, 'find_leftmost_p() | temp box',reset)
            print('\t {}'.format(temp_box))
            print('='*80)

        return temp_box[0], temp_box[1], temp_box[2], temp_box[3]

    def remove_invalid(self, bboxes):
        if self._DEBUG:
            print('='*80)
            print(red + "og array" + reset, bboxes)
            print('='*80)


        nw_bboxes = []
        for indx, box in enumerate(bboxes):
            #if the first index is equal to -1 the whole box will equal to -1,
            #and that will be an invalid box
            if box[0] == -1:
                pass
            else:
                nw_bboxes.append(box)


        #converting the new list into an array, so openCV function can use
        #this array to draw the boxes
        bboxes = np.array(nw_bboxes, dtype='int32')

        if self._DEBUG:
            print('='*80)
            print(red + "resultant array" +reset, bboxes)
            print('='*80)

        return bboxes

    def find_intersection(self, box_one, box_two, reverse=False):
        """
        IMPORT:
        EXPORT:

        PURPOSE
            if you're trying to find the right most corner, set reverse to
            true, and add the width, and the height of the object of interset
        """
        temp_boxes = [box_one, box_two]
        #placing the box with the lowest x value at the front
        temp_boxes = sorted(temp_boxes, key=lambda x: x[0], reverse=reverse)
        #the first boxes x coordinate
        nw_x = temp_boxes[0][0]
        #the right most point will be the temp box's in reverse, and it
        #will be the that boxes x value plus that boxes w value
        nw_w = temp_boxes[0][2]
        #placing the box withthe lowest y value at the front
        temp_boxes = sorted(temp_boxes, key=lambda  y: y[1], reverse=reverse)
        #the first boxes y coordinate
        nw_y = temp_boxes[0][1]
        #the right most point will be the temp boxes in reverse, and it
        #will be that  box's y value plus box's h value
        nw_h = temp_boxes[0][3]

        if self._DEBUG:
            print('='* 80)
            print(red, 'find_intersection() | interesction',reset)
            print('\t {}, {}, {}, {}'.format(nw_x, nw_y, nw_w, nw_h))
            print('='* 80)

        return nw_x, nw_y, nw_w, nw_h

    def draw_boxes(self, bboxes, im, color=(0,0,255)):
        """
        IMPORT:
        EXPORT:

        PURPOSE: it's to draw a bounding box which is either a shape of a
        rectangle or a square
        """
        for box in bboxes:
            #if the box has been labelled by a negative -1 by a filtering
            #algorithm we should skip over this box
            if box[0] == -1:
                pass
            else:
                x,y,w,h = box
                cv.rectangle(im, (x,y), (x+w, y+h), color, 2)

    def _validate_image(self, in_im):
        #an image is going to be an numpy matrice
        if not type(in_im) == np.ndarray:
            #all loaded images, are an unsigned interger by defualt
            if not in_im.dtype == 'uint8':
                raise ImageError("Error: an image wasn't laoded in the system")

        return in_im
