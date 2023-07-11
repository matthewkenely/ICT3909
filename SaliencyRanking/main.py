import cv2
import numpy as np
import matplotlib.pyplot as plt
from saraRC1 import *

def main():
    im = '../COTS Dataset/Part 1 - Single Objects/objects/buddha_colour.jpeg'
    s1 = cv2.imread(im)

    # cv2.imshow('Input Image', s1)

    sara, sara_list = return_sara(s1)
    cv2.imshow('SaRa Output', sara)
    # print(sara_list)

    cv2.waitKey()


if __name__ == '__main__':
    main()