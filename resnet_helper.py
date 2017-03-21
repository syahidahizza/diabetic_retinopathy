from __future__ import print_function
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers import merge, Dropout
from keras.layers.convolutional import Convolution2D, Convolution3D, MaxPooling2D, MaxPooling3D, ZeroPadding2D, ZeroPadding3D, AveragePooling2D, AveragePooling3D
from keras.layers.core import Dense, Activation, Flatten, Dropout
from keras.layers.normalization import BatchNormalization
from keras.metrics import *
from keras.models import Model
from keras.layers import Input
from keras.preprocessing import image
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img
from keras.optimizers import RMSprop, SGD
# from skimage.transform import rotate

import keras.backend as K
import numpy as np
# import pylab
import glob
import cv2
import sklearn.metrics
import sklearn.preprocessing as skp


def extract_contour(image, gray):
    # this is a good threshold for Canny edge finder, but it does not always work. We will see how to deal with it
    #     furhter on.
    #     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = 20

    # Canny edge finder
    edges = np.array([], dtype=np.uint8)
    edges = cv2.Canny(gray, thresh, thresh * 3, edges)

    # Find contours
    # second output is hierarchy - we are not interested in it.
    _, contours, hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Let's see what we've got:
    return display_contours(image, contours, thickness=2)


# Function to display contours using OpenCV.
def display_contours(image, contours, color=(255, 0, 0), thickness=-1, title=None):
    # Contours are drawn on the original image, so let's make a copy first
    #     imShow = image.copy()
    imShow = np.ones([128, 128, 3], dtype=np.uint8)
    for i in range(0, len(contours)):
        cv2.drawContours(imShow, contours, i, color, thickness)

    gray_image = cv2.cvtColor(imShow, cv2.COLOR_BGR2GRAY)
    return toBinary(gray_image)


def toBinary(image):
    result = np.zeros([128, 128], dtype='uint8')
    for i in range(len(image)):
        for j in range(len(image[i])):
            result[i][j] = 0 if image[i][j] > 1 else 1
    return result


def recall_metrics(y_true, y_pred):
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
    recall = true_positives / (possible_positives + K.epsilon())
    return recall


def precision_metrics(y_true, y_pred):
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
    precision = true_positives / (predicted_positives + K.epsilon())
    return precision


def f1_metrics(y_true, y_pred, beta=1):
    if beta < 0:
        raise ValueError('The lowest choosable beta is zero (only precision).')

    # If there are no true positives, fix the F score at 0 like sklearn.
    if K.sum(K.round(K.clip(y_true, 0, 1))) == 0:
        return 0

    p = precision_metrics(y_true, y_pred)
    r = recall_metrics(y_true, y_pred)
    bb = beta ** 2
    fbeta_score = (1 + bb) * (p * r) / (bb * p + r + K.epsilon())

    return fbeta_score

def to_categorical(arr):
    size = arr.shape[0]
    max_val = np.amax(arr) + 1
    result = np.empty([size, max_val], dtype=np.uint8)
    for i in range(0, size):
        for val in range(0, max_val):
            if val == arr[i]:
                result[i][val] = 1
            else:
                result[i][val] = 0

    return result

def gray_to_color(arr):
    size = arr.shape[0]
    x = arr.shape[1]
    y = arr.shape[2]

    result = np.empty([size, 3, x, y], dtype=np.uint8)
    for i in range(0, size):
        element = np.empty([3, x, y])
        element[0] = arr[i]
        element[1] = arr[i]
        element[2] = arr[i]
        result[i] = element

    return result


def load_dataset(datatype, preprocess=False, categorical=True, filterdataset=False, zoom=True, shuffle=True):
    #     base_location = "dataset/";
    base_location = ""
    images = []
    labels = []

    # only use when filterdataset is true
    mean = 0
    images_mean = []
    if filterdataset:
        for f in glob.glob(base_location + datatype + "/*"):
            for img in glob.glob(f + "/*.jpeg"):
                image = cv2.imread(img)
                images_mean.append(image.mean())

        images_mean = np.array(images_mean)
        mean = images_mean.mean()
        print("mean images" + str(mean))

    for f in glob.glob(base_location + datatype + "/*"):
        #         label = int(f.split("/")[2])
        label = int(f.split("/")[3])
        #         for img in glob.glob(f + "/*.jpeg") :
        for img in glob.glob(f + "/*.tiff"):
            image = cv2.imread(img)

            if image.mean() > mean:

                if preprocess:
                    image = convert_image(image, zoom)

                swaper = np.empty([3, 224, 224], dtype=np.uint8)
                for channel in range(0, 3):
                    swaper[channel] = image[:, :, channel]

                labels.append(label)
                images.append(swaper)

    images = np.array(images, dtype=np.uint8)
    labels = np.array(labels, dtype=np.uint8)

    if categorical:
        labels = to_categorical(labels)

    print("dataset loaded total dataset " + str(len(labels)))

    if shuffle:
        return unison_shuffled_copies(images, labels)

    return images, labels

def scaleImages(images):
    R_list = []
    G_list = []
    B_list = []

    size = 224 * 224
    for img in images:
        R_list.append(img[0].reshape(size))
        G_list.append(img[1].reshape(size))
        B_list.append(img[2].reshape(size))

    R_list_2 = skp.scale(R_list, axis=0)
    G_list_2 = skp.scale(G_list, axis=0)
    B_list_2 = skp.scale(B_list, axis=0)

    result = np.empty([len(images), 3, 224, 224], dtype=np.uint8)
    for i in range(0, len(R_list)):
        result[i][0] = R_list[i].reshape(224, 224)
        result[i][1] = G_list[i].reshape(224, 224)
        result[i][2] = B_list[i].reshape(224, 224)
    return result


def rotate_dataset(images, degree):
    for i in range(0, len(images)):
        images[i] = rotate(images[i], degree)
    return images


def convert_image(image, zoom=True):
    scale = 64
    # scale image to a given radius
    # a = scaleRadius(image, scale)

    # subtract local mean color to reduce noise
    a = image
    a = cv2.addWeighted(a, 4, cv2.GaussianBlur(a, (0, 0), scale / 30), -4, 128)

    if zoom:
        # remove outer 10%
        b = np.zeros(a.shape)
        cv2.circle(b, (int((a.shape[1] / 2)), int(a.shape[0] / 2)), int(scale * 0.9), (1, 1, 1), -1, 8, 0)
        a = a * b + 128 * (1 - b)
    return a


def get_predicted_classes(result, y_test):
    predit_classes = np.empty([53576], dtype=np.uint8)
    index = 0;
    for sample in result:
        predict_class = np.argmax(sample)
        predit_classes[index] = predict_class
        index += 1

    expected_classes = np.empty([53576], dtype=np.uint8)
    index = 0;
    for sample in y_test:
        predict_class = np.argmax(sample)
        expected_classes[index] = predict_class
        index += 1

    return predit_classes, expected_classes


def not_continue_epoch():
    with open('config.txt', mode="r") as f:
        for line in f:
            reader = line.split()
            print(eval(reader[0]))
            return eval(reader[0]) 