# coding: utf-8
"""
    functions
"""

# coding: utf-8

import os
from os.path import join, exists
import time
import cv2
import numpy as np


def logger(msg):
    """
        log message
    """
    now = time.ctime()
    print("[%s] %s" % (now, msg))

def createDir(p):
    if not os.path.exists(p):
        os.mkdir(p)

def shuffle_in_unison_scary(a, b):
    rng_state = np.random.get_state()
    np.random.shuffle(a)
    np.random.set_state(rng_state)
    np.random.shuffle(b)

def drawLandmark(img, bbox, landmark):
    cv2.rectangle(img, (bbox.left, bbox.top), (bbox.right, bbox.bottom), (0,0,255), 2)
    for x, y in landmark:
        cv2.circle(img, (int(x), int(y)), 2, (0,255,0), -1)
    return img

def getDataFromTxt(txt, with_landmark=True):
    """
        Generate data from txt file
        return [(img_path, bbox, landmark)]
            bbox: [left, right, top, bottom]
            landmark: [(x1, y1), (x2, y2), ...]
    """
    dirname = os.path.dirname(txt)
    with open(txt, 'r') as fd:
        lines = fd.readlines()

    result = []
    for line in lines:
        line = line.strip()
        components = line.split(' ')
        img_path = os.path.join(dirname, components[0].replace('\\', '/')) # file path
        # bounding box, (left, right, top, bottom)
        bbox = (components[1], components[2], components[3], components[4])
        bbox = [int(_) for _ in bbox]
        # landmark
        if not with_landmark:
            result.append((img_path, BBox(bbox)))
            continue
        landmark = np.zeros((5, 2))
        for index in range(0, 5):
            rv = (float(components[5+2*index]), float(components[5+2*index+1]))
            landmark[index] = rv
        for index, one in enumerate(landmark):
            rv = ((one[0]-bbox[0])/(bbox[1]-bbox[0]), (one[1]-bbox[2])/(bbox[3]-bbox[2]))
            landmark[index] = rv
        result.append((img_path, BBox(bbox), landmark))
    return result

def getPatch(img, bbox, point, padding):
    """
        Get a patch iamge around the given point in bbox with padding
        point: relative_point in [0, 1] in bbox
    """
    point_x = bbox.x + point[0] * bbox.w
    point_y = bbox.y + point[1] * bbox.h
    patch_left = point_x - bbox.w * padding
    patch_right = point_x + bbox.w * padding
    patch_top = point_y - bbox.h * padding
    patch_bottom = point_y + bbox.h * padding
    patch = img[patch_top: patch_bottom+1, patch_left: patch_right+1]
    patch_bbox = BBox([patch_left, patch_right, patch_top, patch_bottom])
    return patch, patch_bbox


def processImage(imgs):
    """
        process images before feeding to CNNs
        imgs: N x 1 x W x H
    """
    imgs = imgs.astype(np.float32)
    for i, img in enumerate(imgs):
        m = img.mean()
        s = img.std()
        imgs[i] = (img - m) / s
    return imgs
    
class BBox(object):
    """
        Bounding Box of face
    """
    def __init__(self, bbox):
        self.left = bbox[0]
        self.right = bbox[1]
        self.top = bbox[2]
        self.bottom = bbox[3]
        self.x = bbox[0]
        self.y = bbox[2]
        self.w = bbox[1] - bbox[0]
        self.h = bbox[3] - bbox[2]

    def expand(self, scale=0.05):
        bbox = [self.left, self.right, self.top, self.bottom]
        bbox[0] -= int(self.w * scale)
        bbox[1] += int(self.w * scale)
        bbox[2] -= int(self.h * scale)
        bbox[3] += int(self.h * scale)
        return BBox(bbox)

    def project(self, point):
        x = (point[0]-self.x) / self.w
        y = (point[1]-self.y) / self.h
        return np.asarray([x, y])

    def reproject(self, point):
        x = self.x + self.w*point[0]
        y = self.y + self.h*point[1]
        return np.asarray([x, y])

    def reprojectLandmark(self, landmark):
        p = np.zeros((len(landmark), 2))
        for i in range(len(landmark)):
            p[i] = self.reproject(landmark[i])
        return p

    def projectLandmark(self, landmark):
        p = np.zeros((len(landmark), 2))
        for i in range(len(landmark)):
            p[i] = self.project(landmark[i])
        return p

    def subBBox(self, leftR, rightR, topR, bottomR):
        leftDelta = self.w * leftR
        rightDelta = self.w * rightR
        topDelta = self.h * topR
        bottomDelta = self.h * bottomR
        left = self.left + leftDelta
        right = self.left + rightDelta
        top = self.top + topDelta
        bottom = self.top + bottomDelta
        return BBox([left, right, top, bottom])
        

def show_landmark(face, landmark):
    """
        view face with landmark for visualization
    """
    face_copied = face.copy().astype(np.uint8)
    for (x, y) in landmark:
        xx = int(face.shape[0]*x)
        yy = int(face.shape[1]*y)
        cv2.circle(face_copied, (xx, yy), 2, (0,0,0), -1)
    cv2.imshow("face_rot", face_copied)
    cv2.waitKey(0)


def rotate(img, bbox, landmark, alpha):
    """
        given a face with bbox and landmark, rotate with alpha
        and return rotated face with bbox, landmark (absolute position)
    """
    center = ((bbox.left+bbox.right)/2, (bbox.top+bbox.bottom)/2)
    rot_mat = cv2.getRotationMatrix2D(center, alpha, 1)
    img_rotated_by_alpha = cv2.warpAffine(img, rot_mat, img.shape)
    landmark_ = np.asarray([(rot_mat[0][0]*x+rot_mat[0][1]*y+rot_mat[0][2],
                 rot_mat[1][0]*x+rot_mat[1][1]*y+rot_mat[1][2]) for (x, y) in landmark])
    face = img_rotated_by_alpha[bbox.top:bbox.bottom+1,bbox.left:bbox.right+1]
    return (face, landmark_)


def flip(face, landmark):
    """
        flip face
    """
    face_flipped_by_x = cv2.flip(face, 1)
    landmark_ = np.asarray([(1-x, y) for (x, y) in landmark])
    landmark_[[0, 1]] = landmark_[[1, 0]]
    landmark_[[3, 4]] = landmark_[[4, 3]]
    return (face_flipped_by_x, landmark_)

def randomShift(landmarkGt, shift):
    """
        Random Shift one time
    """
    diff = np.random.rand(5, 2)
    diff = (2*diff - 1) * shift
    landmarkP = landmarkGt + diff
    return landmarkP

def randomShiftWithArgument(landmarkGt, shift):
    """
        Random Shift more
    """
    N = 2
    landmarkPs = np.zeros((N, 5, 2))
    for i in range(N):
        landmarkPs[i] = randomShift(landmarkGt, shift)
    return landmarkPs