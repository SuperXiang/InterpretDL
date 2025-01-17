import numpy as np

from tqdm import tqdm
from .abc_interpreter import InputGradientInterpreter
from ..data_processor.readers import images_transform_pipeline, preprocess_save_path
from ..data_processor.visualizer import explanation_to_vis, show_vis_explanation, save_image


class SmoothGradInterpreterV2(InputGradientInterpreter):
    """

    Smooth Gradients method solves the problem of meaningless local variations in partial derivatives
    by adding random noise to the inputs multiple times and take the average of the
    gradients.

    More details regarding the Smooth Gradients method can be found in the original paper:
    http://arxiv.org/pdf/1706.03825.pdf
    """

    def __init__(self,
                 paddle_model,
                 use_cuda=None,
                 device='gpu:0'):
        """

        Args:
            paddle_model (callable): A model with ``forward`` and possibly ``backward`` functions.
            device (str): The device used for running `paddle_model`, options: ``cpu``, ``gpu:0``, ``gpu:1`` etc.
            use_cuda (bool):  Would be deprecated soon. Use ``device`` directly.
        """
        
        InputGradientInterpreter.__init__(self, paddle_model, device, use_cuda)

    def interpret(self,
                  inputs,
                  labels=None,
                  noise_amount=0.1,
                  n_samples=50,
                  split=2,
                  resize_to=224, 
                  crop_to=None,
                  visual=True,
                  save_path=None):
        """
        Main function of the interpreter. This passes the unit tests of test_cv and test_cv_class.

        Args:
            inputs (str or list of strs or numpy.ndarray): The input image filepath or a list of filepaths or numpy array of read images.
            labels (list or tuple or numpy.ndarray, optional): The target labels to analyze. The number of labels should be equal to the number of images. If None, the most likely label for each image will be used. Default: None
            noise_amount (float, optional): Noise level of added noise to the image.
                                            The std of Guassian random noise is noise_amount * (x_max - x_min). Default: 0.1
            n_samples (int, optional): The number of new images generated by adding noise. Default: 50
            resize_to (int, optional): [description]. Images will be rescaled with the shorter edge being `resize_to`. Defaults to 224.
            crop_to ([type], optional): [description]. After resize, images will be center cropped to a square image with the size `crop_to`. 
                If None, no crop will be performed. Defaults to None.
            visual (bool, optional): Whether or not to visualize the processed image. Default: True
            save_path (str or list of strs or None, optional): The filepath(s) to save the processed image(s). If None, the image will not be saved. Default: None

        :return: interpretations/gradients for each image
        :rtype: numpy.ndarray
        """

        imgs, data = images_transform_pipeline(inputs, resize_to, crop_to)
        # print(imgs.shape, data.shape, imgs.dtype, data.dtype)  # (1, 224, 224, 3) (1, 3, 224, 224) uint8 float32

        assert len(data) == 1, "interpret each sample individually, it is optimized."

        self._build_predict_fn(gradient_of='probability')

        # obtain the labels (and initialization).
        if labels is None:
            _, preds = self.predict_fn(data, None)
            labels = preds

        labels = np.array(labels).reshape((1, ))

        # SmoothGrad
        max_axis = tuple(np.arange(1, data.ndim))
        stds = noise_amount * (
            np.max(data, axis=max_axis) - np.min(data, axis=max_axis))

        data_noised = []
        for i in range(n_samples):
            noise = np.concatenate([
                np.float32(
                    np.random.normal(0.0, stds[j], (1, ) + tuple(d.shape)))
                for j, d in enumerate(data)
            ])
            data_noised.append(data + noise)
            
        data_noised = np.concatenate(data_noised, axis=0)
        # print(data_i.shape, labels.shape)
        # print(data_noised.shape)  # n_samples, 3, 224, 224

        # splits, to avoid large GPU memory usage.
        if split > 1:
            chunk = n_samples // split
            gradient_chunks = []
            for i in range(split-1):
                gradients_i, _ = self.predict_fn(data_noised[i*chunk: (i+1) * chunk], np.repeat(labels, chunk))
                gradient_chunks.append(gradients_i)
            gradients_s, _ = self.predict_fn(data_noised[chunk*(split-1):], np.repeat(labels, n_samples - chunk*(split-1)))
            gradient_chunks.append(gradients_s)
            gradients = np.concatenate(gradient_chunks, axis=0)
        else:
            # one split.
            gradients, _ = self.predict_fn(data_noised, np.repeat(labels, n_samples))

        avg_gradients = np.mean(gradients, axis=0, keepdims=True)
        # visualize and save image.
        if save_path is None and not visual:
            # no need to visualize or save explanation results.
            pass
        else:
            save_path = preprocess_save_path(save_path, 1)
            # print(imgs[i].shape, avg_gradients[i].shape)
            vis_explanation = explanation_to_vis(imgs[i], np.abs(avg_gradients[0]).sum(0), style='overlay_grayscale')
            if visual:
                show_vis_explanation(vis_explanation)
            if save_path[i] is not None:
                save_image(save_path[i], vis_explanation)

        # intermediate results, for possible further usages.
        self.labels = labels

        return avg_gradients
