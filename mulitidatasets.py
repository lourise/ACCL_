# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import print_function
import sys

if sys.version_info[0] == 2:
    import cPickle as pickle
else:
    import pickle

import torch.utils.data as data
import torch.utils.data
from datasets_utils import *
from utils import *
from torchvision import transforms
from util import *

mean_datasets = {
    'CIFAR10': [x/255 for x in [125.3,123.0,113.9]],
    'notMNIST': (0.4254,),
    'MNIST': (0.1,) ,
    'SVHN':[0.4377,0.4438,0.4728] ,
    'FashionMNIST': (0.2190,),

}
std_datasets = {
    'CIFAR10': [x/255 for x in [63.0,62.1,66.7]],
    'notMNIST': (0.4501,),
    'MNIST': (0.2752,),
    'SVHN': [0.198,0.201,0.197],
    'FashionMNIST': (0.3318,)
}

classes_datasets = {
    'CIFAR10': 10,
    'notMNIST': 10,
    'MNIST': 10,
    'SVHN': 10,
    'FashionMNIST': 10,
}

lr_datasets = {
    'CIFAR10': 0.001,
    'notMNIST': 0.01,
    'MNIST': 0.01,
    'SVHN': 0.001,
    'FashionMNIST': 0.01,

}


gray_datasets = {
    'CIFAR10': False,
    'notMNIST': True,
    'MNIST': True,
    'SVHN': False,
    'FashionMNIST': True,
}



class DatasetGen(object):
    """docstring for DatasetGen"""

    def __init__(self, args):
        super(DatasetGen, self).__init__()

        self.seed = args.seed
        self.batch_size=args.batch_size
        self.pc_valid=args.pc_valid
        self.root = args.data_folder
        self.latent_dim = args.latent_dim

        self.num_tasks = args.num_tasks
        self.num_samples = args.mem_size
        self.num_all_classes = args.n_cls
        self.num_classes = args.n_cls


        self.inputsize = [3,32,32]

        self.indices = {}
        self.dataloaders = {}
        self.idx={}

        self.num_workers = args.workers
        self.pin_memory = True

        np.random.seed(self.seed)
        self.datasets_idx = list(np.random.permutation(self.num_tasks))
        print('Task order =', [list(classes_datasets.keys())[item] for item in self.datasets_idx])
        self.datasets_names = [list(classes_datasets.keys())[item] for item in self.datasets_idx]


        self.taskcla = []
        self.lrs = []

        for i in range(self.num_tasks):
            t = self.datasets_idx[i]
            self.taskcla.append([i, list(classes_datasets.values())[t]])
            self.lrs.append([i, list(lr_datasets.values())[t]])
        print('Learning Rates =', self.lrs)
        print('taskcla =', self.taskcla)


        self.train_set = {}
        self.train_split = {}
        self.test_set = {}

        self.args=args


        self.dataloaders, self.memory_set = {}, {}
        self.memoryloaders = {}

        self.dataloaders, self.memory_set, self.indices = {}, {}, {}
        self.memoryloaders = {}
        self.saliency_loaders, self.saliency_set = {}, {}

        task_ids = np.split(np.array([i for i in range(self.num_classes)]),self.num_tasks)

        self.task_ids = [list(arr) for arr in task_ids]

        for i in range(self.num_tasks):
            self.dataloaders[i] = {}
            self.memory_set[i] = {}
            self.memoryloaders[i] = {}
            self.indices[i] = {}
            # self.saliency_set = {}
            self.saliency_loaders[i] = {}

        self.download = False

        self.train_set = {}
        self.test_set = {}
        self.train_split = {}

        self.task_memory = {}
        for i in range(self.num_tasks):  # saved samples for replay
            self.task_memory[i] = {}
            for j in self.task_ids[i]:
                self.task_memory[i][j] = {}
                self.task_memory[i][j]['x'] = []
                self.task_memory[i][j]['g_y'] = []  # global label
                self.task_memory[i][j]['y'] = []  # local task label
                self.task_memory[i][j]['tt'] = []  # task id
                self.task_memory[i][j]['td'] = []  #

        self.use_memory = args.use_memory


    def get_dataset(self, dataset_idx, task_num, num_samples_per_class=False, normalize=True):
        dataset_name = list(mean_datasets.keys())[dataset_idx]
        nspc = num_samples_per_class

        normalize = transforms.Normalize(mean_datasets[dataset_name], std_datasets[dataset_name])
        #
        # train_transform = transforms.Compose([
        #     transforms.Resize(size=(self.args.size, self.args.size)),
        #     transforms.RandomResizedCrop(size=self.args.size, scale=(0.1 if self.args.dataset == 'tiny-imagenet' else 0.2, 1.)),
        #     transforms.RandomHorizontalFlip(),
        #     transforms.RandomApply([
        #         transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)
        #     ], p=0.8),
        #     transforms.RandomGrayscale(p=0.2),
        #     transforms.RandomApply([transforms.GaussianBlur(kernel_size=self.args.size // 20 * 2 + 1, sigma=(0.1, 2.0))],
        #                            p=0.5 if self.args.size > 32 else 0.0),
        #     transforms.ToTensor(),
        #     normalize,
        # ])
        # self.transformation = TwoCropTransform(train_transform)  # different transform results to build positive pairs

        if normalize:
            train_transform = transforms.Compose([
                transforms.Resize(size=(self.args.size, self.args.size)),
                transforms.RandomResizedCrop(size=self.args.size,
                                             scale=(0.1 if self.args.dataset == 'tiny-imagenet' else 0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomApply([
                    transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)
                ], p=0.8),
                transforms.RandomGrayscale(p=0.2),
                transforms.RandomApply(
                    [transforms.GaussianBlur(kernel_size=self.args.size // 20 * 2 + 1, sigma=(0.1, 2.0))],
                    p=0.5 if self.args.size > 32 else 0.0),
                transforms.ToTensor(),
                normalize,
            ])
            self.transformation = TwoCropTransform(train_transform)
            mnist_transformation = transforms.Compose([
                transforms.Pad(padding=2, fill=0),
                transforms.Resize(size=(self.args.size, self.args.size)),
                transforms.RandomResizedCrop(size=self.args.size,
                                             scale=(0.1 if self.args.dataset == 'tiny-imagenet' else 0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomApply([
                    transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)
                ], p=0.8),
                transforms.RandomGrayscale(p=0.2),
                # transforms.RandomApply(
                #     [transforms.GaussianBlur(kernel_size=self.args.size // 20 * 2 + 1, sigma=(0.1, 2.0))],
                #     p=0.5 if self.args.size > 32 else 0.0),
                transforms.ToTensor(),
                normalize,
            ])
            self.mnist_transformation = TwoCropTransform(mnist_transformation)
            # transformation = transforms.Compose([transforms.ToTensor(),
            #                                      transforms.Normalize(mean_datasets[dataset_name],std_datasets[dataset_name])])
            # mnist_transformation = transforms.Compose([
            #     transforms.Pad(padding=2, fill=0),
            #     transforms.ToTensor(),
            #     transforms.Normalize(mean_datasets[dataset_name], std_datasets[dataset_name])])
        else:
            train_transform = transforms.Compose([
                transforms.Resize(size=(self.args.size, self.args.size)),
                transforms.RandomResizedCrop(size=self.args.size,
                                             scale=(0.1 if self.args.dataset == 'tiny-imagenet' else 0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomApply([
                    transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)
                ], p=0.8),
                transforms.RandomGrayscale(p=0.2),
                transforms.RandomApply(
                    [transforms.GaussianBlur(kernel_size=self.args.size // 20 * 2 + 1, sigma=(0.1, 2.0))],
                    p=0.5 if self.args.size > 32 else 0.0),
                transforms.ToTensor(),
                # normalize,
            ])
            self.transformation = TwoCropTransform(train_transform)
            self.mnist_transformation = TwoCropTransform(train_transform)
            # transformation = transforms.Compose([transforms.ToTensor()])
            # mnist_transformation = transforms.Compose([
            #     transforms.Pad(padding=2, fill=0),
            #     transforms.ToTensor(),
            #     ])

        # target_transormation = transforms.Compose([transforms.ToTensor()])
        target_transormation = None
        if dataset_idx == 0:
            trainset = CIFAR10_(root=self.root, task_num=task_num, num_samples_per_class=nspc, train=True, download=self.download, target_transform = target_transormation, transform=self.transformation, memory=self.task_memory, memory_class=self.task_ids)
            testset = CIFAR10_(root=self.root,  task_num=task_num, num_samples_per_class=nspc, train=False, download=self.download, target_transform = target_transormation, transform=self.transformation)

        if dataset_idx == 1:
            trainset = notMNIST_(root=self.root, task_num=task_num, num_samples_per_class=nspc, train=True, download=self.download, target_transform = target_transormation, transform=self.mnist_transformation, memory=self.task_memory, memory_class=self.task_ids)
            testset = notMNIST_(root=self.root,  task_num=task_num, num_samples_per_class=nspc, train=False, download=self.download, target_transform = target_transormation, transform=self.mnist_transformation)

        if dataset_idx == 2:
            trainset = MNIST_RGB(root=self.root, train=True, num_samples_per_class=nspc, task_num=task_num, download=self.download, target_transform = target_transormation, transform=self.mnist_transformation, memory=self.task_memory, memory_class=self.task_ids)
            testset = MNIST_RGB(root=self.root,  train=False, num_samples_per_class=nspc, task_num=task_num, download=self.download, target_transform = target_transormation, transform=self.mnist_transformation)

        if dataset_idx == 3:
            trainset = SVHN_(root=self.root,  train=True, num_samples_per_class=nspc, task_num=task_num, download=self.download, target_transform = target_transormation, transform=self.transformation, memory=self.task_memory, memory_class=self.task_ids)
            testset = SVHN_(root=self.root,  train=False, num_samples_per_class=nspc, task_num=task_num, download=self.download, target_transform = target_transormation, transform=self.transformation)

        if dataset_idx == 4:
            trainset = FashionMNIST_(root=self.root, num_samples_per_class=nspc, task_num=task_num, train=True, download=self.download, target_transform = target_transormation, transform=self.mnist_transformation, memory=self.task_memory, memory_class=self.task_ids)
            testset = FashionMNIST_(root=self.root,  num_samples_per_class=nspc, task_num=task_num, train=False, download=self.download, target_transform = target_transormation, transform=self.mnist_transformation)

        return trainset, testset


    def get(self, task_id):

        self.dataloaders[task_id] = {}
        sys.stdout.flush()

        current_dataset_idx = self.datasets_idx[task_id]
        dataset_name = list(mean_datasets.keys())[current_dataset_idx]
        self.train_set[task_id], self.test_set[task_id] = self.get_dataset(current_dataset_idx,task_id)

        self.num_classes = classes_datasets[dataset_name]  # renew the parameters num_classes

        split = int(np.floor(self.pc_valid * len(self.train_set[task_id])))
        train_split, valid_split = torch.utils.data.random_split(self.train_set[task_id],
                                                                 [len(self.train_set[task_id]) - split, split])
        if self.use_memory:
            train_split.dataset.update_memory()
            reply_indices = np.where(np.array(train_split.dataset.train_tt) < task_id)[0].tolist()
            train_split.indices = train_split.indices + reply_indices

        # split = int(np.floor(self.pc_valid * len(self.train_set[task_id])))
        # train_split, valid_split = torch.utils.data.random_split(self.train_set[task_id], [len(self.train_set[task_id]) - split, split])

        # self.train_split[task_id] = train_split
        train_loader = torch.utils.data.DataLoader(train_split, batch_size=self.batch_size, num_workers=self.num_workers,
                                                   pin_memory=self.pin_memory,shuffle=True)
        valid_loader = torch.utils.data.DataLoader(valid_split, batch_size=int(self.batch_size * self.pc_valid),
                                                   num_workers=self.num_workers, pin_memory=self.pin_memory,shuffle=True)
        # test_loader = torch.utils.data.DataLoader(self.test_set[task_id], batch_size=self.batch_size, num_workers=self.num_workers,
        #                                           pin_memory=self.pin_memory,shuffle=True)


        self.dataloaders[task_id]['train'] = train_loader
        self.dataloaders[task_id]['valid'] = valid_loader
        # self.dataloaders[task_id]['test'] = test_loader
        self.dataloaders[task_id]['name'] = '{} - {} classes - {} images'.format(dataset_name,
                                                                              classes_datasets[dataset_name],
                                                                              len(self.train_set[task_id]))
        self.dataloaders[task_id]['classes'] = self.num_classes


        print ("Training set size:   {} images of {}x{}".format(len(train_loader.dataset),self.inputsize[1],self.inputsize[1]))
        print ("Validation set size: {} images of {}x{}".format(len(valid_loader.dataset),self.inputsize[1],self.inputsize[1]))
        print ("Train+Val  set size: {} images of {}x{}".format(len(valid_loader.dataset)+len(train_loader.dataset),self.inputsize[1],self.inputsize[1]))
        # print ("Test set size:       {} images of {}x{}".format(len(test_loader.dataset),self.inputsize[1],self.inputsize[1]))

        if self.use_memory and self.num_samples > 0 :
            self.update_memory(task_id)

        return self.dataloaders

    def get_test_dataloader(self, task_id):

        self.dataloaders[task_id] = {}
        sys.stdout.flush()

        current_dataset_idx = self.datasets_idx[task_id]
        dataset_name = list(mean_datasets.keys())[current_dataset_idx]
        self.train_set[task_id], self.test_set[task_id] = self.get_dataset(current_dataset_idx,task_id)

        test_loader = torch.utils.data.DataLoader(self.test_set[task_id], batch_size=self.batch_size, num_workers=self.num_workers,
                                                  pin_memory=self.pin_memory,shuffle=True)

        self.dataloaders[task_id]['test'] = test_loader
        self.dataloaders[task_id]['name'] = 'Multi-{}-{}'.format(task_id,self.task_ids[task_id])
        print ("Test set size:       {} images of {}x{}".format(len(test_loader.dataset),self.inputsize[1],self.inputsize[1]))

        return self.dataloaders

    # def update_memory(self, task_id):
    #
    #     num_samples_per_class = self.num_samples // len(self.task_ids[task_id])
    #     mem_class_mapping = {i: i for i, c in enumerate(self.task_ids[task_id])}
    #
    #     # Looping over each class in the current task
    #     for i in range(len(self.task_ids[task_id])):
    #         # Getting all samples for this class
    #         data_loader = torch.utils.data.DataLoader(self.train_split[task_id], batch_size=1,
    #                                                   num_workers=self.num_workers,
    #                                                   pin_memory=self.pin_memory)
    #         # Randomly choosing num_samples_per_class for this class
    #         randind = torch.randperm(len(data_loader.dataset))[:num_samples_per_class]
    #
    #         # Adding the selected samples to memory
    #         for ind in randind:
    #             self.task_memory[task_id]['x'].append(data_loader.dataset[ind][0])
    #             self.task_memory[task_id]['y'].append(mem_class_mapping[i])
    #             self.task_memory[task_id]['tt'].append(data_loader.dataset[ind][2])
    #             self.task_memory[task_id]['td'].append(data_loader.dataset[ind][3])
    #
    #     print('Memory updated by adding {} images'.format(len(self.task_memory[task_id]['x'])))

    def update_memory(self, task_id):
        num_classes_per_task = int(self.num_all_classes/self.num_tasks)
        # num_samples_per_class = self.num_samples // (int(self.num_classes/self.num_tasks) * (task_id+1))
        num_samples_per_class_previous = math.floor(self.num_samples / (num_classes_per_task * (task_id + 1)))
        num_samples_per_class_new = math.ceil((self.num_samples - (num_classes_per_task * task_id) * num_samples_per_class_previous) / num_classes_per_task)
        mem_class_mapping = {c: i for i, c in enumerate(self.task_ids[task_id])}

        # val_observed_targets = self.task_ids[task_id]
        # val_unique_cls = np.unique(val_observed_targets)  # 单个样本类别标签


        for class_id in self.task_ids[task_id]:
            p = np.where(np.array(self.train_set[task_id].train_global_labels == class_id))[0].tolist()
            s = data.Subset(self.train_set[task_id], p)
            data_loader = data.DataLoader(s, batch_size=1, num_workers=self.num_workers, pin_memory=self.pin_memory,
                                   shuffle=True)
            # data_loader = torch.utils.data.DataLoader(self.train_set[task_id], batch_size=1,
            #                                             num_workers=self.num_workers,
            #                                             pin_memory=self.pin_memory)

            randind = torch.randperm(len(data_loader.dataset))[:num_samples_per_class_new]  # randomly sample some data


            for ind in randind:
                self.task_memory[task_id][class_id]['x'].append(data_loader.dataset[ind][0])
                self.task_memory[task_id][class_id]['g_y'].append(data_loader.dataset[ind][1])
                self.task_memory[task_id][class_id]['y'].append(mem_class_mapping[class_id])
                self.task_memory[task_id][class_id]['tt'].append(data_loader.dataset[ind][3])
                self.task_memory[task_id][class_id]['td'].append(data_loader.dataset[ind][4])

        for i in range(task_id):
            for j in range(num_classes_per_task):
                self.task_memory[i][self.task_ids[i][j]]['x'] = self.task_memory[i][self.task_ids[i][j]]['x'][:num_samples_per_class_previous]
                self.task_memory[i][self.task_ids[i][j]]['g_y'] = self.task_memory[i][self.task_ids[i][j]]['g_y'][:num_samples_per_class_previous]
                self.task_memory[i][self.task_ids[i][j]]['y'] = self.task_memory[i][self.task_ids[i][j]]['y'][:num_samples_per_class_previous]
                self.task_memory[i][self.task_ids[i][j]]['tt'] = self.task_memory[i][self.task_ids[i][j]]['tt'][:num_samples_per_class_previous]
                self.task_memory[i][self.task_ids[i][j]]['td'] = self.task_memory[i][self.task_ids[i][j]]['td'][:num_samples_per_class_previous]


        print ('Memory updated.')

    def report_size(self,dataset_name,task_id):
        print("Dataset {} size: {} ".format(dataset_name, len(self.train_set[task_id])))

