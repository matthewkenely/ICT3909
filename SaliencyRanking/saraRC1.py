import cv2
import numpy as np
import math
import scipy.stats as st
import matplotlib.pyplot as plt
import operator
import time
import os
from enum import Enum
import pandas as pd

# Akisato Kimura <akisato@ieee.org> implementation of Itti's Saliency Map Generator -- https://github.com/akisatok/pySaliencyMap
import pySaliencyMap


# Global Variables
segments_entropies = []
segments_coords = []

seg_dim = 9
segments = []
gt_segments = []
dws = []
sara_list = []

eval_list = []
labels_eval_list = ['Image', 'Index', 'Rank', 'Quartile', 'isGT', 'Outcome']

outcome_list = []
labels_outcome_list = ['Image', 'FN', 'FP', 'TN', 'TP']

dataframe_collection = {}
error_count = 0


# SaRa Initial Functions
def generate_segments(img, seg_count) -> list:
    '''
    Given an image img and the desired number of segments seg_count, this 
    function divides the image into segments and returns a list of segments.
    '''

    segments = []
    segment_count = seg_count
    index = 0

    w_interval = int(img.shape[1] / segment_count)
    h_interval = int(img.shape[0] / segment_count)

    for i in range(segment_count):
        for j in range(segment_count):
            # Note: img[TopRow:BottomRow, FirstColumn:LastColumn]
            temp_segment = img[int(h_interval * i):int(h_interval * (i + 1)),
                              int(w_interval * j):int(w_interval * (j + 1))]
            # cv2.imshow("Crop" + str(i) + str(j), temp_segment)
            # coord_tup = (index, x1, y1, x2, y2)
            coord_tup = (index, int(w_interval * j), int(h_interval * i),
                         int(w_interval * (j + 1)), int(h_interval * (i + 1)))
            segments_coords.append(coord_tup)
            segments.append(temp_segment)
            index += 1

    return segments


def return_itti_saliency(img):
    '''
    Takes an image img as input and calculates the saliency map using the 
    Itti's Saliency Map Generator. It returns the saliency map.
    '''

    img_size = img.shape
    img_width = img_size[1]
    img_height = img_size[0]
    sm = pySaliencyMap.pySaliencyMap(img_width, img_height)
    saliency_map = sm.SMGetSM(img)

    # Scale pixel values to 0-255 instead of float (approx 0, hence black image)
    # https://stackoverflow.com/questions/48331211/how-to-use-cv2-imshow-correctly-for-the-float-image-returned-by-cv2-distancet/48333272
    saliency_map = cv2.normalize(
        saliency_map, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_8UC1)

    return saliency_map


# Saliency Ranking
def calculate_pixel_frequency(img) -> dict:
    '''
    Calculates the frequency of each pixel value in the image img and 
    returns a dictionary containing the pixel frequencies.
    '''

    flt = img.flatten()
    unique, counts = np.unique(flt, return_counts=True)
    pixels_frequency = dict(zip(unique, counts))

    return pixels_frequency


def calculate_entropy(img, w, dw) -> float:
    '''
    Calculates the entropy of an image img using the given weights w and 
    depth weights dw. It returns the entropy value.
    '''

    flt = img.flatten()

    c = flt.shape[0]
    total_pixels = 0
    t_prob = 0
    sum_of_probs = 0
    entropy = 0
    wt = w * 10

    # if imgD=None then proceed normally
    # else calculate its frequency and find max
    # use this max value as a weight in entropy

    pixels_frequency = calculate_pixel_frequency(flt)

    total_pixels = sum(pixels_frequency.values())

    for px in pixels_frequency:
        t_prob = (pixels_frequency.get(px)) / total_pixels
        entropy += entropy + (t_prob * math.log(2, (1 / t_prob)))

    entropy = entropy * wt * dw

    return entropy


def find_most_salient_segment(segments, kernel, dws):
    '''
    Finds the most salient segment among the provided segments using a 
    given kernel and depth weights. It returns the maximum entropy value 
    and the index of the most salient segment.
    '''

    max_entropy = 0
    index = 0
    i = 0

    for segment in segments:
        temp_entropy = calculate_entropy(segment, kernel[i], dws[i])
        temp_tup = (i, temp_entropy)
        segments_entropies.append(temp_tup)
        if temp_entropy > max_entropy:
            max_entropy = temp_entropy
            index = i
        i += 1

    return max_entropy, index


def make_gaussian(size, fwhm=10, center=None):
    '''
    Generates a 2D Gaussian kernel with the specified size and full-width-half-maximum (fwhm). It returns the Gaussian kernel.

    size: length of a side of the square
    fwhm: full-width-half-maximum, which can be thought of as an effective 
    radius.

    https://gist.github.com/andrewgiessel/4635563
    '''

    x = np.arange(0, size, 1, float)
    y = x[:, np.newaxis]

    if center is None:
        x0 = y0 = size // 2
    else:
        x0 = center[0]
        y0 = center[1]

    return np.exp(-4 * np.log(2) * ((x - x0) ** 2 + (y - y0) ** 2) / fwhm ** 2)


# def get_last_non_zero_index(d, default=None) -> int:
#     '''
#     Returns the index of the last non-zero element in a list d. If no 
#     non-zero elements are found, it returns the default value.
#     '''

#     rev = (len(d) - idx for idx, item in enumerate(reversed(d), 1) if item)
#     return next(rev, default)


# def get_first_non_zero_index(list) -> int:
#     '''
#     Returns the index of the first non-zero element in a list list. If no 
#     non-zero elements are found, it returns None.
#     '''

#     return next((i for i, x in enumerate(list) if x), None)


def gen_depth_weights(d_segments, depth_map) -> list:
    '''
    Generates depth weights for the segments based on the depth map. It 
    returns a list of depth weights.
    '''

    hist_d, bins_d = np.histogram(depth_map, 256, [0, 256])

    # Get first non-zero index
    first_nz = next((i for i, x in enumerate(hist_d) if x), None)

    # Get last non-zero index
    rev = (len(hist_d) - idx for idx, item in enumerate(reversed(hist_d), 1) if item)
    last_nz = next(rev, default=None)

    mid = (first_nz + last_nz) / 2

    for seg in d_segments:
        hist, _ = np.histogram(seg, 256, [0, 256])
        dw = 0
        ind = 0
        for s in hist:
            if ind > mid:
                dw = dw + (s * 1)
            ind = ind + 1
        dws.append(dw)

    return dws


def gen_blank_depth_weight(d_segments):
    '''
    Generates blank depth weights for the segments. It returns a list of 
    depth weights.
    '''

    for _ in d_segments:
        dw = 1
        dws.append(dw)
    return dws


def generate_heatmap(img, mode, sorted_seg_scores, segments_coords) -> tuple:
    '''
    Generates a heatmap overlay on the input image img based on the 
    provided sorted segment scores. The mode parameter determines the color 
    scheme of the heatmap. It returns the image with the heatmap overlay 
    and a list of segment scores.

    mode: 0 for white grid, 1 for color-coded grid
    '''

    font = cv2.FONT_HERSHEY_SIMPLEX
    print_index = 0
    set_value = int(0.25 * len(sorted_seg_scores))
    color = (0, 0, 0)

    sara_list_out = []

    for ent in sorted_seg_scores:
        quartile = 0
        if mode == 0:
            color = (255, 255, 255)
            t = 4
        elif mode == 1:
            if print_index + 1 <= set_value:
                color = (0, 0, 255)
                t = 8
                quartile = 4
            elif print_index + 1 <= set_value * 2:
                color = (0, 128, 255)
                t = 6
                quartile = 3
            elif print_index + 1 <= set_value * 3:
                color = (0, 255, 255)
                t = 4
                quartile = 2
            elif print_index + 1 <= set_value * 4:
                color = (0, 250, 0)
                t = 2
                quartile = 1

        x1 = segments_coords[ent[0]][1]
        y1 = segments_coords[ent[0]][2]
        x2 = segments_coords[ent[0]][3]
        y2 = segments_coords[ent[0]][4]
        x = int((x1 + x2) / 2)
        y = int((y1 + y2) / 2)

        cv2.putText(img, str(print_index), (x - 2, y),
                    font, .5, color, 1, cv2.LINE_AA)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, t)

        sara_tuple = (ent[0], print_index, quartile)
        sara_list_out.append(sara_tuple)
        print_index += 1

    return img, sara_list_out


def generate_sara(tex, tex_segments):
    '''
    Generates the SaRa (Salient Region Annotation) output by calculating 
    saliency scores for the segments of the given texture image tex. It 
    returns the texture image with the heatmap overlay and a list of 
    segment scores.
    '''

    gaussian_kernel_array = make_gaussian(seg_dim)
    gaussian1d = gaussian_kernel_array.ravel()

    dws = gen_blank_depth_weight(tex_segments)

    max_h, index = find_most_salient_segment(tex_segments, gaussian1d, dws)
    dict_entropies = dict(segments_entropies)
    sorted_entropies = sorted(dict_entropies.items(),
                              key=operator.itemgetter(1), reverse=True)

    tex_out, sara_list_out = generate_heatmap(
        tex, 1, sorted_entropies, segments_coords)
    return tex_out, sara_list_out


def return_sara(input_img):
    '''
    Computes the SaRa output for the given input image. It uses the 
    generate_sara function internally. It returns the SaRa output image and 
    a list of segment scores.
    '''

    tex_segments = generate_segments(return_itti_saliency(input_img), 9)
    sara_output, sara_list_output = generate_sara(input_img, tex_segments)

    return sara_output, sara_list_output


def mean_squared_error(image_a, image_b) -> float:
    '''
    Calculates the Mean Squared Error (MSE), i.e. sum of squared 
    differences between two images image_a and image_b. It returns the MSE 
    value.

    NOTE: The two images must have the same dimension
    '''

    err = np.sum((image_a.astype("float") - image_b.astype("float")) ** 2)
    err /= float(image_a.shape[0] * image_a.shape[1])

    return err
