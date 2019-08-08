#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
# @Time : 8/6/2019 2:45 PM 
# @Author : gfyulx 
# @File : vgg.py 
# @description: 使用vgg-16模型做迁移学习

import os
import tensorflow as tf
from tensorflow.contrib import slim
import tensorflow.contrib.slim.nets as nets
from six.moves import xrange
import math
import numpy as np
from sklearn.preprocessing import LabelEncoder  # 用于Label编码
from sklearn.preprocessing import OneHotEncoder  # 用于one-hot编码
from tensorflow.python.platform import gfile
import cv2

# 只加载特定参数时，使用variables_to_restore

FLAGS = tf.app.flags.FLAGS  # 定义tensorflow的变量定义 dict
tf.app.flags.DEFINE_string('pre_model_path', "../data/vgg_16.ckpt", '预加载vgg16模型位置')
tf.app.flags.DEFINE_string('model_dir', "./model/vgg", '模型保存目录')
tf.app.flags.DEFINE_string('tfrecord_dir', "../data/tfrecord/flower/", '生成用于队列的tfrecord文件目录')
tf.app.flags.DEFINE_string('data_dir', "../data/flower_photos/", '预加载vgg16模型位置')
tf.app.flags.DEFINE_integer("max_steps", 1000, '最大训练次数')
tf.app.flags.DEFINE_integer('batch_size', 8, '批次大小')
tf.app.flags.DEFINE_integer('num_example_for_train', 1000, '每次训练队列中的最小样本数量')

HEIGHT = 224
WIDTH = 224


# 处理训练数据集
def get_file(data_dir):
    data_dir = FLAGS.data_dir
    contents = os.listdir(data_dir)
    classes = [x for x in contents if os.path.isdir(data_dir + x)]  # 文件夹为所有分类,5类
    labels = []
    images = []
    for i in classes:
        files = os.listdir(data_dir + i)
        for ii, file in enumerate(files, 1):
            # img_raw=tf.gfile.FastGFile(data_dir+i+"/"+file,'rb').read()
            # img=tf.image.decode_jpeg(img_raw)
            # img.set_shape([224, 224, 3])
            images.append(data_dir + i + "/" + file)
            labels.append(i)  # 转为数字标签
    lf = LabelEncoder().fit(labels)
    data_label = lf.transform(labels).tolist()
    return images, data_label


def writeTFRecord():
    if gfile.Exists(FLAGS.tfrecord_dir):
        gfile.DeleteRecursively(FLAGS.tfrecord_dir)
    gfile.MakeDirs(FLAGS.tfrecord_dir)
    images, labels = get_file(FLAGS.data_dir)
    print(len(images),len(labels))
    len_per_shard = 1000  # 每个tfrecord文件的记录数
    num_shards = int(np.ceil(len(images) / len_per_shard))
    for index in xrange(num_shards):
        # 文件编号使用tf-00000n ,代表编号
        filename = os.path.join(FLAGS.tfrecord_dir, 'tfrecord-%.5d' % (index))
        writer = tf.python_io.TFRecordWriter(filename)
        for file, label in zip(images[index * len_per_shard:((index + 1) * len_per_shard)],
                                labels[index * len_per_shard:((index + 1) * len_per_shard)]):
            img_raw = tf.gfile.FastGFile(file, 'rb').read()
            im = cv2.imread(file)
            im1=cv2.resize(im,(224,224))
            im=im1.tobytes()
            sample = tf.train.Example(features=tf.train.Features(
                feature={'image': tf.train.Feature(bytes_list=tf.train.BytesList(value=[im])),
                         "label": tf.train.Feature(int64_list=tf.train.Int64List(value=[label]))}))
            serialized = sample.SerializeToString()
            writer.write(serialized)
        writer.close()


def parse_map(reader):
    return tf.io.parse_single_example(reader, features={'image': tf.io.FixedLenFeature([], tf.string),
                                                        'label': tf.io.FixedLenFeature([], tf.int64)})


# 读取tfrecord文件并写入队列。
def read_and_decode(fileName):
    filename_queue = tf.train.string_input_producer(fileName)
    reader = tf.TFRecordReader()
    _, serialized_sample = reader.read(filename_queue)
    # # reader=tf.data.TFRecordDataset(fileName)
    #
    # features =reader.map(parse_map)
    features = tf.io.parse_single_example(serialized_sample, features={'image': tf.io.FixedLenFeature([], tf.string),
                                                            'label': tf.io.FixedLenFeature([], tf.int64)})

    #print(features)
    img = tf.decode_raw(features['image'], tf.uint8)
    img = tf.reshape(img, [HEIGHT, WIDTH, 3])
    img = tf.cast(img, tf.float32)
    label = features['label']
    label = tf.cast(label, tf.int32)
    return img, label


def input_data(fileName):
    img, label = read_and_decode(fileName)
    num_threads = 16
    capacity = FLAGS.num_example_for_train
    print(img,label)
    images_batch, labels_batch = tf.train.shuffle_batch([img, label], batch_size=FLAGS.batch_size,
                                                        capacity=capacity + 3 * FLAGS.batch_size,
                                                        min_after_dequeue=capacity, num_threads=num_threads)
    return images_batch, labels_batch


def vgg_16(inputs, scope='vgg_16'):
    # inputs是224*224*3 的图像
    # 使用slim快速定义一个vgg16模型，以用于特征提取,.对应到vgg16模型的fc8层之前的所有层
    with tf.variable_scope(scope, 'vgg_16', [inputs]) as sc:
        with slim.arg_scope([slim.conv2d, slim.fully_connected, slim.max_pool2d]):
            net = slim.repeat(inputs, 2, slim.conv2d, 64, [3, 3], scope='conv1')
            net = slim.max_pool2d(net, [2, 2], scope='pool1')
            net = slim.repeat(net, 2, slim.conv2d, 128, [3, 3], scope='conv2')
            net = slim.max_pool2d(net, [2, 2], scope='pool2')
            net = slim.repeat(net, 3, slim.conv2d, 256, [3, 3], scope='conv3')
            net = slim.max_pool2d(net, [2, 2], scope='pool3')
            net = slim.repeat(net, 3, slim.conv2d, 512, [3, 3], scope='conv4')
            net = slim.max_pool2d(net, [2, 2], scope='pool4')
            net = slim.repeat(net, 3, slim.conv2d, 512, [3, 3], scope='conv5')
            net = slim.max_pool2d(net, [2, 2], scope='pool5')
            # net = slim.flatten(net)
            # net = slim.fully_connected(net, 4096, scope='fc6')  #最新版本使用了conv2d代替了fully_connected
            # net = slim.dropout(net, 0.5, scope='dropout6')
            # net = slim.fully_connected(net, 4096, scope='fc7')
            # net = slim.dropout(net, 0.5, scope='dropout6')
            # Use conv2d instead of fully_connected layers.
            net = slim.conv2d(net, 4096, [7, 7], padding='VALID', scope='fc6')
            net = slim.dropout(net, 0.5, is_training=True, scope='dropout6')
            net = slim.conv2d(net, 4096, [1, 1], scope='fc7')
            net = slim.dropout(net, 0.5, is_training=True, scope='dropout7')

    return net


def main():
    data_dir = FLAGS.tfrecord_dir
    contents = os.listdir(data_dir)
    fileNames = [os.path.join(data_dir, x) for x in contents]
    print(fileNames)
    images, labels = input_data(fileNames)
    feature_op = vgg_16(images, "vgg_16")

    gpu_options = tf.GPUOptions(allow_growth=True)
    coord = tf.train.Coordinator()
    init = tf.global_variables_initializer()
    sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))
    sess.run(init)
    exclude_layer = ['vgg_16/fc8']  # 不加载最后的fc8层  --全连接到1000个分类 ## 。
    variables_to_restore = []
    for var in tf.model_variables():
        for exclude in exclude_layer:
            if var.op.name.startswith(exclude):
                continue
            variables_to_restore.append(var)
    saver = tf.train.Saver(variables_to_restore)
    queue_runner = tf.train.start_queue_runners(sess=sess, coord=coord)
    saver.restore(sess, FLAGS.pre_model_path)  # 恢复vg16预训练模型中的参数值
    # sess.run([images,labels])
    # print(images[0])
    for step in xrange(FLAGS.max_steps):
        print(step)
        print(images)
        feature = sess.run(feature_op)
        print(feature)
    # 获取到特征
    # 重新构建分类网络
    coord.request_stop()
    coord.join(queue_runner)
    print("Training end!")


if __name__ == '__main__':
    #writeTFRecord()
    main()
