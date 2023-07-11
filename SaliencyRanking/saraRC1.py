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

#Import Akisato Kimura <akisato@ieee.org> implementation of Itti's Saliency Map Generator
#Original Source: https://github.com/akisatok/pySaliencyMap
import pySaliencyMap

#-------------------------------------------------
#Start Global Variables
#-------------------------------------------------

segmentsEntropies = []
segmentsCoords = []

# dir = "/Users/dylanseychell/dev/MSRA10K_Imgs_GT/MSRA10K_Imgs_GT/Imgs"
# dir2 = "/Users/dylanseychell/dev/shelves"
# dir3 = "/Users/dylanseychell/dev/COTS/COTSDataset/Part2-MultipleObjects"

segDim = 9
segments = []
gtSegments = []
dws = []
saraList = []

evalList = []
labelsEvalList = ['Image','Index','Rank','Quartile','isGT','Outcome']

outcomeList = []
labelsOutcomeList = ['Image', 'FN', 'FP', 'TN', 'TP']

dataframeCollection = {}
errorCount = 0

#-------------------------------------------------
#SaRa Initial Functions
#-------------------------------------------------

def generateSegments(img, segCount, depth=None):
    segments = []
    segmentCount = segCount
    index = 0

    wInterval = int(img.shape[1]/segmentCount)
    hInterval = int(img.shape[0]/segmentCount)

    for i in range(segmentCount):
        for j in range(segmentCount):
            #Note: img[TopRow:BottomRow, FirstColumn:LastColumn]
            tempSegment = img[int(hInterval*i):int(hInterval*(i+1)), int(wInterval*j):int(wInterval*(j+1))]
            #cv2.imshow("Crop" + str(i) + str(j), tempSegment)
            #coordTup = (index, x1, y1, x2, y2)
            coordTup = (index, int(wInterval*j), int(hInterval*i), int(wInterval*(j+1)), int(hInterval*(i+1)))
            segmentsCoords.append(coordTup)
            segments.append(tempSegment)
            index+=1

    return segments

def returnIttiSaliency(img):
    imgsize = img.shape
    img_width  = imgsize[1]
    img_height = imgsize[0]
    sm = pySaliencyMap.pySaliencyMap(img_width, img_height)
    saliency_map = sm.SMGetSM(img)

    #Scale pixel values to 0-255 instead of float (approx 0, hence black image)
    #https://stackoverflow.com/questions/48331211/how-to-use-cv2-imshow-correctly-for-the-float-image-returned-by-cv2-distancet/48333272
    saliency_map = cv2.normalize(saliency_map, None, 255,0, cv2.NORM_MINMAX, cv2.CV_8UC1)

    return saliency_map

#-------------------------------------------------
#Saliency Ranking
#-------------------------------------------------

def calculatePixelFrequency(img):
    flt = img.flatten()
    unique, counts = np.unique(flt, return_counts=True)
    pixelsFrequency = dict(zip(unique, counts))

    return pixelsFrequency

def calculateEntropy(img, w, dw):
    flt = img.flatten()

    c = flt.shape[0]
    totalPixels = 0
    tprob = 0
    sumOfProbs = 0
    entropy = 0
    wt = w*10

    #if imgD=None then proceed normally
    #else calculate its frequency and find max
    #use this max value as a weight in entropy

    pixelsFrequency = calculatePixelFrequency(flt)

    totalPixels = sum(pixelsFrequency.values())

    for px in pixelsFrequency:
        tprob = (pixelsFrequency.get(px))/totalPixels
        #probs[px] = tprob
        entropy += entropy + (tprob*math.log(2,(1/tprob)))

        entropy = entropy * wt * dw

    return(entropy)

def findMostSalientSegment(segments, kernel, dws):
    maxEntropy = 0
    index = 0
    i = 0
    for segment in segments:
        #tempEntropy = calculateEntropy(segment, kernel[i])
        tempEntropy = calculateEntropy(segment, kernel[i], dws[i])
        tempTup = (i, tempEntropy)
        segmentsEntropies.append(tempTup)
        if tempEntropy > maxEntropy:
            maxEntropy = tempEntropy
            index = i
        i += 1

    return maxEntropy, index

def makeGaussian(size, fwhm = 10, center=None):
    #https://gist.github.com/andrewgiessel/4635563
    """ Make a 2D gaussian kernel.
    size is the length of a side of the square
    fwhm is full-width-half-maximum, which
    can be thought of as an effective radius.
    """

    x = np.arange(0, size, 1, float)
    y = x[:,np.newaxis]

    if center is None:
        x0 = y0 = size // 2
    else:
        x0 = center[0]
        y0 = center[1]

    return np.exp(-4*np.log(2) * ((x-x0)**2 + (y-y0)**2) / fwhm**2)

def get_last_non_zero_index(d, default=None):
    rev = (len(d) - idx for idx, item in enumerate(reversed(d), 1) if item)
    return next(rev, default)

def get_first_non_zero_indox(list):
    return next((i for i, x in enumerate(list) if x), None)

def genDepthWeights(dSegments, depthMap):

    histD,binsD = np.histogram(depthMap,256,[0,256])
    firstNZ = get_first_non_zero_indox(histD)
    lastNZ = get_last_non_zero_index(histD)
    mid = (firstNZ+lastNZ)/2

    for seg in dSegments:
        hist,bins = np.histogram(seg,256,[0,256])
        #print(hist)
        dw=0
        ind = 0
        for s in hist:
            if(ind > mid):
                dw = dw + (s*(1))
            ind = ind + 1
        dws.append(dw)

    return dws

def genBlankDepthWeight(dSegments):
    for seg in dSegments:
        dw=1
        dws.append(dw)
    return dws

def generateHeatMap(img, mode, sortedSegScores, SegmentsCoords):
    #mode0 prints just a white grid
    #mode1 prints prints a colour-coded grid

    font = cv2.FONT_HERSHEY_SIMPLEX
    printIndex = 0
    set = int(0.25*len(sortedSegScores))
    color = (0,0,0)

    saraListOut = []

    #rank = 0

    for ent in sortedSegScores:
        quartile = 0
        if(mode == 0):
            color = (255,255,255)
            t = 4
        elif(mode == 1):
            if(printIndex+1 <= set):
                color = (0,0,255)
                t = 8
                quartile = 4
            elif(printIndex+1 <= set*2):
                color = (0,128,255)
                t = 6
                quartile = 3
            elif(printIndex+1 <= set*3):
                color = (0,255,255)
                t = 4
                quartile = 2
            elif(printIndex+1 <= set*4):
                color = (0,250,0)
                t = 2
                quartile = 1

        x1 = segmentsCoords[ent[0]][1]
        y1 = segmentsCoords[ent[0]][2]
        x2 = segmentsCoords[ent[0]][3]
        y2 = segmentsCoords[ent[0]][4]
        x = int((x1 + x2 )/2)
        y = int((y1 + y2)/2)

        cv2.putText(img, str(printIndex), (x-2,y), font, .5, color ,1 ,cv2.LINE_AA)
        cv2.rectangle(img, (x1,y1), (x2,y2), color , t)

        #print("\nText Index:" + str(printIndex))
        #print("Rank:" + str(ent[0]))
        #print("Quartile:" + str(quartile))

        #cv2.putText(gtSara, str(printIndex), (x-2,y), font, .5, (255,255,255) ,1 ,cv2.LINE_AA)
        #cv2.rectangle(gtSara, (x1,y1), (x2,y2), color , t)

        #saraTuple = (index, rank, quartile)
        saraTuple = (ent[0], printIndex, quartile)
        #print("\nSara Tuple: " + str(saraTuple))
        saraListOut.append(saraTuple)
        printIndex+=1

    #print(saraListOut)
    return img, saraListOut

def generateSaRa(tex, texSegments):
    #Generate Gaussian Weights
    gaussian_kernel_array = makeGaussian(segDim)
    gaussian1d = gaussian_kernel_array.ravel()

    #Generate Depth scores
    #dSegments = generateSegments(gt, segDim)
    dws = genBlankDepthWeight(texSegments)

    #Generate Saliency Ranking
    maxH, index = findMostSalientSegment(texSegments, gaussian1d, dws)
    dictEntropies = dict(segmentsEntropies)
    sortedEntropies = sorted(dictEntropies.items(), key=operator.itemgetter(1), reverse=True)

    #Generate Heatmap and display it
    texOut, saraListOut = generateHeatMap(tex, 1, sortedEntropies, segmentsCoords)
    return texOut, saraListOut

#-------------------------------------------------
#Evaluation Functions
#-------------------------------------------------

def returnSARA(inputImg):

    texSegments = generateSegments(returnIttiSaliency(inputImg), 9)
    saraOutput, saraListOutput = generateSaRa(inputImg, texSegments)

    return saraOutput, saraListOutput

def mse(imageA, imageB):
	# the 'Mean Squared Error' between the two images is the
	# sum of the squared difference between the two images;
	# NOTE: the two images must have the same dimension
	err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
	err /= float(imageA.shape[0] * imageA.shape[1])

	# return the MSE, the lower the error, the more "similar"
	# the two images are
	return err

#-------------------------------------------------
#-------------------------------------------------
#Start Main Code
#-------------------------------------------------
#-------------------------------------------------

cotsSet = "academic_book_no"
imgPath1 = "/Users/dylanseychell/dev/COTS/COTSDataset/Part2-MultipleObjects/" + cotsSet +"/3_colour.jpeg"

s1 = cv2.imread(imgPath1)

#for another image, simply import a second image and initialise s2 and replicate the code below for the scond image
#s2 = cv2.imread(imgPath2)

cv2.imshow("Input Image", s1)
print(texPath1)

#texSegments1 = generateSegments(returnIttiSaliency(s1), 9)

print("Generating SaRa")

outS1, saraListS1 = returnSARA(s1)
cv2.imshow("SaRa Output for S1", outS1)
print(saraListS1)

cv2.waitKey()

#-------------------------------------------------
#Auxiliary Output Code
#-------------------------------------------------

#start_time = time.time()
#Code to be timed goes here
#print("%s" % (time.time() - start_time))

#returns zero if all pixels are black
#print(cv2.countNonZero(gtSegments[0]))
