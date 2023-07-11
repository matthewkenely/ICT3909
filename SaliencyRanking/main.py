import cv2
import numpy as np
import matplotlib.pyplot as plt
import saraRC1 as sara

def maximise_entropy(im):
    grid_entropies = []
    s1 = cv2.imread(im)

    for i in range(3, 20):
        heatmap, sara_list = sara.return_sara(s1.copy(), i)
        cv2.imshow('SaRa Output', heatmap)
        # print(f'{i} : {sara_list[0][1]}')

        entropies = sara_list[0:50][1]
        average = sum(entropies) / len(entropies)
        grid_entropies.append((i, average))
        sara.reset()

    ranks = grid_entropies.copy()
    grid_entropies.sort(key=lambda x: x[1], reverse=True)

    return grid_entropies[0][0], ranks

def main():
    im = '../COTS Dataset/Part 1 - Single Objects/objects/buddha_colour.jpeg'

    grid_size, ranks = maximise_entropy(im)

    heatmap, _ = sara.return_sara(cv2.imread(im), grid_size)
    cv2.imshow('SaRa Output - Grid Size ' + str(grid_size), heatmap)
    # print(entropies)

    for i in ranks:
        print(i)

    plt.figure()
    plt.plot([i[0] for i in ranks], [i[1] for i in ranks])
    plt.xlabel('Grid Size')
    plt.ylabel('Average Entropy')
    plt.title('Average Entropy vs Grid Size')
    plt.show()

    # logarithmic scale
    plt.figure()
    plt.plot([i[0] for i in ranks], [i[1] for i in ranks])
    plt.xlabel('Grid Size')
    plt.ylabel('Average Entropy')
    plt.title('Average Entropy vs Grid Size (Logarithmic Scale)')
    plt.yscale('log')
    plt.show()

    cv2.waitKey()


if __name__ == '__main__':
    main()
