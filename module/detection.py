import numpy as np
from google.protobuf import text_format
from caffe.proto import caffe_pb2
import os
import caffe
import hashlib

class SSDDetect:
    def __init__(self, weights_path, def_path,
    labelmap_path=os.path.expanduser('~/SSD-instruments/data/ILSVRC2016/labelmap_ilsvrc_det.prototxt')):
        """
        weights_path = path to model weights (.caffemodel)
        def_path = path to model definition (deploy.prototxt)
        """
        self.def_path = def_path
        self.labelmap_path = labelmap_path

        expected_hash = ''
        #TODO: versioning
        if not validate_file(weights_path, expected_hash):
            # TODO: Download correct weights
            weights_path = ''

        self.weights_path = weights_path

        caffe.set_device(0)
        caffe.set_mode_gpu()


    def validate_file(fpath, file_hash, algorithm='auto', chunk_size=65535):
        """Validates a file against a sha256 or md5 hash.
        From keras/data_utils.py
        # Arguments
        fpath: path to the file being validated
        file_hash:  The expected hash string of the file.
        The sha256 and md5 hash algorithms are both supported.
        algorithm: Hash algorithm, one of 'auto', 'sha256', or 'md5'.
        The default 'auto' detects the hash algorithm in use.
        chunk_size: Bytes to read at a time, important for large files.
        # Returns
        Whether the file is valid
        """
        if ((algorithm is 'sha256') or (algorithm is 'auto' and len(file_hash) is 64)):
            hasher = 'sha256'
        else:
            hasher = 'md5'

        if str(_hash_file(fpath, hasher, chunk_size)) == str(file_hash):
            return True
        else:
            return False


    def _hash_file(fpath, algorithm='sha256', chunk_size=65535):
        """Calculates a file sha256 or md5 hash.
        From keras/data_utils.py
        # Example
        ```python
        >>> from keras.data_utils import _hash_file
        >>> _hash_file('/path/to/file.zip')
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        ```
        # Arguments
        fpath: path to the file being validated
        algorithm: hash algorithm, one of 'auto', 'sha256', or 'md5'.
        The default 'auto' detects the hash algorithm in use.
        chunk_size: Bytes to read at a time, important for large files.
        # Returns
        The file hash
        """
        if (algorithm is 'sha256') or (algorithm is 'auto' and len(hash) is 64):
            hasher = hashlib.sha256()
        else:
            hasher = hashlib.md5()

        with open(fpath, 'rb') as fpath_file:
            for chunk in iter(lambda: fpath_file.read(chunk_size), b''):
                hasher.update(chunk)

        return hasher.hexdigest()


    def get_labelname(labelmap, labels):
        """
        Retrieves human-readable labels from labelmap file
        From ssd_detect.ipynb in SSD repo
        """
        num_labels = len(labelmap.item)
        labelnames = []
        if type(labels) is not list:
            labels = [labels]
        for label in labels:
            found = False
            for i in xrange(0, num_labels):
                if label == labelmap.item[i].label:
                    found = True
                    labelnames.append(labelmap.item[i].display_name)
                    break
            assert found == True
        return labelnames


    # TODO: adjust for image batches? - determine whether necessary
    def detect(self, image_path, batch_size=1):
        f = open(self.labelmap_path, 'r')
        labelmap = caffe_pb2.LabelMap()
        text_format.Merge(str(file.read()), labelmap)

        model_def = self.def_path
        model_weights = self.weights_path

        net = caffe.Net(model_def, model_weights, caffe.TEST)

        # input preprocessing: 'data' is the name of the input blob == net.inputs[0]
        transformer = caffe.io.Transformer({'data': net.blobs['data'].data.shape})
        transformer.set_transpose('data', (2, 0, 1))
        transformer.set_mean('data', np.array([104,117,123])) # mean pixel
        transformer.set_raw_scale('data', 255)  # the reference model operates on images in [0,255] range instead of [0,1]
        transformer.set_channel_swap('data', (2,1,0))  # the reference model has channels in BGR order instead of RGB

        image_resize = 300
        net.blobs['data'].reshape(batch_size, 3, image_resize, image_resize)
        image = caffe.io.load_image(image_path)

        transformed_image = transformer.preprocess('data', image)
        net.blobs['data'].data[...] = transformed_image

        # Forward pass.
        detections = net.forward()['detection_out']

        # Parse the outputs.
        det_label = detections[0,0,:,1]
        det_conf = detections[0,0,:,2]
        det_xmin = detections[0,0,:,3]
        det_ymin = detections[0,0,:,4]
        det_xmax = detections[0,0,:,5]
        det_ymax = detections[0,0,:,6]

        # Get detections with confidence higher than 0.6.
        top_indices = [i for i, conf in enumerate(det_conf) if conf >= 0.6]

        top_conf = det_conf[top_indices]
        top_label_indices = det_label[top_indices].tolist()
        top_labels = get_labelname(labelmap, top_label_indices)
        top_xmin = det_xmin[top_indices]
        top_ymin = det_ymin[top_indices]
        top_xmax = det_xmax[top_indices]
        top_ymax = det_ymax[top_indices]

        boxes = []
        # Tuples formatted ((xmin, ymin, w, h), score, label)
        # where label is human-readable label
        for i in xrange(top_conf.shape[0]):
            xmin = int(round(top_xmin[i] * image.shape[1]))
            ymin = int(round(top_ymin[i] * image.shape[0]))
            xmax = int(round(top_xmax[i] * image.shape[1]))
            ymax = int(round(top_ymax[i] * image.shape[0]))
            score = top_conf[i]
            label = int(top_label_indices[i])
            label_name = top_labels[i]
            coords = (xmin, ymin, xmax-xmin+1, ymax-ymin+1)
            tup = (coords, score, label_name)
            boxes.append(tup)

        return boxes

    # TODO: determine whether this is necessary
    def detect_batches(self, image_dir, batch_size):
        # TODO
        pass
