import numpy as np
from scipy.optimize import curve_fit


def twoD_Gaussian((x, y), amplitude, xo, yo, sigma_x, sigma_y, offset):
    theta = 0
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta) ** 2) / (2 * sigma_x ** 2) + (np.sin(theta) ** 2) / (2 * sigma_y ** 2)
    b = -(np.sin(2 * theta)) / (4 * sigma_x ** 2) + (np.sin(2 * theta)) / (4 * sigma_y ** 2)
    c = (np.sin(theta) ** 2) / (2 * sigma_x ** 2) + (np.cos(theta) ** 2) / (2 * sigma_y ** 2)
    g = offset + amplitude * np.exp(- (a * ((x - xo) ** 2) + 2 * b * (x - xo) * (y - yo)
                                       + c * ((y - yo) ** 2)))
    return g.ravel()


def bilinear_interpolate(im, x, y):
    x = np.asarray(x)
    y = np.asarray(y)

    x0 = np.floor(x).astype(int)
    x1 = x0 + 1
    y0 = np.floor(y).astype(int)
    y1 = y0 + 1

    x0 = np.clip(x0, 0, im.shape[1] - 1)
    x1 = np.clip(x1, 0, im.shape[1] - 1)
    y0 = np.clip(y0, 0, im.shape[0] - 1)
    y1 = np.clip(y1, 0, im.shape[0] - 1)

    Ia = im[y0, x0]
    Ib = im[y1, x0]
    Ic = im[y0, x1]
    Id = im[y1, x1]

    wa = (x1 - x) * (y1 - y)
    wb = (x1 - x) * (y - y0)
    wc = (x - x0) * (y1 - y)
    wd = (x - x0) * (y - y0)

    return wa * Ia + wb * Ib + wc * Ic + wd * Id


def centroid(hdulist):
    data = hdulist[0].data
    cent = np.transpose(np.nonzero(data > 0.9 * np.max(data)))
    cx = int(np.mean(cent[:, 0]))
    cy = int(np.mean(cent[:, 1]))
    roi_size = 200
    x = np.linspace(0, roi_size, roi_size)
    y = np.linspace(0, roi_size, roi_size)
    xx, yy = np.meshgrid(x, y)
    cut_data = data[cx - roi_size / 2:cx + roi_size / 2, cy - roi_size / 2:cy + roi_size / 2]

    initial_guess = (np.max(cut_data), roi_size / 2, roi_size / 2, 25, 25, 0)
    popt, pcov = curve_fit(twoD_Gaussian, (xx, yy), cut_data.ravel(), p0=initial_guess)

    return popt[1] + cy - roi_size / 2, popt[2] + cx - roi_size / 2
