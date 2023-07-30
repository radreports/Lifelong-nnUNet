import torch
import torch.nn as nn
import numpy as np

class Unflatten(nn.Module):
    def forward(self, x):
        assert len(x.shape)==2  #x: (B, C)
        return x[:, :, None, None]
    
class Resize(nn.Module):
    def __init__(self, shape) -> None:
        super().__init__()
        self.shape = shape
        assert len(self.shape) == 3
    def forward(self, x):
        assert len(x.shape) == len(self.shape)+1, f"{len(x.shape)} == {len(self.shape)}+1"
        assert x.shape[1] == self.shape[0]#<- usually, we do not want to change the num of channels

        left_x = int(np.ceil((x.shape[2] - self.shape[1])/2))
        right_x = x.shape[2] - int(np.floor((x.shape[2] - self.shape[1])/2))

        left_y = int(np.ceil((x.shape[3] - self.shape[2])/2))
        right_y = x.shape[3] - int(np.floor((x.shape[3] - self.shape[2])/2))

        return x[:, :, left_x:right_x, left_y:right_y]


class VAE(nn.Module):
    def __init__(self, shape, hidden_dim) -> None:
        super().__init__()

        #for now:
        assert len(shape) == 3  
        # shape: (C, H, W)

        num_channels =  shape[0]
        assert hidden_dim >= shape[0]

        shape = np.asarray(list(shape))

        encoder = []
        decoder = [Resize(shape),nn.Conv2d(hidden_dim, num_channels,3,1,1)]
        while np.any(shape[1:] >1):
            stride = np.asarray([1,1])
            stride[shape[1:] >1] = 2

            encoder.append(nn.Conv2d(num_channels,hidden_dim,(3,3), stride ,1))
            encoder.append(nn.BatchNorm2d(hidden_dim))
            encoder.append(nn.LeakyReLU(inplace=True))
            encoder.append(nn.Conv2d(hidden_dim,hidden_dim,(3,3),1,1))
            encoder.append(nn.BatchNorm2d(hidden_dim))
            encoder.append(nn.LeakyReLU(inplace=True))


            decoder.append(nn.LeakyReLU(inplace=True))
            decoder.append(nn.BatchNorm2d(hidden_dim))
            decoder.append(nn.Conv2d(hidden_dim,hidden_dim,(3,3),1,1))
            decoder.append(nn.LeakyReLU(inplace=True))
            decoder.append(nn.BatchNorm2d(hidden_dim))
            decoder.append(nn.Conv2d(hidden_dim,hidden_dim,(3,3),1,1))
            decoder.append(nn.ConvTranspose2d(hidden_dim, hidden_dim, stride, stride, bias=False))


            shape = np.ceil(shape /2)
            num_channels=hidden_dim

        #self.encoder = nn.Conv2d(shape[0], hidden_dim,3,2,1)
        encoder.append(nn.Flatten())
        encoder.append(nn.Linear(hidden_dim,hidden_dim))
        encoder.append(nn.BatchNorm1d(hidden_dim))
        encoder.append(nn.LeakyReLU(inplace=True))
        self.encoder = nn.Sequential(*encoder)

        decoder.append(Unflatten())
        decoder.append(nn.LeakyReLU(inplace=True))
        decoder.append(nn.BatchNorm1d(hidden_dim))
        decoder.append(nn.Linear(hidden_dim,hidden_dim))
        self.decoder = nn.Sequential(*(decoder[::-1]))

        self.compute_mean = nn.Linear(hidden_dim, hidden_dim)
        self.compute_log_var = nn.Linear(hidden_dim, hidden_dim)

    def sample_from(self, mean, log_var):
        eps = torch.randn(mean.shape, device=mean.device)
        var = 0.5 * torch.exp(log_var)
        return mean + eps * var

    def encode(self, x):
        x = self.encoder(x)
        return self.compute_mean(x), self.compute_log_var(x)

    def forward(self, x):
        mean, log_var =self.encode(x)

        z = self.sample_from(mean, log_var)
        x_hat = self.decoder(z)
        return x_hat, mean, log_var