import cv2
import glob
import logging
import os
import pathlib
import pandas as pd
import numpy as np
from sklearn.datasets.base import Bunch
from scipy.io import loadmat
from functools import partial

from src import paths
from .utils import fetch_file, unpack, fetch_files


_MODULE_DIR = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


def fetch(dataset_name, data_dir=None, **kwargs):
    '''Fetch a dataset

    
    '''
    return fetch_and_unpack(dataset_name, data_dir=data_dir, do_unpack=False)

def fetch_and_unpack(dataset_name, data_dir=None, do_unpack=True):
    '''Fetch and unpack a dataset

    data_dir: string or None 
        root location of data directories.
        Raw files will be downloaded to `data_dir`/raw_data_dir
        Unpacked files will be placed in `data_dir`/interim
        if None, the values in src.paths will be used

    dataset_name:
        Name of dataset. Must be in `datasets.available_datasets`

'''
    if dataset_name not in datasets:
        raise Exception(f"Unknown Dataset: {dataset_name}")

    if data_dir is None:
        data_dir = paths.data_path
        raw_data_dir = paths.raw_data_path
        interim_data_dir = paths.interim_data_path
    else:
        data_dir = pathlib.Path(data_dir)
        raw_data_dir = data_dir / 'raw'
        interim_data_dir = data_dir / 'interim'
        
    interim_dataset_dir = interim_data_dir / dataset_name
    
    logger.info(f"Checking for {dataset_name}")
    if datasets[dataset_name].get('url_list', None):
        single_file = False
        status, results = fetch_files(dst_dir=raw_data_dir,
                                      **datasets[dataset_name])
        if status:
            logger.info(f"Retrieved Dataset successfully")
        else:
            logger.error(f"Failed to retrieve all data files: {results}")
            raise Exception("Failed to retrieve all data files")
        if do_unpack:
            for _, filename, _ in results:
                logger.info(f"Unpacking {dataset_name}")
                unpack(filename, dst_dir=interim_dataset_dir)
    else:
        single_file = True
        status, filename, hashval = fetch_file(dst_dir=raw_data_dir,
                                               **datasets[dataset_name])
        hashtype = datasets[dataset_name].get('hash_type', None)
        if status:
            logger.info(f"Retrieved Dataset: {dataset_name} "
                        f"({hashtype}: {hashval})")
        else:
            logger.error(f"Unpack to {filename} failed (hash: {hashval}). "
                         f"Status: {status}")
            raise Exception(f"Failed to download raw data: {filename}")
        if do_unpack:
            logger.info(f"Unpacking {dataset_name}")
            unpack(filename, dst_dir=interim_dataset_dir)
    if do_unpack:
        return interim_dataset_dir
    else:
        if single_file:
            return filename 
        else:
            return raw_data_dir

def load_coil_20():
    c20 = Bunch()
    feature_vectors = []
    glob_path = paths.interim_data_path / 'coil-20' / 'processed_images' / '*.pgm'
    filelist = glob.glob(str(glob_path))
    for filename in filelist:
        im = cv2.imread(filename)
        feature_vectors.append(im.flatten())

    c20['target'] = pd.Series(filelist).str.extract("obj([0-9]+)", expand=False)
    c20['data'] = np.vstack(feature_vectors)
    with open(_MODULE_DIR / 'coil-20.txt') as fd:
        c20['DESCR'] = fd.read()
    return c20

def load_coil_100():
    c100 = Bunch()
    feature_vectors = []
    glob_path = paths.interim_data_path / 'coil-100' / 'coil-100/' / '*.ppm'
    filelist = glob.glob(str(glob_path))
    for filename in filelist:
        im = cv2.imread(filename)
        feature_vectors.append(im.flatten())

    c100['target'] = pd.Series(filelist).str.extract("obj([0-9]+)", expand=False)
    c100['data'] = np.vstack(feature_vectors)
    with open(_MODULE_DIR / 'coil-100.txt') as fd:
        c100['DESCR'] = fd.read()
    return c100

def load_fmnist(kind='train', return_X_y=False):
    '''
    Load the fashion-MNIST dataset
    kind: {'train', 'test'}
        Dataset comes pre-split into training and test data.
        Indicates which dataset to load

    '''
    fmnist = Bunch()

    if kind == 'test':
        kind = 't10k'

    label_path = paths.interim_data_path / 'f-mnist' / f"{kind}-labels-idx1-ubyte"
    with open(label_path, 'rb') as fd:
        fmnist['target'] = np.frombuffer(fd.read(), dtype=np.uint8, offset=8)
    data_path = paths.interim_data_path / 'f-mnist' / f"{kind}-images-idx3-ubyte"
    with open(data_path, 'rb') as fd:
        fmnist['data'] = np.frombuffer(fd.read(), dtype=np.uint8,
                                       offset=16).reshape(len(fmnist['target']), 784)
    with open(_MODULE_DIR / 'f-mnist.txt') as fd:
        fmnist['DESCR'] = fd.read()

    if return_X_y:
        return fmnist.data, fmnist.target
    else:
        return fmnist

def load_mnist(kind='train', variant='mnist', return_X_y=False):
    '''
    Load the MNIST dataset
    variant: {'mnist', 'f-mnist'}
        Which variant to load
    kind: {'train', 'test'}
        Dataset comes pre-split into training and test data.
        Indicates which dataset to load

    '''
    dset = Bunch()

    if kind == 'test':
        kind = 't10k'

    label_path = paths.interim_data_path / variant / f"{kind}-labels-idx1-ubyte"
    with open(label_path, 'rb') as fd:
        dset['target'] = np.frombuffer(fd.read(), dtype=np.uint8, offset=8)
    data_path = paths.interim_data_path / variant / f"{kind}-images-idx3-ubyte"
    with open(data_path, 'rb') as fd:
        dset['data'] = np.frombuffer(fd.read(), dtype=np.uint8,
                                       offset=16).reshape(len(dset['target']), 784)
    with open(_MODULE_DIR / f'{variant}.txt') as fd:
        dset['DESCR'] = fd.read()

    if return_X_y:
        return dset.data, dset.target
    else:
        return dset



def load_dataset(dataset_name, return_X_y=False, **kwargs):
    '''Loads a scikit-learn style dataset
    
    dataset_name:
        Name of dataset to load
    return_X_y: boolean, default=False
        if True, returns (data, target) instead of a Bunch object
    '''

    if dataset_name not in datasets:
        raise Exception(f'Unknown Dataset: {dataset_name}')

    dset = datasets[dataset_name]['load_function'](**kwargs)
    
    if return_X_y:
        return dset.data, dset.target
    else:
        return dset

def load_frey_faces(return_X_y=False):
    '''
    Load the Frey Faces dataset

    Note, there are no labels associated with this dataset; i.e.
    `target` is a vector of all zeros
    '''
    frey_file = fetch('frey-faces')
    
    dset = Bunch()
    ff = loadmat(frey_file, squeeze_me=True, struct_as_record=False)
    ff = ff["ff"].T

    with open(_MODULE_DIR / 'frey-faces.txt') as fd:
        dset['DESCR'] = fd.read()

    dset.data = ff
    dset.target = np.zeros(ff.shape[0])
    
    if return_X_y:
        return dset.data, dset.target
    else:
        return dset
    
    
datasets = {
    'frey-faces': {
        'url': 'https://cs.nyu.edu/~roweis/data/frey_rawface.mat',
        'hash_type': 'sha1',
        'hash_value': '32c4bc7a947721c46df32d4f4973f31daf5d3946',
        'load_function': load_frey_faces,
        },
    'f-mnist': {
        'url_list': [
            {
                'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/train-images-idx3-ubyte.gz',
                'hash_type': 'md5',
                'hash_value': '8d4fb7e6c68d591d4c3dfef9ec88bf0d',
                'name': 'training_data',
            },
            {
                'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/train-labels-idx1-ubyte.gz',
                'hash_type': 'md5',
                'hash_value': '25c81989df183df01b3e8a0aad5dffbe',
                'name': 'training_labels',
            },
            {
                'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/t10k-images-idx3-ubyte.gz',
                'hash_type': 'md5',
                'hash_value': 'bef4ecab320f06d8554ea6380940ec79',
                'name': 'test_data'
            },
            {
                'url': 'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/t10k-labels-idx1-ubyte.gz',
                'hash_type': 'md5',
                'hash_value': 'bb300cfdad3c16e7a12a480ee83cd310',
                'name': 'test_labels'
            },
        ],
        'load_function': partial(load_mnist, variant='f-mnist'),
    },
    'mnist': {
        'url_list': [
            {
                'url': 'http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz',
                'name': 'training_data',
            },
            {
                'url': 'http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz',
                'name': 'training_labels',
            },
            {
                'url': 'http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz',
                'name': 'test_data'
            },
            {
                'url': 'http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz',
                'name': 'test_labels'
            },
        ],
        'load_function': load_mnist,
    },
    'coil-20': {
        'url': 'http://www.cs.columbia.edu/CAVE/databases/SLAM_coil-20_coil-100/coil-20/coil-20-proc.tar.gz',
        'hash_type': 'sha1',
        'hash_value': 'e5d518fa9ef1d81aef7dfa24b398e4a509b2ffd5',
        'load_function': load_coil_20,
    },
    'coil-100': {
        'url': 'http://www.cs.columbia.edu/CAVE/databases/SLAM_coil-20_coil-100/coil-100/coil-100.tar.gz',
        'hash_type': 'sha1',
        'hash_value': 'b58920394780e1c224a39004e74bd3574fbed85a',
        'load_function': load_coil_100,
    },
}

available_datasets = tuple(datasets.keys())
