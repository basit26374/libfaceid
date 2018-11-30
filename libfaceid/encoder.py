import os
import numpy as np
from enum import Enum
import cv2                     # for FaceEncoderModels.LBPH, FaceEncoderModels.OPENFACE
import pickle                  # for FaceEncoderModels.OPENFACE and FaceEncoderModels.DLIBRESNET
from imutils import paths      # for FaceEncoderModels.LBPH
from sklearn.preprocessing import LabelEncoder # for FaceEncoderModels
import dlib                    # for FaceEncoderModels.DLIBRESNET
from libfaceid.classifier import FaceClassifierModels, FaceClassifier



OUTPUT_LBPH_CLASSIFIER     = 'lbph.yml'
OUTPUT_LBPH_LABELER        = 'lbph_le.pickle'

INPUT_OPENFACE_MODEL       = 'openface_nn4.small2.v1.t7'
OUTPUT_OPENFACE_CLASSIFIER = 'openface_re.pickle'
OUTPUT_OPENFACE_LABELER    = 'openface_le.pickle'

INPUT_DLIBRESNET_MODEL       = 'dlib_face_recognition_resnet_model_v1.dat'
INPUT_DLIBRESNET_MODEL2      = 'shape_predictor_5_face_landmarks.dat'
OUTPUT_DLIBRESNET_CLASSIFIER = 'dlib_re.pickle'
OUTPUT_DLIBRESNET_LABELER    = 'dlib_le.pickle'


class FaceEncoderModels(Enum):

    LBPH                = 0    # [ML] LBPH Local Binary Patterns Histograms
    OPENFACE            = 1    # [DL] OpenCV OpenFace
    DLIBRESNET          = 2    # [DL] DLIB ResNet
    # VGGFACE1_VGG16    = 3    # Refer to models\others\vggface_recognition
    # VGGFACE2_RESNET50 = 4    # Refer to models\others\vggface_recognition
    # FACENET           = 5    # Refer to models\others\facenet-master_recognition


class FaceEncoder():

    def __init__(self, model=FaceEncoderModels.LBPH, path=None, path_training=None, training=False):
        self._base = None
        if model == FaceEncoderModels.LBPH:
            self._base = FaceEncoder_LBPH(path, path_training, training)
        elif model == FaceEncoderModels.OPENFACE:
            self._base = FaceEncoder_OPENFACE(path, path_training, training)
        elif model == FaceEncoderModels.DLIBRESNET:
            self._base = FaceEncoder_DLIBRESNET(path, path_training, training)

    def identify(self, frame, face_rect):
        return self._base.identify(frame, face_rect)

    def train(self, face_detector, path_dataset, verify=False, classifier=FaceClassifierModels.LINEAR_SVM):
        self._base.train(face_detector, path_dataset, verify, classifier)


class FaceEncoder_LBPH():

    def __init__(self, path=None, path_training=None, training=False):
        self.path = path
        self.path_training = path_training
        self.clf = None
        self.embedder = None
        self.label_encoder = None
        self.shaper = None

        self.clf = cv2.face.LBPHFaceRecognizer_create()
        if training == False:
            self.clf.read(self.path_training + OUTPUT_LBPH_CLASSIFIER)
            self.label_encoder = pickle.loads(open(self.path_training + OUTPUT_LBPH_LABELER, "rb").read())
            print(self.label_encoder.classes_)

    def identify(self, frame, face_rect):
        face_id = "Unknown"
        confidence = 99.99
        (x, y, w, h) = face_rect
        frame_gray = frame[y:y+h, x:x+w]
        face = cv2.cvtColor(frame_gray, cv2.COLOR_BGR2GRAY)
        try:
            id, confidence = self.clf.predict(face)
            if confidence > 99.99: 
                confidence = 99.99
            face_id = self.label_encoder.classes_[id]
            #print("{} {}", self.names[id], face_id)
        except:
            print("except occurred")
        return face_id, confidence

    def train(self, face_detector, path_dataset, verify, classifier):
        imagePaths = sorted(list(paths.list_images(path_dataset)))
        faceSamples=[]
        ids = []
        knownNames = []

        id = -1
        for (i, imagePath) in enumerate(imagePaths):
            frame = cv2.imread(imagePath, cv2.IMREAD_COLOR)
            name = imagePath.split(os.path.sep)[-2]
            try:
                id = knownNames.index(name)
            except:
                id = id + 1
            print("name=%s id=%d" % (name, id))

            # FACE DETECTION
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_detector.detect(frame)
            for (index, face) in enumerate(faces):
                (x, y, w, h) = face
                faceSamples.append(frame_gray[y:y+h,x:x+w])
                knownNames.append(name)
                ids.append(id)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 1)
                break

            if verify and len(faces) != 1:
                print("\n [INFO] Image {} has {} faces ".format(imagePath, len(faces)))
                cv2.imshow('frame', frame)
                cv2.waitKey(1000)
        print(ids)
        print(knownNames)

        self.clf.train(faceSamples, np.array(ids))
        self.clf.write(self.path_training + OUTPUT_LBPH_CLASSIFIER)

        le = LabelEncoder()
        labels = le.fit_transform(knownNames)
        print(le.classes_)
        print(labels)
        
        f = open(self.path_training + OUTPUT_LBPH_LABELER, "wb")
        f.write(pickle.dumps(le))
        f.close()


class FaceEncoder_OPENFACE():

    def __init__(self, path=None, path_training=None, training=False):
        self.path = path
        self.path_training = path_training
        self.clf = None
        self.embedder = None
        self.label_encoder = None
        self.shaper = None

        self.embedder = cv2.dnn.readNetFromTorch(self.path + INPUT_OPENFACE_MODEL)
        if training == False:
            self.clf = pickle.loads(open(self.path_training + OUTPUT_OPENFACE_CLASSIFIER, "rb").read())
            self.label_encoder = pickle.loads(open(self.path_training + OUTPUT_OPENFACE_LABELER, "rb").read())
            print(self.label_encoder.classes_)

    def identify(self, frame, face_rect):
        face_id = "Unknown"
        confidence = 99.99
        (x, y, w, h) = face_rect
        face = frame[y:y+h, x:x+w]
        faceBlob = cv2.dnn.blobFromImage(face, 1.0 / 255, (96, 96), (0, 0, 0), swapRB=True, crop=False)
        self.embedder.setInput(faceBlob)
        vec = self.embedder.forward()

        predictions_face = self.clf.predict(vec)[0]
        id = np.argmax(predictions_face)
        confidence = predictions_face[id] * 100
        face_id = self.label_encoder.classes_[id]
        return face_id, confidence

    def train(self, face_detector, path_dataset, verify, classifier):
        knownEmbeddings = []
        knownNames = []
        total = 0

        imagePaths = sorted(list(paths.list_images(path_dataset)))

        for (j, imagePath) in enumerate(imagePaths):
            print("[INFO] processing image {}/{}".format(j + 1, len(imagePaths)))
            name = imagePath.split(os.path.sep)[-2]
            print(name)

            frame = cv2.imread(imagePath, cv2.IMREAD_COLOR)
            frame_rgb = frame[:, :, ::-1]

            faces = face_detector.detect(frame)
            for (index, face) in enumerate(faces):
                (x, y, w, h) = face
                face = frame_rgb[y:y+h, x:x+w]
                
                faceBlob = cv2.dnn.blobFromImage(face, 1.0 / 255, (96, 96), (0, 0, 0), swapRB=True, crop=False)
                self.embedder.setInput(faceBlob)
                vec = self.embedder.forward()
                print("vecshape={}".format(vec.shape))
                print("vec={}".format(vec))
                
                knownNames.append(name)
                knownEmbeddings.append(vec.flatten())
                total += 1

        print(len(knownNames))
        print(len(knownEmbeddings))
        print("[INFO] Number of images = {}".format(total))
        print("[INFO] Number of classes = {}".format(knownNames))

        le = LabelEncoder()
        labels = le.fit_transform(knownNames)
        print(le.classes_)
        print(labels)

        clf = FaceClassifier(classifier)
        clf.fit(knownEmbeddings, labels)

        f = open(self.path_training + OUTPUT_OPENFACE_CLASSIFIER, "wb")
        f.write(pickle.dumps(clf))
        f.close()

        f = open(self.path_training + OUTPUT_OPENFACE_LABELER, "wb")
        f.write(pickle.dumps(le))
        f.close()


class FaceEncoder_DLIBRESNET():


    def __init__(self, path=None, path_training=None, training=False):
        self.path = path
        self.path_training = path_training
        self.clf = None
        self.embedder = None
        self.label_encoder = None
        self.shaper = None

        self.embedder = dlib.face_recognition_model_v1(self.path + INPUT_DLIBRESNET_MODEL)
        self.shaper = dlib.shape_predictor(self.path + INPUT_DLIBRESNET_MODEL2)
        if training == False:
            self.clf = pickle.loads(open(self.path_training + OUTPUT_DLIBRESNET_CLASSIFIER, "rb").read())
            self.label_encoder = pickle.loads(open(self.path_training + OUTPUT_DLIBRESNET_LABELER, "rb").read())
            print(self.label_encoder.classes_)

    def identify(self, frame, face_rect):
        face_id = "Unknown"
        confidence = 99.99
        (x, y, w, h) = face_rect
        rect = dlib.rectangle(x, y, x+w, y+h)
        frame_rgb = frame[:, :, ::-1]
        shape = self.shaper(frame_rgb, rect)
        vec = self.embedder.compute_face_descriptor(frame_rgb, shape)

        vec = np.array([vec])
        predictions_face = self.clf.predict(vec)[0]
        print(predictions_face)
        id = np.argmax(predictions_face)
        confidence = predictions_face[id] * 100
        face_id = self.label_encoder.classes_[id]
        return face_id, confidence

    def train(self, face_detector, path_dataset, verify, classifier):
        knownEmbeddings = []
        knownNames = []
        total = 0

        imagePaths = sorted(list(paths.list_images(path_dataset)))

        for (j, imagePath) in enumerate(imagePaths):
            print("[INFO] processing image {}/{}".format(j + 1, len(imagePaths)))
            name = imagePath.split(os.path.sep)[-2]
            print(name)

            frame = cv2.imread(imagePath, cv2.IMREAD_COLOR)
            frame_rgb = frame[:, :, ::-1]

            faces = face_detector.detect(frame)
            for (index, face) in enumerate(faces):
                (x, y, w, h) = face
                rect = dlib.rectangle(x, y, x+w, y+h)

                shape = self.shaper(frame_rgb, rect)
                vec = self.embedder.compute_face_descriptor(frame, shape)
                print("vecshape={}".format(vec.shape))
                vec = np.array([vec])
                print("NEW vecshape={}".format(vec.shape))
                print("vec={}".format(vec))

                knownNames.append(name)
                knownEmbeddings.append(vec.flatten())
                total += 1

        print(len(knownNames))
        print(len(knownEmbeddings))
        print("[INFO] Number of images = {}".format(total))
        print("[INFO] Number of classes = {}".format(knownNames))

        le = LabelEncoder()
        labels = le.fit_transform(knownNames)
        print(le.classes_)
        print(labels)

        clf = FaceClassifier(classifier)
        clf.fit(knownEmbeddings, labels)

        f = open(self.path_training + OUTPUT_DLIBRESNET_CLASSIFIER, "wb")
        f.write(pickle.dumps(clf))
        f.close()

        f = open(self.path_training + OUTPUT_DLIBRESNET_LABELER, "wb")
        f.write(pickle.dumps(le))
        f.close()


