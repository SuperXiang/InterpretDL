from assets.resnet import ResNet50
import paddle.fluid as fluid
import numpy as np
import sys
sys.path.append('..')
import interpretdl as it
from interpretdl.data_processor.readers import preprocess_image, read_image
from interpretdl.data_processor.visualizer import visualize_grayscale
from PIL import Image
import cv2


def grad_shap_example():
    def predict_fn(data):

        class_num = 1000
        model = ResNet50()
        logits = model.net(input=data, class_dim=class_num)

        probs = fluid.layers.softmax(logits, axis=-1)
        return probs

    img_path = 'assets/catdog.png'

    gs = it.GradShapCVInterpreter(predict_fn, "assets/ResNet50_pretrained",
                                  True)
    gradients = gs.interpret(
        img_path,
        labels=None,
        noise_amount=0.1,
        n_samples=20,
        visual=True,
        save_path='assets/gs_test.jpg')


if __name__ == '__main__':
    grad_shap_example()
