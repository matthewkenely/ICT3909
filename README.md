<h1>Abstract</h1>

<i>
In today’s digital age where the photograph is paramount in interest stimulation, news outlets engage in constant competition for our attention towards advertisements and news articles. Thus, the need for a saliency model capable of approximating visual attention and ranking interface elements based on how much prioritisation they garner from the human visual system is becoming ever more prevalent.

While the application of saliency to traditional photographs has seen rapid development in recent years, its application in the context of user interfaces has been scarce. The aim of this project was two-fold: to optimise an existing saliency ranking framework (SaRa) which could be used to measure attention distribution fairness in news websites by organising interface elements into a rank hierarchy, and to curate a dataset of attention within user interfaces which indicates the extent to which distracting elements detract from the user experience. This dataset would subsequently be used to evaluate SaRa qualitatively.

Quantitative evaluation was carried out by assessing the optimised SaRa framework in the task of saliency ranking on a dataset combining object masks from MS-COCO and fixation sequences from SALICON. It was subsequently compared to its original version, as well as to current state-of-the-art models on the Salient Object Ranking (SOR) metric. The proposed optimisations were found to be successful, allowing SaRa to achieve a SOR score of 0.724, proving comparable to state-of-the-art performance and resulting in an increase of 0.07 (10.7\%) when compared to the original framework.

The saliency dataset was curated through the collection of gaze location data within Maltese news website interfaces using an eye-tracker as well as an online experiment where mouse trajectories/taps were tracked. The eye-tracking and online experiments consisted of 30 and 363 participants respectively. Participants were split into a control and experimental group. Each of these groups had the excessively salient elements either included or removed, with the discrepancy between them serving as an indicator of how distracting the excessively salient elements were.

Qualitative evaluation was carried out through a discussion comparing the heat-maps gathered from the experiments to the saliency rank predictions made by SaRa. SaRa was found to work well as a framework for the assessment of attention distribution fairness in news website user interfaces, and its saliency generator backbone, DeepGaze IIE, accurately captured the attention observed in the experiments.

Moving forward, work which contributes to the creation of large-scale datasets featuring saliency within a variety of user interfaces is proposed, with the scope of pushing saliency models toward greater reliability in the task of attention distribution fairness assessment, as well as to serve as a benchmark on which these models can be evaluated.
</i>
