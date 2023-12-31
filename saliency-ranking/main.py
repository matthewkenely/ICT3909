import cv2
import numpy as np
import matplotlib.pyplot as plt
import saraRC1 as sara


def maximise_entropy(im, name, n):
    '''
    Given an image im, this function returns the grid size that maximises the average entropy of the top n segments generated by SaRa.
    '''

    entropies = {}
    s1 = cv2.imread(im)

    # All grid sizes
    plt.figure(name + ' SaRa Output - All Grid Sizes')
    plt.gcf().set_size_inches(12, 6)

    for seg_dim in range(5, n):
        heatmap, sara_list = sara.return_sara(s1.copy(), seg_dim)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # Plot heatmap of grid size i x i
        plt.subplot(4, 5, seg_dim - 4)
        plt.imshow(heatmap)
        plt.xticks([])
        plt.yticks([])
        plt.title(str(seg_dim) + ' x ' + str(seg_dim))

        # Output heatmap to file
        path = './output/' + name + \
            ' (' + str(seg_dim) + 'x' + str(seg_dim) + ').png'
        # heatmap = cv2.cvtColor(heatmap, cv2.COLOR_RGB2BGR)
        # cv2.imwrite(path, heatmap)
        # print(f'Image saved to {path}')

        # Average entropy of the top 25% grid segments
        top = seg_dim * seg_dim // 4
        average = sum(sara_list[0:top][1]) / len(sara_list[0:top][1])
        entropies[seg_dim] = (seg_dim, average, sara_list, path)

        sara.reset()

    entropies_sorted = entropies.copy()
    entropies_sorted = sorted(entropies_sorted.items(),
                              key=lambda x: x[1][1], reverse=True)

    return entropies, entropies_sorted


def plot_heatmap(im, grid_size, name=None):
    '''
    Given an image im, this function plots the heatmap generated by SaRa for the given grid size.
    '''

    heatmap, _ = sara.return_sara(cv2.imread(im), grid_size)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    plt.figure(name + ' SaRa Output - Grid Size ' +
               str(grid_size) + ' x ' + str(grid_size))
    plt.gcf().set_size_inches(12, 6)
    plt.imshow(heatmap)
    plt.xticks([])
    plt.yticks([])
    plt.title('SaRa Output - Grid Size ' +
              str(grid_size) + ' x ' + str(grid_size))


def plot_entropy_vs_grid_size(entropies, name=None):
    '''
    Given a dictionary of entropies, this function plots the average entropy vs grid size.
    '''

    plt.figure(name + ' Average Entropy vs Grid Size (Logarithmic Scale)')
    for seg_dim in entropies.keys():
        plt.plot(seg_dim, entropies[seg_dim][1], 'bo')
        if seg_dim > 5:
            plt.plot([seg_dim - 1, seg_dim], [entropies[seg_dim - 1][1], entropies[seg_dim][1]], 'k-')
        plt.grid(True)

    plt.xlabel('Grid Size')
    plt.ylabel('Average Entropy (Top 25% Segments)')
    plt.title('Average Entropy vs Grid Size (Logarithmic Scale)')
    plt.yscale('log')

    plt.gcf().set_size_inches(12, 6)
    plt.show()


def main():
    n = 25

    path = '../Flowers/'
    name = 'cropped.jpg'
    im = path + name

    entropies, entropies_sorted = maximise_entropy(im, name, n)


    # Grid size which maximises average entropy
    grid_size = entropies_sorted[0][0]


    # Plot heatmap of grid size which maximises average entropy
    plot_heatmap(im, grid_size, name)


    # Average Entropy vs Grid Size (Logarithmic Scale)
    plot_entropy_vs_grid_size(entropies, name)

    # Top 4 Grid Sizes
    plt.figure(name + ' SaRa Output - Top 4 Grid Sizes')
    plt.gcf().set_size_inches(12, 6)

    for i in range(4):
        plt.subplot(2, 2, i + 1)
        im = cv2.imread(entropies_sorted[i][1][3])
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        plt.imshow(im)
        plt.xticks([])
        plt.yticks([])
        plt.title(str(entropies_sorted[i][1][0]) +
                  ' x ' + str(entropies_sorted[i][1][0]))

    plt.show()
    cv2.waitKey()


if __name__ == '__main__':
    main()
