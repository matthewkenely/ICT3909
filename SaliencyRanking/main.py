import cv2
import numpy as np
import matplotlib.pyplot as plt
import saraRC1 as sara

def maximise_entropy(im, name, n=25):
    '''
    Given an image im, this function returns the grid size that maximises the average entropy of the top n segments generated by SaRa.
    '''

    entropies = []
    s1 = cv2.imread(im)

    plt.figure(name + ' SaRa Output - All Grid Sizes')
    plt.gcf().set_size_inches(12, 6)

    for i in range(5, 15):
        heatmap, sara_list = sara.return_sara(s1.copy(), i)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # Plot heatmap of grid size i x i
        plt.subplot(2, 5, i - 4)
        plt.imshow(heatmap)
        plt.xticks([])
        plt.yticks([])
        plt.title(str(i) + ' x ' + str(i))

        # Output heatmap to file
        path = './output/' + str(i) + 'x' + str(i) + '.png'
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_RGB2BGR)
        cv2.imwrite(path, heatmap)

        # Average entropy of the top 25% grid segments
        top = i * i // 4

        average = sum(sara_list[0:top][1]) / len(sara_list[0:n][1])
        entropies.append((i, average, path))

        print(f'Image saved to {path}')

        sara.reset()

    ranks = entropies.copy()
    entropies.sort(key=lambda x: x[1], reverse=True)

    return entropies, ranks

def main():
    n = 25

    path = '../COTS Dataset/Part 1 - Single Objects/objects/'
    name = 'cmt_mug_colour.jpeg'
    im = path + name

    entropies, ranks = maximise_entropy(im, name, n)
    grid_size = entropies[0][0]

    heatmap, _ = sara.return_sara(cv2.imread(im), grid_size)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    plt.figure(name + ' SaRa Output - Grid Size ' + str(grid_size) + ' x ' + str(grid_size))
    plt.gcf().set_size_inches(12, 6)
    plt.imshow(heatmap)
    plt.xticks([])
    plt.yticks([])
    plt.title('SaRa Output - Grid Size ' + str(grid_size) + ' x ' + str(grid_size))

    for i in ranks:
        print(i)

    plt.figure(name + ' Average Entropy vs Grid Size (Logarithmic Scale)')
    plt.plot([i[0] for i in ranks], [i[1] for i in ranks], 'k')
    plt.plot([i[0] for i in ranks], [i[1] for i in ranks], 'bo')
    plt.grid(True)
    plt.xlabel('Grid Size')
    plt.ylabel('Average Entropy (Top ' + str(n) + ' Segments)')
    plt.title('Average Entropy vs Grid Size (Logarithmic Scale)')
    plt.yscale('log')

    plt.gcf().set_size_inches(12, 6)


    plt.figure(name + ' SaRa Output - Top 4 Grid Sizes')
    plt.gcf().set_size_inches(12, 6)

    for i in range(4):
        plt.subplot(2, 2, i + 1)
        im = cv2.imread(entropies[i][2])
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        plt.imshow(im)
        plt.xticks([])
        plt.yticks([])
        plt.title(str(entropies[i][0]) + ' x ' + str(entropies[i][0]))

        

    plt.show()




    cv2.waitKey()


if __name__ == '__main__':
    main()
