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

# Entropy, sum, depth, centre-bias
WEIGHTS = (1, 1, 1, 1)

DO_LOG = True

# segments_entropies = []
segments_scores = []
segments_coords = []

seg_dim = 0
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
            temp_segment = img[int(h_interval * i):int(h_interval * (i + 1)),
                              int(w_interval * j):int(w_interval * (j + 1))]
            segments.append(temp_segment)
            
            coord_tup = (index, int(w_interval * j), int(h_interval * i),
                         int(w_interval * (j + 1)), int(h_interval * (i + 1)))
            segments_coords.append(coord_tup)
            
            index += 1

    return segments


def return_saliency(img, generator='itti', deepgaze_model=None, emlnet_models=None, DEVICE='cpu'):
    '''
    Takes an image img as input and calculates the saliency map using the 
    Itti's Saliency Map Generator. It returns the saliency map.
    '''

    img_width, img_height = img.shape[1], img.shape[0]

    if generator == 'itti':

        sm = pySaliencyMap.pySaliencyMap(img_width, img_height)
        saliency_map = sm.SMGetSM(img)

        # Scale pixel values to 0-255 instead of float (approx 0, hence black image)
        # https://stackoverflow.com/questions/48331211/how-to-use-cv2-imshow-correctly-for-the-float-image-returned-by-cv2-distancet/48333272
        saliency_map = cv2.normalize(saliency_map, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_8UC1)

        return saliency_map
    elif generator == 'deepgaze':
        import numpy as np
        from scipy.misc import face
        from scipy.ndimage import zoom
        from scipy.special import logsumexp
        import torch

        import deepgaze_pytorch

        # you can use DeepGazeI or DeepGazeIIE
        # model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(DEVICE)

        if deepgaze_model is None:
            model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(DEVICE)
        else:
            model = deepgaze_model

        # image = face()
        image = img

        # Resize to half
        image = cv2.resize(image, (image.shape[1] // 2, image.shape[0] // 2))

        # load precomputed centerbias log density (from MIT1003) over a 1024x1024 image
        # you can download the centerbias from https://github.com/matthias-k/DeepGaze/releases/download/v1.0.0/centerbias_mit1003.npy
        # alternatively, you can use a uniform centerbias via `centerbias_template = np.zeros((1024, 1024))`.
        # centerbias_template = np.load('centerbias_mit1003.npy')
        centerbias_template = np.zeros((1024, 1024))
        # rescale to match image size
        centerbias = zoom(centerbias_template, (image.shape[0]/centerbias_template.shape[0], image.shape[1]/centerbias_template.shape[1]), order=0, mode='nearest')
        # renormalize log density
        centerbias -= logsumexp(centerbias)

        image_tensor = torch.tensor([image.transpose(2, 0, 1)]).to(DEVICE)
        centerbias_tensor = torch.tensor([centerbias]).to(DEVICE)

        log_density_prediction = model(image_tensor, centerbias_tensor)

        saliency_map = cv2.resize(log_density_prediction.detach().cpu().numpy()[0, 0], (img_width, img_height))

    elif generator == 'fpn':
        # Add ./fpn to the system path
        import sys
        sys.path.append('./fpn')
        import inference as inf

        results_dict = {}
        rt_args = inf.parse_arguments(img)
        
        # Call the run_inference function and capture the results
        pred_masks_raw_list, pred_masks_round_list = inf.run_inference(rt_args)
        
        # Store the results in the dictionary
        results_dict['pred_masks_raw'] = pred_masks_raw_list
        results_dict['pred_masks_round'] = pred_masks_round_list

        saliency_map = results_dict['pred_masks_raw']

        if img_width > img_height:
            saliency_map = cv2.resize(saliency_map, (img_width, img_width))

            diff = (img_width - img_height) // 2

            saliency_map = saliency_map[diff:img_width - diff, 0:img_width]
        else:
            saliency_map = cv2.resize(saliency_map, (img_height, img_height))

            diff = (img_height - img_width) // 2

            saliency_map = saliency_map[0:img_height, diff:img_height - diff]

    elif generator == 'emlnet':
        from emlnet.eval_combined import main as eval_combined
        saliency_map = eval_combined(img, emlnet_models)

        # Resize to image size
        saliency_map = cv2.resize(saliency_map, (img_width, img_height))

    # Normalize saliency map
    saliency_map = cv2.normalize(saliency_map, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_8UC1)

    saliency_map = cv2.GaussianBlur(saliency_map, (31, 31), 10)
    saliency_map = saliency_map // 4

    return saliency_map


def return_saliency_batch(images, generator='deepgaze', deepgaze_model=None, emlnet_models=None, DEVICE='cuda', BATCH_SIZE=1):
    img_widths, img_heights = [], []
    if generator == 'deepgaze':
        import numpy as np
        from scipy.misc import face
        from scipy.ndimage import zoom
        from scipy.special import logsumexp
        import torch

        import deepgaze_pytorch

        # you can use DeepGazeI or DeepGazeIIE
        # model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(DEVICE)

        if deepgaze_model is None:
            model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(DEVICE)
        else:
            model = deepgaze_model

        # image = face()
        # image = img
        image_batch = torch.tensor([img.transpose(2, 0, 1) for img in images]).to(DEVICE)
        centerbias_template = np.zeros((1024, 1024))
        centerbias_tensors = []

        for img in images:
            centerbias = zoom(centerbias_template, (img.shape[0] / centerbias_template.shape[0], img.shape[1] / centerbias_template.shape[1]), order=0, mode='nearest')
            centerbias -= logsumexp(centerbias)
            centerbias_tensors.append(torch.tensor(centerbias).to(DEVICE))

            # Set img_width and img_height
            img_widths.append(img.shape[1])


        # rescale to match image size
        # centerbias = zoom(centerbias_template, (image.shape[0]/centerbias_template.shape[0], image.shape[1]/centerbias_template.shape[1]), order=0, mode='nearest')
        # # renormalize log density
        # centerbias -= logsumexp(centerbias)

        # image_tensor = torch.tensor([image.transpose(2, 0, 1)]).to(DEVICE)
        # centerbias_tensor = torch.tensor([centerbias]).to(DEVICE)
        with torch.no_grad():
            # Process the batch of images in one forward pass
            log_density_predictions = model(image_batch, torch.stack(centerbias_tensors))

        # log_density_prediction = model(image_tensor, centerbias_tensor)

        # saliency_map = cv2.resize(log_density_prediction.detach().cpu().numpy()[0, 0], (img_width, img_height))

        saliency_maps = []

        for i in range(len(images)):
            saliency_map = cv2.resize(log_density_predictions[i, 0].cpu().numpy(), (img_widths[i], img_widths[i]))

            saliency_map = cv2.normalize(saliency_map, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_8UC1)

            saliency_map = cv2.GaussianBlur(saliency_map, (31, 31), 10)
            saliency_map = saliency_map // 8
            
            saliency_maps.append(saliency_map)

        return saliency_maps
    

# def return_itti_saliency(img):
#     '''
#     Takes an image img as input and calculates the saliency map using the 
#     Itti's Saliency Map Generator. It returns the saliency map.
#     '''

#     img_width, img_height = img.shape[1], img.shape[0]

#     sm = pySaliencyMap.pySaliencyMap(img_width, img_height)
#     saliency_map = sm.SMGetSM(img)

#     # Scale pixel values to 0-255 instead of float (approx 0, hence black image)
#     # https://stackoverflow.com/questions/48331211/how-to-use-cv2-imshow-correctly-for-the-float-image-returned-by-cv2-distancet/48333272
#     saliency_map = cv2.normalize(saliency_map, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_8UC1)

#     return saliency_map


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


def calculate_score(H, sum, ds, cb, w):
    '''
    Calculates the saliency score of an image img using the entropy H, depth score ds, centre-bias cb and weights w. It returns the saliency score.
    '''

    ## NEW
    if w[0] == 0:
        H = 0
    else:
        H = H ** w[0]

    if w[1] == 0:
        sum = 0
    else:
        sum = sum ** w[1]

    if DO_LOG:
        if sum > 0:
            sum = np.log(sum)


    if w[2] == 0:
        ds = 0
    else:
        ds = ds ** w[2]

    if w[3] == 0:
        cb = 0
    else:
        cb = (cb + 1) ** w[3]

    return (H + sum + ds + cb), H, sum, ds, cb


    ## OLD
    # H = H * w[0]

    # # if sum > 0:
    # #     sum = np.log(sum)
    # # sum = sum ** w[1]

    # ds = ds * w[2]

    # cb = cb * w[3]

    # return H + ds + cb


def calculate_entropy(img, w, dw) -> float:
    '''
    Calculates the entropy of an image img using the given weights w and 
    depth weights dw. It returns the entropy value.
    '''

    flt = img.flatten()

    # c = flt.shape[0]
    total_pixels = 0
    t_prob = 0
    # sum_of_probs = 0
    entropy = 0
    wt = w * 10

    # if imgD=None then proceed normally
    # else calculate its frequency and find max
    # use this max value as a weight in entropy

    pixels_frequency = calculate_pixel_frequency(flt)

    total_pixels = sum(pixels_frequency.values())

    for px in pixels_frequency:
        t_prob = pixels_frequency[px] / total_pixels

        if t_prob != 0:
            entropy += (t_prob * math.log((1 / t_prob), 2))

    # entropy = entropy * wt * dw

    return entropy


def find_most_salient_segment(segments, kernel, dws):
    '''
    Finds the most salient segment among the provided segments using a 
    given kernel and depth weights. It returns the maximum entropy value 
    and the index of the most salient segment.
    '''

    # max_entropy = 0
    max_score = 0
    index = 0
    i = 0

    for segment in segments:
        temp_entropy = calculate_entropy(segment, kernel[i], dws[i])
        # Normalise semgnet bweetn 0 and 255
        segment = cv2.normalize(segment, None, 255, 0, cv2.NORM_MINMAX, cv2.CV_8UC1)
        temp_sum = np.sum(segment)
        # temp_tup = (i, temp_entropy)
        # segments_entropies.append(temp_tup)

        w = WEIGHTS
        
        temp_score, res_entropy, res_sum, res_dws, res_kernel = calculate_score(temp_entropy, temp_sum, dws[i], kernel[i], w)

        # NEW
        temp_tup = (i, temp_score, res_entropy, res_sum, res_dws, res_kernel)

        # # OLD
        # temp_tup = (i, temp_score, temp_entropy * w[0], 0, (kernel[i] + 1) * w[2], dws[i] * w[3])

        # segments_scores.append((i, temp_score))
        segments_scores.append(temp_tup)

        # if temp_entropy > max_entropy:
        #     max_entropy = temp_entropy
        #     index = i

        if temp_score > max_score:
            max_score = temp_score
            index = i

        i += 1

    # return max_entropy, index
    return max_score, index


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


def gen_depth_weights(d_segments, depth_map) -> list:
    '''
    Generates depth weights for the segments based on the depth map. It 
    returns a list of depth weights.
    '''

    hist_d, _ = np.histogram(depth_map, 256, [0, 256])

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

    mode: 0 for white grid, 1 for color-coded grid, 2 for interpolated
    '''

    font = cv2.FONT_HERSHEY_SIMPLEX
    # print_index = 0
    print_index = len(sorted_seg_scores) - 1
    set_value = int(0.25 * len(sorted_seg_scores))
    color = (0, 0, 0)


    # Check number of segments
    n = len(sorted_seg_scores)

    # Interpolate colors between lb and ub based on the number of segments
    colors = []

    lb = (1, 1, 1)
    ub = (255, 255, 255)

    for i in range(n):
        r = int(lb[0] + (ub[0] - lb[0]) * (i / n))
        g = int(lb[1] + (ub[1] - lb[1]) * (i / n))
        b = int(lb[2] + (ub[2] - lb[2]) * (i / n))

        colors.append((r, g, b))

    colors = list(reversed(colors))

    # print(colors)

    max_x = 0
    max_y = 0

    overlay = np.zeros_like(img, dtype=np.uint8)
    text_overlay = np.zeros_like(img, dtype=np.uint8)

    text_overlay = cv2.resize(text_overlay, (0, 0), fx=2, fy=2)

    sara_list_out = []

    done_coords = {}

    for ent in reversed(sorted_seg_scores):
        if mode in [0, 1]:
            quartile = 0
            if mode == 0:
                color = (255, 255, 255)
                t = 4
            elif mode == 1:
                if print_index + 1 <= set_value:
                    color = (0, 0, 255, 255)
                    t = 2
                    quartile = 1
                elif print_index + 1 <= set_value * 2:
                    color = (0, 128, 255, 192)
                    t = 4
                    quartile = 2
                elif print_index + 1 <= set_value * 3:
                    color = (0, 255, 255, 128)
                    t = 4
                    t = 6
                    quartile = 3
                # elif print_index + 1 <= set_value * 4:
                #     color = (0, 250, 0, 64)
                #     t = 8
                #     quartile = 4
                else:
                    color = (0, 250, 0, 64)
                    t = 8
                    quartile = 4
        elif mode == 2:
            color = colors[print_index]

        x1 = segments_coords[ent[0]][1]
        y1 = segments_coords[ent[0]][2]
        x2 = segments_coords[ent[0]][3]
        y2 = segments_coords[ent[0]][4]

        if x2 > max_x:
            max_x = x2
        if y2 > max_y:
            max_y = y2

        x = int((x1 + x2) / 2)
        y = int((y1 + y2) / 2)



        # fill rectangle
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)

        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), 1)

        # Check if this will overlap with a previous segment
        for coord in done_coords:
            if x1 < done_coords[coord]['coords'][2] and x2 > done_coords[coord]['coords'][0] and y1 < done_coords[coord]['coords'][3] and y2 > done_coords[coord]['coords'][1]:
                # Check if this is larger than the previous segment
                this_size = (x2 - x1) * (y2 - y1)
                previous_size = (done_coords[coord]['coords'][2] - done_coords[coord]['coords'][0]) * (done_coords[coord]['coords'][3] - done_coords[coord]['coords'][1])

                if this_size > previous_size:
                    # Redo the previous segment
                    cv2.rectangle(overlay, (done_coords[coord]['coords'][0], done_coords[coord]['coords'][1]), (done_coords[coord]['coords'][2], done_coords[coord]['coords'][3]), done_coords[coord]['color'], -1)

                    cv2.rectangle(overlay, (done_coords[coord]['coords'][0], done_coords[coord]['coords'][1]), (done_coords[coord]['coords'][2], done_coords[coord]['coords'][3]), (0, 0, 0), 1)
                
        
        # put text in the middle of the rectangle
        # white text
        if mode in [0, 1]:
            cv2.putText(text_overlay, str(print_index + 1), (x - 5, y),
                        font, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        elif mode == 2:
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            font_size = 1.6

            thickness = 3

            text_to_display = f'{str(print_index + 1)}'

            (text_width, text_height), _ = cv2.getTextSize(text_to_display, cv2.FONT_HERSHEY_DUPLEX, font_size, thickness)

            # If width or height are greater than the segment, reduce font size
            if text_width > (x2 - x1) - 20 or text_height > (y2 - y1) - 20:
                font_size = 0.8
                thickness = 2
                (text_width, text_height), _ = cv2.getTextSize(text_to_display, cv2.FONT_HERSHEY_DUPLEX, font_size, thickness)

            text_position = (center_x - text_width // 2, center_y + 20) 


            cv2.putText(text_overlay, str(print_index + 1), text_position, cv2.FONT_HERSHEY_DUPLEX, font_size, (255, 255, 255), thickness, cv2.LINE_AA)

            done_coords[print_index] = {}
            done_coords[print_index]['coords'] = (x1, y1, x2, y2)
            done_coords[print_index]['color'] = color
        
        # Index, rank, score, entropy, sum, depth, centre-bias
        sara_tuple = (ent[0], print_index, ent[1], ent[2], ent[3], ent[4], ent[5])
        sara_list_out.append(sara_tuple)
        print_index -= 1

    if mode in [0, 1]:
        # crop the overlay to up to x2 and y2
        overlay = overlay[0:max_y, 0:max_x]
        text_overlay = text_overlay[0:max_y, 0:max_x]
        img = img[0:max_y, 0:max_x]

        
        img = cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)

        # img[text_overlay > 128] = text_overlay[text_overlay > 128]

        return img, sara_list_out
    elif mode == 2:
        heatmap = overlay[0:img.shape[0], 0:img.shape[1]]
        text_overlay = text_overlay[0:img.shape[0], 0:img.shape[1]]

        return [heatmap, text_overlay], sara_list_out


def generate_sara(tex, tex_segments, mode):
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
    # dict_entropies = dict(segments_entropies)
    # segments_scores list with 5 elements, use index as key for dict and store rest as list of index
    dict_scores = {}

    for segment in segments_scores:
        # Index: score, entropy, sum, depth, centre-bias
        dict_scores[segment[0]] = [segment[1], segment[2], segment[3], segment[4], segment[5]]

    # sorted_entropies = sorted(dict_entropies.items(),
    #                           key=operator.itemgetter(1), reverse=True)
                              

    # sorted_scores = sorted(dict_scores.items(),
    #                           key=operator.itemgetter(1), reverse=True)

    # Sort by first value in value list
    sorted_scores = sorted(dict_scores.items(), key=lambda x: x[1][0], reverse=True)
    
    # flatten
    sorted_scores = [[i[0], i[1][0], i[1][1], i[1][2], i[1][3], i[1][4]] for i in sorted_scores]

    # tex_out, sara_list_out = generate_heatmap(
    #     tex, 1, sorted_entropies, segments_coords)

    if mode in [0, 1]:
        tex_out, sara_list_out = generate_heatmap(
            tex, mode, sorted_scores, segments_coords)
    elif mode == 2:
        [tex_out, text_overlay], sara_list_out = generate_heatmap(
            tex, mode, sorted_scores, segments_coords)
    
    sara_list_out = list(reversed(sara_list_out))
    
    if mode in [0, 1]:
        return tex_out, sara_list_out
    elif mode == 2:
        return [tex_out, text_overlay], sara_list_out


def return_sara(input_img, grid=9, generator='itti', saliency_map=None, segments=None, coords=None, mode=1):
    '''
    Computes the SaRa output for the given input image. It uses the 
    generate_sara function internally. It returns the SaRa output image and 
    a list of segment scores.
    '''

    global seg_dim, segments_coords
    seg_dim = grid

    if saliency_map is None:
        saliency_map = return_saliency(input_img, generator)

    if segments is None:
        tex_segments = generate_segments(saliency_map, seg_dim)
    else:
        tex_segments = segments
        segments_coords = coords

    # tex_segments = generate_segments(input_img, seg_dim)
        
    if mode in [0, 1]:
        sara_output, sara_list_output = generate_sara(input_img, tex_segments, mode)
        return sara_output, sara_list_output
    elif mode == 2:
        [sara_output, text_overlay], sara_list_output = generate_sara(input_img, tex_segments, mode)
        return [sara_output, text_overlay], sara_list_output


def mean_squared_error(image_a, image_b) -> float:
    '''
    Calculates the Mean Squared Error (MSE), i.e. sum of squared 
    differences between two images image_a and image_b. It returns the MSE 
    value.

    NOTE: The two images must have the same dimension
    '''

    err = np.sum((image_a.astype('float') - image_b.astype('float')) ** 2)
    err /= float(image_a.shape[0] * image_a.shape[1])

    return err


def reset():
    '''
    Resets all global variables to their default values.
    '''

    # global segments_entropies, segments_scores, segments_coords, seg_dim, segments, gt_segments, dws, sara_list

    global segments_scores, segments_coords, seg_dim, segments, gt_segments, dws, sara_list, WEIGHTS, DO_LOG

    # segments_entropies = []
    segments_scores = []
    segments_coords = []

    seg_dim = 0
    segments = []
    gt_segments = []
    dws = []
    sara_list = []

    WEIGHTS = (1, 1, 1, 1)
    DO_LOG = True
